"""Released SDK/native facades over experimental authenticated carriage."""

import asyncio
import copy
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from carrier import Listener, connect
from configuration import BINDING, StudyReader, resolve
from fixtures import BroadcastPublisher, certificates, contexts, fingerprint

from mesh_plus.api import Client, Endpoint, ReadGuard, ReferenceProfile
from mesh_plus.bridge import Bridge
from mesh_plus.catalog import Catalog
from mesh_plus.evidence import clock_domain, digest
from mesh_plus.testing.cases import profile_cases
from mesh_plus.transport import boottime_ms
from mesh_plus.view import current_sessions


class StateCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mesh-wss-state-")
        self.root = Path(self.temp.name)
        await asyncio.to_thread(certificates, self.root)
        self.server_context, self.client_context = contexts(self.root)
        self.listeners = []
        self.readers = []
        self.clients = []
        self.publishers = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        for listener in self.listeners:
            await listener.close()
            self.assertFalse(listener.tasks)
            self.assertFalse(listener.channels)
            self.assertEqual(listener.unexpected, 0)
        for reader in self.readers:
            self.assertEqual(reader.inspect()["activeConnections"], 0)
        for publisher in self.publishers:
            self.assertEqual(publisher.watchers, 0)
        self.temp.cleanup()

    async def setup(self, domain, host="beta", near_expiry=False, heartbeat=.1):
        import json
        publisher = BroadcastPublisher(domain, host)
        if near_expiry:
            earliest = min(r["expiry"] for r in publisher.codec.inspect_native(publisher.frame).receipts)
            publisher.age(earliest - boottime_ms() - 3500)
        self.publishers.append(publisher)
        binding = [host, publisher.source, publisher.profile]
        async def policy():
            return {fingerprint(self.root): binding}
        listener = await Listener(self.server_context, Bridge(publisher, heartbeat_interval=heartbeat).serve,
                                  policy, binding, policy_interval=.05).start()
        self.listeners.append(listener)
        catalog = Catalog(json.loads(files("mesh_plus.testing").joinpath("catalog.json").read_text()))
        registry = {"protocol": BINDING, "endpoints": [{"hostId": host, "sourceId": "default",
                    "profile": publisher.profile, "url": listener.url, "product": "state",
                    "capabilities": ["snapshot", "proof", "subscribe"]}]}
        bound = resolve(catalog, registry, digest({"trust": 1}))[0]
        async def connection():
            channel = await connect(bound.url, self.client_context)
            client = await Client.connect(channel, host=bound.host, source=bound.source,
                                          profile=bound.profile, codec=publisher.validate)
            self.clients.append(client)
            return client
        async def revision():
            return bound.selection_revision
        reader = StudyReader(domain, [Endpoint(host, False, bound.token, connection, publisher.codec)],
                             local_host="alpha", catalog_revision=bound.selection_revision,
                             catalog_check=revision, profile=publisher.state_profile, bindings=(bound,))
        self.readers.append(reader)
        return publisher, listener, reader, bound

    async def until(self, iterator, guard, predicate, timeout=5):
        async def wait():
            while True:
                view = await anext(iterator)
                guard.accept(view)
                if predicate(view):
                    return view
        return await asyncio.wait_for(wait(), timeout)

    async def test_both_domains_watch_update_restart_disconnect_reconnect_expiry(self):
        for domain in ("tmux", "agent"):
            with self.subTest(domain=domain):
                publisher, listener, reader, _ = await self.setup(domain, near_expiry=True)
                request = "a" * 32
                guard = ReadGuard(domain, request, profile=publisher.state_profile)
                watch = reader.watch(request_id=request, proof_interval=.1)
                def ready(v):
                    return "mesh" in v and v["mesh"]["hosts"][0]["delivery"]["status"] == "ready"
                try:
                    first = await self.until(watch, guard, ready)
                    self.assertEqual(first["mesh"]["hosts"][0]["delivery"]["path"], "wss")
                    self.assertTrue(guard.current(boottime_ms(), clock_domain()))
                    original = copy.deepcopy(publisher.codec.inspect_native(publisher.frame).receipts)
                    publisher.update()
                    changed = await self.until(watch, guard, lambda v: ready(v) and
                                               v["mesh"]["hosts"][0]["owner"]["service"]["viewRevision"] ==
                                               publisher.frame["viewRevision"])
                    self.assertTrue(any((r["name"] if domain == "tmux" else r["title"]).startswith("revision-")
                                        for r in changed["sessions"]))
                    publisher.update(restart=True)
                    restarted = await self.until(watch, guard, lambda v: ready(v) and v["mesh"]["kind"] == "resync")
                    epoch = restarted["mesh"]["hosts"][0]["delivery"]["epoch"]
                    for channel in list(listener.channels):
                        channel.writer.transport.abort()
                    revoked = await self.until(watch, guard, lambda v: not ready(v))
                    self.assertEqual(revoked["mesh"]["hosts"][0]["delivery"]["path"], "wss")
                    self.assertFalse(guard.current(boottime_ms(), clock_domain()))
                    await self.until(watch, guard, lambda v: ready(v) and
                                     v["mesh"]["hosts"][0]["delivery"]["epoch"] > epoch)
                    def expired_runtime(v):
                        if not ready(v):
                            return False
                        return all(r["health"] not in {"current", "partial"}
                                   for r in v["mesh"]["hosts"][0]["receipts"]
                                   if domain == "tmux" or r["component"] == "runtime")
                    expired = await self.until(watch, guard, expired_runtime, timeout=8)
                    self.assertEqual(publisher.codec.inspect_native(publisher.frame).receipts, original)
                    # Agent saved history can remain eligible; runtime receipts must expire.
                    self.assertTrue(expired_runtime(expired))
                    self.assertFalse(guard.current(boottime_ms(), clock_domain()))
                finally:
                    await watch.aclose()

    async def test_full_nonce_proof_forgery_revokes_rows_both_domains(self):
        for domain in ("tmux", "agent"):
            publisher, _, reader, _ = await self.setup(domain)
            good = publisher.wrap
            for mutation in ("nonce", "digest", "clock", "receipt"):
                def forged(nonce=None):
                    reply = good(nonce)
                    if nonce:
                        if mutation == "nonce":
                            reply["nonce"] = "b" * 32
                        elif mutation == "digest":
                            reply["ownerDigest"] = "sha256:" + "0" * 64
                        elif mutation == "clock":
                            reply["clock"] = {**reply["clock"], "bootId": "00000000-0000-0000-0000-000000000000"}
                        else:
                            reply["remaining"][0]["remainingMs"] += 1
                    return reply
                with self.subTest(domain=domain, mutation=mutation), patch.object(publisher, "wrap", forged):
                    view = await reader.snapshot()
                    self.assertEqual(view["mesh"]["hosts"][0]["delivery"]["status"], "unavailable")
                    self.assertEqual(view["sessions"], [])

    async def test_broadcast_is_independent_and_requests_continue_during_push(self):
        for domain in ("tmux", "agent"):
            publisher, _, reader, _ = await self.setup(domain)
            endpoint = reader.endpoints[0]
            clients = [await endpoint.connect() for _ in range(2)]
            subscriptions = [await client.subscribe() for client in clients]
            try:
                for sub in subscriptions:
                    await asyncio.wait_for(anext(sub), 2)
                publisher.update()
                frames = await asyncio.gather(*(asyncio.wait_for(anext(sub), 2) for sub in subscriptions))
                self.assertTrue(all(frame["payload"]["ownerFrame"]["viewRevision"] == publisher.frame["viewRevision"]
                                    for frame in frames))
                await subscriptions[0].close()
                await clients[1].request("proof", {"nonce": "c" * 32})
                publisher.update()
                frame = await asyncio.wait_for(anext(subscriptions[1]), 2)
                self.assertEqual(frame["kind"], "data")
            finally:
                for sub in subscriptions:
                    await sub.close()

    async def test_reader_catalog_terminal_and_handle_rotation(self):
        publisher, _, reader, _ = await self.setup("tmux")
        guard = ReadGuard("tmux", "d" * 32, profile=publisher.state_profile)
        watch = reader.watch(request_id="d" * 32, proof_interval=.1, catalog_interval=.05)
        def ready(v):
            return "mesh" in v and v["mesh"]["status"] == "complete"
        try:
            with patch("mesh_plus.client.ROTATION_HANDLES", 4):
                await self.until(watch, guard, lambda v: ready(v) and reader.inspect()["rotations"] >= 2)
            self.assertGreaterEqual(reader.inspect()["connectionsOpened"], 3)
            async def changed():
                return digest({"changed": True})
            reader.catalog_check = changed
            terminal = await self.until(watch, guard, lambda v: "error" in v and "mesh" not in v)
            self.assertEqual(terminal["error"]["code"], "scope_changed")
            self.assertFalse(guard.current(boottime_ms(), clock_domain()))
        finally:
            await watch.aclose()

    async def test_listener_restart_and_healthy_sibling_survive_failed_host(self):
        from dataclasses import replace
        profile = ReferenceProfile("tmux")
        _, _, first_reader, a = await self.setup("tmux", "beta")
        _, second, second_reader, b = await self.setup("tmux", "gamma")
        revision = digest({"ordered": [a.token, b.token]})
        bindings = [replace(binding, selection_revision=revision) for binding in (a, b)]
        endpoints = [replace(reader.endpoints[0], route_token=binding.token)
                     for reader, binding in zip((first_reader, second_reader), bindings, strict=True)]
        async def catalog():
            return revision
        reader = StudyReader("tmux", endpoints, local_host="alpha", catalog_revision=revision,
                             catalog_check=catalog, profile=profile, bindings=bindings)
        self.readers.append(reader)
        guard = ReadGuard("tmux", "e" * 32, profile=profile)
        watch = reader.watch(request_id="e" * 32, proof_interval=.1)
        try:
            await self.until(watch, guard, lambda v: v.get("mesh", {}).get("status") == "complete")
            port = second.port
            await second.close()
            partial = await self.until(watch, guard, lambda v: v.get("mesh", {}).get("status") == "partial")
            self.assertEqual(partial["mesh"]["hosts"][0]["delivery"]["status"], "ready")
            self.assertEqual(partial["mesh"]["hosts"][1]["delivery"]["path"], "wss")
            self.assertTrue(any(profile.record_host(row) == "beta" for row in guard.current(boottime_ms(), clock_domain())))
            replacement = await Listener(second.context, second.handler, second.policy, second.binding,
                                         policy_interval=.05).start(port)
            self.listeners.append(replacement)
            recovered = await self.until(watch, guard, lambda v: v.get("mesh", {}).get("status") == "complete")
            self.assertEqual(recovered["mesh"]["kind"], "resync")
        finally:
            await watch.aclose()

    async def test_frozen_empty_warming_historical_partial_and_unsaved_cases(self):
        for domain in ("tmux", "agent"):
            publisher, _, reader, _ = await self.setup(domain)
            for case in profile_cases(domain):
                if len(case.response["mesh"]["hosts"]) != 1:
                    continue
                with self.subTest(case=case.case_id):
                    original_host = case.response["mesh"]["hosts"][0]
                    frame = copy.deepcopy(case.native[original_host["hostId"]])
                    # Preserve the corpus consumer time, not just source time:
                    # historical cases intentionally evaluate later than emission.
                    shift = boottime_ms() - 100 - case.selections[0]["now_ms"]
                    clock = clock_domain()
                    def rewrite(value):
                        if isinstance(value, dict):
                            for key, item in value.items():
                                if key in {"hostId", "hostScope", "authority"}:
                                    value[key] = "beta"
                                elif key in {"encodedAt", "startedAt", "finishedAt", "acceptedAt", "expiresAt",
                                             "lastAttemptAt", "emittedBoottimeMs", "sampledBoottimeMs", "expiresBoottimeMs"} and type(item) is int:
                                    value[key] += shift
                                elif key == "bootId":
                                    value[key] = clock["bootId"]
                                elif key == "timeNamespace":
                                    value[key] = clock["timeNamespace"]
                                elif key == "clockDomain":
                                    value[key] = "time:[" + clock["timeNamespace"].split(":")[1] + "]"
                                else:
                                    rewrite(item)
                        elif isinstance(value, list):
                            for item in value:
                                rewrite(item)
                    rewrite(frame)
                    publisher.frame = frame
                    publisher.codec.inspect_native(frame)
                    if original_host["viewState"] == "historical":
                        # Corpus historical views can contain a formerly current
                        # owner frame. Age the whole source cache, preserving its
                        # original native lease, so a NEW nonce proof is expired.
                        latest = max(r["expiry"] for r in publisher.codec.inspect_native(frame).receipts)
                        publisher.age(latest - boottime_ms() + 200)
                    view = await reader.snapshot()
                    host = view["mesh"]["hosts"][0]
                    self.assertEqual(host["delivery"]["status"], "ready")
                    self.assertEqual(host["viewState"], original_host["viewState"])
                    self.assertEqual(len(current_sessions(view, boottime_ms(), clock_domain(), profile=publisher.state_profile)),
                                     len(case.selections[0]["rows"]))

    async def test_slow_consumer_gap_resync_deadline_and_terminal_barrier(self):
        publisher, _, reader, _ = await self.setup("tmux", heartbeat=5)
        client = await reader.endpoints[0].connect()
        sub = await client.subscribe()
        try:
            await asyncio.wait_for(anext(sub), 2)
            for _ in range(80):
                publisher.update()
                await asyncio.sleep(.01)
            gap = False
            for _ in range(80):
                frame = await asyncio.wait_for(anext(sub), 2)
                if frame["kind"] == "control" and frame["control"] == "gap":
                    gap = True
                if gap and frame["kind"] == "data":
                    self.assertEqual(frame["deliveryKind"], "resync")
                    break
            self.assertTrue(gap)
            original = publisher.snapshot
            async def slow(parameters):
                await asyncio.sleep(.1)
                return await original(parameters)
            with patch.object(publisher, "snapshot", slow), self.assertRaises(Exception):
                await client.request(timeout_ms=10)
            await asyncio.sleep(.15)
            self.assertEqual((await client.request())["hostId"], "beta")
        finally:
            await sub.close()
        with self.assertRaises(StopAsyncIteration):
            await anext(sub)
        self.assertFalse(client.subscriptions)

    async def test_real_handle_budget_rotates_without_tombstone_reuse(self):
        from dataclasses import replace

        from mesh_plus.client import ROTATION_HANDLES
        publisher, _, initial, binding = await self.setup("tmux", heartbeat=5)
        opening = initial.endpoints[0].connect
        warmed = await opening()
        for _ in range(ROTATION_HANDLES):
            await warmed.request()
        self.assertTrue(warmed.rotation_due())
        self.assertEqual(len(warmed.guard.handles), ROTATION_HANDLES)
        used = False
        async def connection():
            nonlocal used
            if not used:
                used = True
                return warmed
            return await opening()
        endpoint = replace(initial.endpoints[0], connect=connection)
        reader = StudyReader("tmux", [endpoint], local_host="alpha", profile=publisher.state_profile,
                             catalog_revision=binding.selection_revision, catalog_check=initial.catalog_check,
                             bindings=(binding,))
        self.readers.append(reader)
        guard = ReadGuard("tmux", "f" * 32, profile=publisher.state_profile)
        watch = reader.watch(request_id="f" * 32, proof_interval=.1)
        try:
            await self.until(watch, guard, lambda v: v.get("mesh", {}).get("status") == "complete")
            self.assertTrue(warmed.channel.closed)
            self.assertEqual(reader.inspect()["rotations"], 1)
            self.assertEqual(len(warmed.guard.handles), ROTATION_HANDLES)
        finally:
            await watch.aclose()
