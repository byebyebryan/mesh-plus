"""SDK conformance without native packages, inheritance or bound-method discovery."""

import asyncio
import builtins
import copy
import inspect
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sdk_fixture import ROOT, Profile, Publisher

from mesh_plus.api import (
    SDK_INTERFACE_VERSION,
    Bridge,
    Client,
    Endpoint,
    Reader,
    ReadGuard,
    configured_reader,
    current_sessions,
    reconstructed,
    validate_response,
)
from mesh_plus.catalog import Catalog
from mesh_plus.protocol import ProtocolError
from mesh_plus.remote import connect_catalog_host
from mesh_plus.transport import IPCServer, boottime_ms, connect_ipc


def blocked_import(name, *args, **kwargs):
    if name.startswith(("tmux_observer", "agent_observer", "mesh_plus.observer")) or name == "observer":
        raise AssertionError("SDK imported native reference integration: " + name)
    return ORIGINAL_IMPORT(name, *args, **kwargs)


ORIGINAL_IMPORT = builtins.__import__


class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_combined_bridge_admission_keeps_mesh_checks_and_strict_fallback(self):
        from mesh_plus.state import validate_bridge

        publisher = Publisher("agent", "local")
        profile = publisher.state_profile
        codec = profile.bind("local", "default")
        payload = publisher.wrap("a" * 32)
        original = codec.inspect_native
        with patch.object(codec, "validate_bridge", wraps=codec.validate_bridge) as validate, \
                patch.object(codec, "inspect_native", wraps=original) as inspect_native:
            validate_bridge(profile, codec, payload)
            self.assertEqual((validate.call_count, inspect_native.call_count), (1, 1))
        calls = []

        def admit(payload):
            calls.append(payload)
            return original(payload["ownerFrame"])

        codec.admit_bridge = admit
        with patch.object(codec, "validate_bridge", side_effect=AssertionError("duplicate validate")), \
                patch.object(codec, "inspect_native", side_effect=AssertionError("duplicate inspect")):
            state = validate_bridge(profile, codec, payload)
        self.assertEqual(state, original(payload["ownerFrame"]))
        self.assertEqual(len(calls), 1)
        for kind in ("digest", "clock", "receipts", "scope", "native", "state"):
            bad = copy.deepcopy(payload)
            codec.admit_bridge = admit
            if kind == "digest":
                bad["ownerDigest"] = "sha256:" + "0" * 64
            elif kind == "clock":
                bad["clock"]["bootId"] = "00000000-0000-0000-0000-000000000000"
            elif kind == "receipts":
                bad["remaining"][0]["remainingMs"] += 1
            elif kind == "scope":
                bad["hostId"] = "foreign"
            elif kind == "native":
                codec.admit_bridge = lambda payload: replace(original(payload["ownerFrame"]), records=[])
            else:
                codec.admit_bridge = lambda payload: None
            with self.subTest(kind=kind), self.assertRaises(Exception):
                validate_bridge(profile, codec, bad)

    async def test_owned_watch_and_execute_share_request_checks_and_cleanup(self):
        from prepared_fixture import StaticPreparation

        from mesh_plus.api import AdmittedResponse, PreparedReadGuard

        publisher = Publisher("agent", "local")
        profile = publisher.state_profile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            reader = await configured_reader("agent", source="default", socket=path, scope="local",
                                             local_host="local", profile=profile)
            request = {"meshProtocol": 1, "requestId": "a" * 32, "profile": profile.descriptor.profile_id,
                       "operation": "watch", "access": "cached", "selection": {"mode": "local", "hostIds": []},
                       "extensions": {}}
            stream = reader.execute_admitted(request)
            guard = PreparedReadGuard("agent", "a" * 32, profile=profile, preparation=StaticPreparation(profile))
            try:
                for _ in range(10):
                    frame = await asyncio.wait_for(anext(stream), 2)
                    self.assertIs(type(frame), AdmittedResponse)
                    guard.accept(frame)
                    context = guard.context()
                    if guard.current(boottime_ms(), context["mesh"]["reader"]["clock"]):
                        break
                self.assertEqual(guard.snapshot()["sessions"], publisher.frame["snapshot"]["sessions"])
            finally:
                guard.disconnect()
                await stream.aclose()
                await server.close()
            self.assertEqual(reader.inspect()["activeConnections"], 0)
            self.assertEqual(publisher.watchers, 0)
            request["selection"] = {"mode": "hosts", "hostIds": ["foreign"]}
            self.assertEqual([f async for f in reader.execute_admitted(request)][0]["error"]["code"], "unknown_host")

    def test_runtime_version_matches_installed_distribution_metadata(self):
        from importlib.metadata import version

        import mesh_plus

        self.assertEqual(mesh_plus.__version__, version("mesh-plus"))

    def setUp(self):
        self.blocker = patch("builtins.__import__", side_effect=blocked_import)
        self.blocker.start()
        self.addCleanup(self.blocker.stop)

    async def test_configured_poll_and_push_full_profile_path_and_owned_close(self):
        for domain in ("tmux", "agent"):
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as directory:
                publisher = Publisher(domain, "local")
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
        catalog = Catalog(json.loads((ROOT / "reference/rofi-ssh-plus/contracts/host-mesh-v1/fixtures/valid/list-multi-route.json").read_text()))
        host = catalog.select("hosts", ["beta"])[0]
        publisher = Publisher("agent", "beta", source="agent")
        codec = publisher.state_profile.bind("beta", "agent")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "remote.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            async def connector(*args, **kwargs):
                channel = await connect_ipc(path)
                channel.reached_count = 1
                return channel
            async def connect():
                return await connect_catalog_host(catalog, host, "agent", "agent", profile=publisher.state_profile,
                                                  codec=codec, connector=connector)
            reader = Reader("agent", [Endpoint("beta", False, catalog.route_token("beta", host["routes"][0]),
                                                connect, codec)], local_host=catalog.local_host,
                            catalog_revision=catalog.revision, profile=publisher.state_profile)
            try:
                response = await reader.snapshot()
                self.assertEqual(response["mesh"]["status"], "complete")
                self.assertIsNotNone(response["mesh"]["hosts"][0]["delivery"]["proof"])
            finally:
                await server.close()

    async def test_wrong_binding_rejected_before_dispatch_and_mutation_rejected(self):
        profile = Profile("tmux")
        connect = AsyncMock()
        codec = profile.bind("wrong", "default")
        with self.assertRaisesRegex(ProtocolError, "endpoint_codec_binding"):
            Reader("tmux", [Endpoint("local", True, None, connect, codec)], local_host="local", profile=profile)
        connect.assert_not_awaited()
        codec = profile.bind("local", "default")
        client = AsyncMock()
        reader = Reader("tmux", [Endpoint("local", True, None, connect, codec)], local_host="local", profile=profile)
        codec.source = "changed"
        with self.assertRaisesRegex(ProtocolError, "endpoint_codec_binding"):
            await reader.read_host(client, reader.endpoints[0])
        client.request.assert_not_awaited()
        profile.descriptor = replace(profile.descriptor, sdk_version=2)
        with self.assertRaisesRegex(ProtocolError, "profile_descriptor"):
            await configured_reader("tmux", source="default", socket="/owned/socket", local_host="local", profile=profile)

    async def test_wrong_client_hello_cannot_dispatch_request(self):
        publisher = Publisher("tmux", "local")
        codec = publisher.state_profile.bind("local", "default")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            client = await Client.connect(await connect_ipc(path), host="local", source="default",
                                          profile=publisher.profile, codec=lambda payload: None)
            reader = Reader("tmux", [Endpoint("local", True, None, AsyncMock(), codec)], local_host="local",
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
            publisher = Publisher("agent", "remote")
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
            reader = Reader("agent", [Endpoint("remote", False, "sha256:" + "a" * 64, connect, codec)],
                            local_host="local", catalog_revision="sha256:" + "b" * 64, profile=publisher.state_profile)
            with self.subTest(fault=fault):
                response = await reader.snapshot()
                self.assertEqual(response["sessions"], [])
                self.assertEqual(response["mesh"]["status"], "unavailable")
                client.close.assert_awaited_once()

    async def test_independent_frozen_views_roundtrip_expiry_and_adversarial_validation(self):
        for domain in ("tmux", "agent"):
            profile = Profile(domain)
            for path in (ROOT / "contracts/mesh-read-v1/examples").glob(domain + "-*.json"):
                response = json.loads(path.read_text())
                with self.subTest(path=path.name):
                    validate_response(response, profile=profile)
                    self.assertEqual(current_sessions(response, 2**52, response["mesh"]["reader"]["clock"], profile=profile), [])
            response = json.loads((ROOT / f"contracts/mesh-read-v1/examples/{domain}-fleet.json").read_text())
            for mutation in ("missing_receipt", "expiry", "proof", "duplicate", "reconstruction"):
                altered = copy.deepcopy(response)
                if mutation == "missing_receipt":
                    altered["mesh"]["hosts"][0]["receipts"].pop()
                elif mutation == "expiry":
                    altered["mesh"]["hosts"][0]["receipts"][0]["expiresAtMs"] += 100
                elif mutation == "proof":
                    altered["mesh"]["hosts"][1]["delivery"]["proof"]["payloadDigest"] = "sha256:" + "0" * 64
                elif mutation == "duplicate":
                    altered["sessions"].insert(0, copy.deepcopy(altered["sessions"][0]))
                else:
                    altered["mesh"]["hosts"][1]["owner"]["service"]["viewRevision"] += 1
                with self.subTest(domain=domain, mutation=mutation), self.assertRaises(Exception):
                    validate_response(altered, profile=profile)
            profile.record_receipts = lambda row, state: frozenset()
            self.assertEqual(current_sessions(response, response["mesh"]["reader"]["encodedAtMs"],
                                              response["mesh"]["reader"]["clock"], profile=profile), [])

    async def test_sdk_version_and_defaults_are_additive(self):
        self.assertEqual(SDK_INTERFACE_VERSION, 1)
        from mesh_plus import api
        baseline = json.loads((ROOT / "tests/fixtures/sdk-interface-v1.json").read_text())
        self.assertEqual(sorted(set(api.__all__) - {"CachedSource", "CachedPublication", "CachedPublisher",
                         "PREPARATION_INTERFACE_VERSION", "PreparationDescriptor", "PreparationState",
                     "PreparedReadGuard", "PreparedRule", "StatePreparation", "ADMISSION_INTERFACE_VERSION",
                     "AdmittedResponse", "SELECTION_INTERFACE_VERSION", "SelectionRule", "PreparedSelection"}),
                         baseline["exports"])
        self.assertEqual({name: str(inspect.signature(getattr(api, name))) for name in baseline["signatures"]},
                         baseline["signatures"])
        profile = Profile("agent")
        with self.assertRaisesRegex(ProtocolError, "profile_descriptor"):
            Reader("tmux", [Endpoint("local", True, None, AsyncMock())], local_host="local", profile=profile)

    async def test_setup_deadline_keeps_healthy_host_and_cancellation_retires_setup(self):
        publisher = Publisher("tmux", "local")
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
            reader = Reader("tmux", [Endpoint("local", True, None, healthy, profile.bind("local", "default")),
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
        publisher = Publisher("tmux", "local")
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
        reader = Reader("tmux", [Endpoint("local", True, None, healthy, profile.bind("local", "default")),
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
        profile = Profile("agent")
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/agent-local.json").read_text())
        response["mesh"].update(operation="watch", requestId="a" * 32)
        guard = ReadGuard("agent", "a" * 32, profile=profile)
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
        replacement["mesh"]["hosts"][0]["owner"]["service"]["serviceId"] = "22222222-2222-4222-8222-222222222222"
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
        reader = Reader("agent", [Endpoint("remote", False, "sha256:" + "a" * 64, connect,
                                          profile.bind("remote", "default"))], local_host="local",
                        catalog_revision="sha256:" + "b" * 64, catalog_check=changed, profile=profile)
        watch = reader.watch()
        try:
            await anext(watch)
            terminal = await asyncio.wait_for(anext(watch), 1)
            self.assertEqual(terminal["error"]["code"], "scope_changed")
        finally:
            await watch.aclose()
