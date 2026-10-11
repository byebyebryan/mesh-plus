"""Portable owned IPC/remote-proof lifecycle tests for any accepted profile."""

import asyncio
import copy
import json
import tempfile
import unittest
import uuid
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ..api import (
    Bridge,
    Client,
    Endpoint,
    Reader,
    ReadGuard,
    configured_reader,
    current_sessions,
    reconstructed,
)
from ..catalog import Catalog
from ..protocol import ProtocolError
from ..remote import connect_catalog_host
from ..transport import IPCServer, boottime_ms, connect_ipc
from .cases import profile_cases
from .sample import Publisher


class _Binding:
    def __init__(self, value):
        self.value = value

    def __getattr__(self, name):
        return getattr(self.value, name)


class _NetworkTests(unittest.IsolatedAsyncioTestCase):
    def __init__(self, methodName="runTest"):
        super().__init__(methodName)
        self.case_id = "network-" + self.domain + "-" + self._testMethodName.removeprefix("test_")

    def _profile(self):
        return self.factory(self.domain)

    def _publisher(self, host, source="default"):
        return self.publisher_factory(self.domain, host, source, self._profile())

    async def _publisher_transition(self, restart):
        for local in (True, False):
            with self.subTest(local=local), tempfile.TemporaryDirectory() as directory:
                host = "local" if local else "remote"
                publisher = self._publisher(host)
                profile = publisher.state_profile
                path = Path(directory) / "mesh.sock"
                server = await IPCServer(path, Bridge(publisher).serve).start()
                clients = []
                async def connect():
                    client = await Client.connect(await connect_ipc(path), host=host, source="default",
                                                  profile=publisher.profile, codec=publisher.validate)
                    clients.append(client)
                    return client
                revision = "sha256:" + "b" * 64
                async def catalog_check():
                    return revision
                reader = Reader(self.domain, [Endpoint(host, local, None if local else "sha256:" + "a" * 64,
                                                       connect, profile.bind(host, "default"))],
                                local_host="local", catalog_revision=None if local else revision,
                                catalog_check=None if local else catalog_check, profile=profile)
                request_id = "c" * 32
                guard = ReadGuard(self.domain, request_id, host_ids=[host], profile=profile)
                # Long proof cadence makes the pushed update, rather than a
                # scheduled read, responsible for observing the new frame.
                watch = reader.watch(proof_interval=60, request_id=request_id)
                async def until(predicate):
                    async with asyncio.timeout(3):
                        async for response in watch:
                            guard.accept(response)
                            if predicate(response):
                                return response
                    self.fail("watch ended before publisher transition")
                try:
                    request_metric = "snapshotRequests" if local else "proofRequests"
                    def settled_baseline(response):
                        if not clients or response["mesh"]["hosts"][0]["delivery"]["status"] != "ready":
                            return False
                        metrics = clients[0].inspect()
                        return (metrics["operations"][request_metric] >= 2 and metrics["pendingRequests"] == 0
                                and metrics["channel"]["byKind"]["received"].get("data", {}).get("frames", 0) >= 1)
                    baseline = await until(settled_baseline)
                    initial_epoch = baseline["mesh"]["hosts"][0]["delivery"]["epoch"]
                    self.assertTrue(guard.current(boottime_ms(), baseline["mesh"]["reader"]["clock"]))
                    original = copy.deepcopy(publisher.frame)
                    changed = copy.deepcopy(original)
                    title_key = "name" if self.domain == "tmux" else "title"
                    changed["snapshot"]["sessions"][0][title_key] = "conformance pushed update"
                    changed["viewRevision"] += 1
                    changed["sequence"] += 1
                    publisher_key = "publisherId" if self.domain == "tmux" else "serviceId"
                    if restart:
                        changed[publisher_key] = str(uuid.uuid4())
                    publisher.frame = changed
                    await publisher.changes.put(None)
                    if restart:
                        revoked = await until(lambda r: r["mesh"]["hosts"][0]["delivery"]["status"] == "unavailable")
                        self.assertEqual(guard.current(boottime_ms(), revoked["mesh"]["reader"]["clock"]), [])
                    replacement = await until(lambda r: r["mesh"]["hosts"][0]["delivery"]["status"] == "ready"
                                              and reconstructed(r, r["mesh"]["hosts"][0], profile=profile) == changed)
                    outcome = replacement["mesh"]["hosts"][0]
                    if restart:
                        self.assertEqual(replacement["mesh"]["kind"], "resync")
                        self.assertGreater(outcome["delivery"]["epoch"], initial_epoch)
                        self.assertGreaterEqual(len(clients), 2)
                    else:
                        self.assertEqual(outcome["delivery"]["epoch"], initial_epoch)
                        self.assertEqual(len(clients), 1)
                        self.assertGreaterEqual(clients[0].inspect()["channel"]["byKind"]["received"]["data"]["frames"], 2)
                    if not local:
                        self.assertIsNotNone(outcome["delivery"]["proof"])
                    rows = guard.current(boottime_ms(), replacement["mesh"]["reader"]["clock"])
                    self.assertTrue(rows)
                    self.assertEqual(rows[0][title_key], "conformance pushed update")
                    # Delivery changes never renew original source receipts.
                    self.assertEqual(profile.bind(host, "default").inspect_native(original).receipts,
                                     profile.bind(host, "default").inspect_native(changed).receipts)
                finally:
                    guard.disconnect()
                    await watch.aclose()
                    await server.close()
                self.assertEqual(publisher.watchers, 0)
                self.assertTrue(all(client.channel.closed for client in clients))
                self.assertEqual(reader.inspect()["activeConnections"], 0)
                self.assertEqual(reader.inspect()["cleanupFailures"], 0)

    async def test_pushed_update_crosses_carrier_with_original_receipts(self):
        await self._publisher_transition(restart=False)

    async def test_publisher_restart_revokes_then_resyncs_through_carrier(self):
        await self._publisher_transition(restart=True)

    async def test_configured_poll_and_push_full_profile_path_and_owned_close(self):
        for domain in (self.domain,):
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as directory:
                publisher = self._publisher("local")
                path = Path(directory) / "mesh.sock"
                server = await IPCServer(path, Bridge(publisher).serve).start()
                authority = AsyncMock()
                reader = await configured_reader(domain, source="default", socket=path, scope="local",
                                                 local_host="local", authority=authority, profile=publisher.state_profile)
                watch = reader.watch(proof_interval=.1, request_id="a" * 32)
                try:
                    response = await reader.snapshot()
                    self.assertEqual(response["mesh"]["status"], "complete")
                    self.assertEqual(reconstructed(response, response["mesh"]["hosts"][0],
                                                   profile=publisher.state_profile), publisher.frame)
                    self.assertTrue(current_sessions(response, boottime_ms(), response["mesh"]["reader"]["clock"],
                                                     profile=publisher.state_profile))
                    guard = ReadGuard(domain, "a" * 32, profile=publisher.state_profile)
                    for _ in range(10):
                        frame = await asyncio.wait_for(anext(watch), 2)
                        guard.accept(frame)
                        if guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]):
                            break
                    self.assertTrue(guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]))
                    guard.disconnect()
                    self.assertEqual(guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]), [])
                finally:
                    await watch.aclose()
                    await server.close()
                authority.load.assert_not_awaited()
                self.assertEqual(publisher.watchers, 0)
                self.assertEqual(reader.inspect()["activeConnections"], 0)

    async def test_remote_route_uses_same_profile_and_checked_hello(self):
        catalog = Catalog(json.loads(files(__package__).joinpath("catalog.json").read_text()))
        host = catalog.select("hosts", ["beta"])[0]
        publisher = self._publisher("beta", source=self.domain)
        codec = publisher.state_profile.bind("beta", self.domain)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "remote.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            async def connector(*args, **kwargs):
                channel = await connect_ipc(path)
                channel.reached_count = 1
                return channel
            async def connect():
                return await connect_catalog_host(catalog, host, self.domain, self.domain, profile=publisher.state_profile,
                                                  codec=codec, connector=connector)
            reader = Reader(self.domain, [Endpoint("beta", False, catalog.route_token("beta", host["routes"][0]),
                                                connect, codec)], local_host=catalog.local_host,
                            catalog_revision=catalog.revision, profile=publisher.state_profile)
            try:
                response = await reader.snapshot()
                self.assertEqual(response["mesh"]["status"], "complete")
                self.assertIsNotNone(response["mesh"]["hosts"][0]["delivery"]["proof"])
            finally:
                await server.close()

    async def test_wrong_binding_rejected_before_dispatch_and_mutation_rejected(self):
        profile = self._profile()
        connect = AsyncMock()
        codec = profile.bind("wrong", "default")
        with self.assertRaisesRegex(ProtocolError, "endpoint_codec_binding"):
            Reader(self.domain, [Endpoint("local", True, None, connect, codec)], local_host="local", profile=profile)
        connect.assert_not_awaited()
        codec = _Binding(profile.bind("local", "default"))
        client = AsyncMock()
        reader = Reader(self.domain, [Endpoint("local", True, None, connect, codec)], local_host="local", profile=profile)
        codec.source = "changed"
        with self.assertRaisesRegex(ProtocolError, "endpoint_codec_binding"):
            await reader.read_host(client, reader.endpoints[0])
        client.request.assert_not_awaited()
        profile = _Binding(profile)
        profile.descriptor = replace(profile.descriptor, sdk_version=2)
        with self.assertRaisesRegex(ProtocolError, "profile_descriptor"):
            await configured_reader(self.domain, source="default", socket="/owned/socket", local_host="local", profile=profile)

    async def test_wrong_client_hello_cannot_dispatch_request(self):
        publisher = self._publisher("local")
        codec = publisher.state_profile.bind("local", "default")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            client = await Client.connect(await connect_ipc(path), host="local", source="default",
                                          profile=publisher.profile, codec=lambda payload: None)
            reader = Reader(self.domain, [Endpoint("local", True, None, AsyncMock(), codec)], local_host="local",
                            profile=publisher.state_profile)
            try:
                client.guard.hello["sourceId"] = "wrong"
                with patch.object(client, "request", new_callable=AsyncMock) as request:
                    with self.assertRaisesRegex(ProtocolError, "endpoint_client_binding"):
                        await reader.read_host(client, reader.endpoints[0])
                    request.assert_not_awaited()
            finally:
                await client.close()
                await server.close()

    async def test_forged_bridge_nonce_digest_receipts_clock_do_not_grant_rows(self):
        for fault in ("nonce", "digest", "receipt", "clock", "host", "source"):
            publisher = self._publisher("remote")
            codec = publisher.state_profile.bind("remote", "default")
            client = AsyncMock()
            del client.guard
            del client.inspect
            del client.route_token
            async def request(operation, parameters, **kwargs):
                result = publisher.wrap(parameters["nonce"])
                if fault == "nonce":
                    result["nonce"] = "0" * 32
                elif fault == "digest":
                    result["ownerDigest"] = "sha256:" + "0" * 64
                elif fault == "receipt":
                    result["remaining"].pop()
                elif fault == "clock":
                    result["clock"]["timeNamespace"] = "time:999"
                elif fault == "host":
                    result["hostId"] = "other"
                else:
                    result["sourceId"] = "other"
                return result
            client.request.side_effect = request
            async def connect():
                return client
            reader = Reader(self.domain, [Endpoint("remote", False, "sha256:" + "a" * 64, connect, codec)],
                            local_host="local", catalog_revision="sha256:" + "b" * 64, profile=publisher.state_profile)
            with self.subTest(fault=fault):
                response = await reader.snapshot()
                self.assertEqual(response["sessions"], [])
                self.assertEqual(response["mesh"]["status"], "unavailable")
                client.close.assert_awaited_once()

    async def test_setup_deadline_keeps_healthy_host_and_cancellation_retires_setup(self):
        publisher = self._publisher("local")
        profile = publisher.state_profile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            cancelled = asyncio.Event()
            clients = []
            async def healthy():
                client = await Client.connect(await connect_ipc(path), host="local", source="default",
                                              profile=publisher.profile, codec=lambda payload: None)
                clients.append(client)
                return client
            async def blocked():
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            reader = Reader(self.domain, [Endpoint("local", True, None, healthy, profile.bind("local", "default")),
                                      Endpoint("remote", False, "sha256:" + "a" * 64, blocked,
                                               profile.bind("remote", "default"))], local_host="local",
                            catalog_revision="sha256:" + "b" * 64, profile=profile)
            try:
                response = await reader.snapshot(timeout_ms=50)
                self.assertEqual(response["mesh"]["status"], "partial")
                self.assertEqual(response["mesh"]["hosts"][1]["delivery"]["error"]["code"], "timeout")
                self.assertTrue(response["sessions"])
                self.assertTrue(cancelled.is_set())
                cancelled.clear()
                task = asyncio.create_task(reader.snapshot())
                await asyncio.sleep(.02)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertTrue(cancelled.is_set())
                self.assertTrue(all(c.channel.closed for c in clients))
                self.assertEqual(reader.inspect()["activeConnections"], 0)
            finally:
                await server.close()

    async def test_snapshot_repeated_cancellation_waits_for_all_sibling_cleanup(self):
        publisher = self._publisher("local")
        profile = publisher.state_profile
        started, release, blocked_started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        client = AsyncMock()
        del client.guard
        del client.inspect
        del client.route_token
        client.request.return_value = publisher.wrap()
        async def close():
            started.set()
            await release.wait()
        client.close.side_effect = close
        async def healthy():
            return client
        async def blocked():
            blocked_started.set()
            await asyncio.Event().wait()
        reader = Reader(self.domain, [Endpoint("local", True, None, healthy, profile.bind("local", "default")),
                                  Endpoint("remote", False, "sha256:" + "a" * 64, blocked,
                                           profile.bind("remote", "default"))], local_host="local",
                        catalog_revision="sha256:" + "b" * 64, profile=profile)
        task = asyncio.create_task(reader.snapshot())
        try:
            await asyncio.wait_for(started.wait(), 1)
            await asyncio.wait_for(blocked_started.wait(), 1)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(.01)
                self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(reader.inspect()["activeConnections"], 0)
            self.assertEqual(reader.inspect()["connectionsOpened"], reader.inspect()["connectionsClosed"])
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    async def test_gap_restart_and_catalog_change_revoke_without_native_imports(self):
        profile = self._profile()
        response = next(c.response for c in profile_cases(self.domain) if c.case_id == self.domain + "-local")
        response["mesh"].update(operation="watch", requestId="a" * 32)
        guard = ReadGuard(self.domain, "a" * 32, profile=profile)
        guard.accept(response)
        gap = copy.deepcopy(response)
        gap.pop("sessions")
        gap["mesh"].pop("hosts")
        gap["mesh"].pop("scope")
        gap["mesh"].pop("catalog")
        gap["mesh"].pop("status")
        gap["mesh"].pop("extensions")
        gap["mesh"]["kind"] = "gap"
        gap["mesh"]["reader"]["sequence"] += 1
        guard.accept(gap)
        self.assertEqual(guard.current(response["mesh"]["reader"]["encodedAtMs"],
                                       response["mesh"]["reader"]["clock"]), [])
        replacement = copy.deepcopy(response)
        replacement["mesh"]["reader"].update(sequence=3, revision=2)
        replacement["mesh"]["hosts"][0]["owner"]["service"]["publisherId" if self.domain == "tmux" else "serviceId"] = "22222222-2222-4222-8222-222222222222"
        with self.assertRaisesRegex(ProtocolError, "read_resync_required"):
            guard.accept(replacement)
        self.assertEqual(guard.sequence, 2)
        replacement["mesh"]["kind"] = "resync"
        guard.accept(replacement)
        guard.disconnect()
        self.assertEqual(guard.current(2**52, response["mesh"]["reader"]["clock"]), [])
        async def changed():
            return "sha256:" + "c" * 64
        connect = AsyncMock(side_effect=asyncio.CancelledError)
        reader = Reader(self.domain, [Endpoint("remote", False, "sha256:" + "a" * 64, connect,
                                          profile.bind("remote", "default"))], local_host="local",
                        catalog_revision="sha256:" + "b" * 64, catalog_check=changed, profile=profile)
        watch = reader.watch()
        try:
            await anext(watch)
            terminal = await asyncio.wait_for(anext(watch), 1)
            self.assertEqual(terminal["error"]["code"], "scope_changed")
        finally:
            await watch.aclose()

def network_suite(profile_factory, *, domain, publisher_factory=None):
    """Create owned lifecycle tests; connector binding uses IPC, not actual SSH."""
    if domain not in {"tmux", "agent"}:
        raise ValueError("conformance_domain")
    def publisher(domain, host, source, profile):
        return Publisher(domain, host, source, profile=profile)
    test_class = type("OwnerNetworkTests", (_NetworkTests,), {
        "domain": domain, "factory": staticmethod(profile_factory),
        "publisher_factory": staticmethod(publisher_factory or publisher),
    })
    return unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
