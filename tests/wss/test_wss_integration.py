"""Promotion regressions: real mixed carriers, public factory and IO ownership."""

import asyncio
import json
import sys
import tempfile
import threading
import time
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from wss_fixtures import BroadcastPublisher, ReferenceProfile, certificates, contexts, fingerprint

from mesh_plus.api import Client, ReadGuard
from mesh_plus.bridge import Bridge
from mesh_plus.evidence import clock_domain
from mesh_plus.protocol import ProtocolError
from mesh_plus.remote import connect_catalog_host
from mesh_plus.testing.sample import Publisher
from mesh_plus.testing.ssh_carrier import ssh_server
from mesh_plus.transport import IPCServer, boottime_ms
from mesh_plus.wss import Listener, Selection, configured_reader, connect
from mesh_plus.wss.local_files import LocalReadOwner


class IntegrationCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mesh-wss-integration-")
        self.root = Path(self.temp.name)
        await asyncio.to_thread(certificates, self.root)
        self.server_context, self.client_context = contexts(self.root)
        self.selections = []
        self.listeners = []

    async def asyncTearDown(self):
        for listener in self.listeners:
            await listener.close()
            self.assertFalse(listener.channels)
            self.assertFalse(listener.tasks)
            self.assertEqual(listener.unexpected, 0)
        for selection in self.selections:
            selection.close()
        self.temp.cleanup()

    async def selection(self, domain):
        publisher = BroadcastPublisher(domain)
        async def policy():
            return {fingerprint(self.root): ["beta", "default", publisher.profile]}
        listener = await Listener(self.server_context, Bridge(publisher).serve, policy,
                                  ["beta", "default", publisher.profile], policy_interval=.05).start()
        self.listeners.append(listener)
        catalog = self.root / "catalog.json"
        catalog.write_bytes(files("mesh_plus.testing").joinpath("catalog.json").read_bytes())
        registry = self.root / "registry.json"
        registry.write_text(json.dumps({"protocol": "mesh-plus.wss.v1", "endpoints": [
            {"hostId": "beta", "sourceId": "default", "profile": publisher.profile,
             "url": listener.url, "product": "state", "capabilities": ["snapshot", "proof", "subscribe"]}]}))
        for path in (catalog, registry):
            path.chmod(0o600)
        selected = Selection.load(catalog, registry, self.root / "ca.pem", self.root / "client.pem",
                                  self.root / "client.key")
        self.selections.append(selected)
        return publisher, listener, selected

    async def test_real_mixed_factory_poll_watch_failure_tokens_both_profiles(self):
        for domain in ("tmux", "agent"):
            publisher, listener, selection = await self.selection(domain)
            profile = ReferenceProfile(domain)
            local = Publisher(domain, "alpha", profile=profile)
            socket = self.root / (domain + ".sock")
            server = await IPCServer(socket, Bridge(local).serve).start()
            # Real SSH authentication/stdio; explicit connector injection only redirects
            # the captured synthetic catalog destination into its disposable daemon.
            native = "ReferenceProfile" if type(profile).__name__ == "ReferenceProfile" else "Profile"
            imports = ("from mesh_plus.api import ReferenceProfile" if native == "ReferenceProfile" else
                       "from mesh_plus.testing.sample import Profile")
            program = ("import asyncio; " + imports + "; from mesh_plus.testing.sample import Publisher; "
                       "from mesh_plus.bridge import Bridge; from mesh_plus.cli import stdio_channel; "
                       "async def_placeholder")
            program = program.replace("async def_placeholder", "\nasync def run():\n"
                                      f"    await Bridge(Publisher('{domain}', 'gamma', profile={native}('{domain}'))).serve(await stdio_channel())\n"
                                      "asyncio.run(run())\n")
            try:
                with tempfile.TemporaryDirectory(prefix=".mesh-wss-ssh-", dir=Path.home()) as name:
                    async with ssh_server(Path(name), [sys.executable, "-B", "-c", program], "default") as opening:
                        async def remote(catalog, host, domain, source, **kwargs):
                            return await connect_catalog_host(catalog, host, domain, source,
                                                              connector=lambda *a, **k: opening(), **kwargs)
                        with patch("mesh_plus.wss.configured_read.connect_catalog_host", remote):
                            reader = await configured_reader(domain, selection=selection, source="default",
                                                             socket=socket, profile=profile)
                            response = await reader.snapshot()
                            self.assertEqual(response["mesh"]["status"], "complete", response)
                            outcomes = response["mesh"]["hosts"]
                            self.assertEqual([h["delivery"]["path"] for h in outcomes], ["ipc", "wss", "ssh"])
                            self.assertEqual(outcomes[1]["delivery"]["routeToken"], selection.bindings[0].token)
                            gamma = selection.catalog.hosts[2]
                            self.assertEqual(outcomes[2]["delivery"]["routeToken"],
                                             selection.catalog.route_token("gamma", gamma["routes"][0]))
                            self.assertEqual(response["mesh"]["catalog"]["revision"], selection.revision)
                            self.assertEqual(reader.inspect()["byteScope"], "mixed")
                            guard = ReadGuard(domain, "a" * 32, profile=profile)
                            watch = reader.watch(request_id="a" * 32, proof_interval=.1)
                            try:
                                for _ in range(20):
                                    frame = await asyncio.wait_for(anext(watch), 4)
                                    guard.accept(frame)
                                    if frame["mesh"]["status"] == "complete":
                                        break
                                self.assertEqual(frame["mesh"]["status"], "complete")
                                self.assertTrue(guard.current(boottime_ms(), clock_domain()))
                                publisher.update()
                                for _ in range(20):
                                    frame = await asyncio.wait_for(anext(watch), 4)
                                    guard.accept(frame)
                                    if frame["mesh"]["hosts"][1]["owner"]["service"]["viewRevision"] == publisher.frame["viewRevision"]:
                                        break
                                self.assertEqual(frame["mesh"]["hosts"][1]["owner"]["service"]["viewRevision"],
                                                 publisher.frame["viewRevision"])
                            finally:
                                await watch.aclose()
                            await listener.close()
                            response = await reader.snapshot()
                            self.assertEqual(response["mesh"]["status"], "partial")
                            self.assertEqual(response["mesh"]["hosts"][1]["delivery"]["path"], "wss")
                            self.assertEqual([h["delivery"]["status"] for h in response["mesh"]["hosts"]],
                                             ["ready", "unavailable", "ready"])
                            self.assertEqual(reader.inspect()["activeConnections"], 0)
            finally:
                await server.close()

    async def test_health_changes_do_not_revoke_but_private_key_and_registry_do(self):
        _, _, selection = await self.selection("tmux")
        original = selection.paths[0].read_bytes()
        catalog = json.loads(original)
        catalog["generatedAt"] += 1
        catalog["hosts"][1]["routes"][0]["lastReachableAt"] = catalog["generatedAt"]
        selection.paths[0].write_text(json.dumps(catalog))
        self.assertEqual(await selection.check(), selection.revision)
        # A caller's mutable Catalog projection cannot alter the captured authority.
        selection.catalog.payload["hosts"][1]["id"] = "changed"
        self.assertEqual(selection.catalog.hosts[1]["id"], "beta")
        self.assertNotIn(selection.key_bytes.decode(), repr(selection))
        selection.paths[-1].write_bytes(b"changed")
        with self.assertRaises(ProtocolError):
            await selection.check()

    async def test_wss_operation_bytes_match_channel_scope(self):
        publisher, _, selection = await self.selection("tmux")
        client = await Client.connect(await connect(selection.bindings[0].url, selection.context),
                                      host="beta", source="default", profile=publisher.profile,
                                      codec=publisher.validate)
        try:
            await client.request()
            report = client.inspect()
            self.assertEqual(report["operations"]["snapshotResultBytes"],
                             report["channel"]["byKind"]["received"]["result"]["bytes"])
            self.assertEqual(report["operations"]["unprocessedResultBytes"], 0)
        finally:
            await client.close()

    async def test_send_validation_time_is_inside_budget_and_closes(self):
        _, _, selection = await self.selection("tmux")
        channel = await connect(selection.bindings[0].url, selection.context)
        from mesh_plus.wss.carrier import validate
        async def receive():
            await channel.receive()
        consumer = asyncio.create_task(receive())
        original_clock = boottime_ms()
        def expired(*args):
            validate(*args)
            clock.return_value = original_clock + 3000
        hello = json.loads((Path(__file__).resolve().parents[2] /
                            "contracts/mesh-delivery-v1/examples/client-hello.json").read_text())
        with patch("mesh_plus.wss.carrier.boottime_ms", return_value=original_clock) as clock:
            with patch("mesh_plus.wss.carrier.validate", expired), self.assertRaises(ProtocolError):
                await channel.send(hello)
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
        self.assertTrue(channel.closed)
        self.assertTrue(channel.pump.done())

    async def test_setup_phases_share_one_deadline_before_dispatch(self):
        _, listener, selection = await self.selection("tmux")
        original = listener.policy
        observed = 0
        started = boottime_ms()

        async def policy():
            nonlocal observed
            observed += 1
            allowed = await original()
            if observed == 2:
                clock.return_value = started + 16000
            return allowed

        listener.policy = policy
        with patch("mesh_plus.wss.carrier.boottime_ms", return_value=started) as clock:
            with patch("mesh_plus.transport.boottime_ms", clock), self.assertRaises(Exception):
                await connect(selection.bindings[0].url, selection.context)
        self.assertEqual(observed, 2)
        self.assertEqual(listener.dispatched, 0)

    async def test_snapshot_scope_check_shares_short_acquisition_budget(self):
        publisher, _, selection = await self.selection("tmux")
        reader = await configured_reader("tmux", selection=selection, source="default",
                                         socket=self.root / "unused.sock", scope="hosts", hosts=["beta"],
                                         profile=publisher.state_profile)

        async def delayed():
            await asyncio.sleep(.1)
            return selection.revision

        reader.catalog_check = delayed
        with self.assertRaises(TimeoutError):
            await reader.snapshot(timeout_ms=20)
        self.assertEqual(reader.inspect()["connectionAttempts"], 0)


class LocalFilesCase(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_and_close_report_owned_job_and_reject_replacement(self):
        owner = LocalReadOwner()
        release = threading.Event()
        calls = []
        def blocked():
            calls.append(1)
            release.wait(2)
            return "late"
        try:
            with self.assertRaises(TimeoutError):
                await owner.read(blocked, timeout_ms=20)
            with self.assertRaises(ProtocolError):
                await owner.read(blocked, timeout_ms=20)
            with self.assertRaises(ProtocolError):
                owner.close(timeout=.01)
            self.assertEqual(calls, [1])
            release.set()
            await asyncio.to_thread(owner.thread.join, 1)
            owner.close(timeout=.1)
            with self.assertRaises(ProtocolError):
                await owner.read(lambda: "new")
        finally:
            release.set()
            owner.close(timeout=2)

    async def test_queue_admission_uses_same_deadline(self):
        owner = LocalReadOwner()
        release = threading.Event()
        first = asyncio.create_task(owner.read(lambda: release.wait(1)))
        await asyncio.sleep(.02)
        try:
            with self.assertRaises(TimeoutError):
                await owner.read(lambda: time.sleep(.1), timeout_ms=20)
        finally:
            release.set()
            await first
            owner.close()
