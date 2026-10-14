"""Public publisher/factory acceptance with independent profiles and cached sources."""

import asyncio
import copy
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from publisher_fixture import Source, factory
from sdk_fixture import Profile
from test_sdk import blocked_import

from mesh_plus.api import Bridge, CachedPublication, CachedPublisher, Client
from mesh_plus.cli import configured_adapter, publisher_factory_map
from mesh_plus.evidence import digest
from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import IPCServer, connect_ipc

TESTS = Path(__file__).resolve().parent


def config(root, domain, host="local"):
    path = root / "sources.toml"
    path.write_text(f'version=1\nhost="{host}"\n[sources.default]\ndomain="{domain}"\nsocket="/unused"\n')
    path.chmod(0o600)
    return path


def launcher(root, domain, path):
    script = root / "launch.py"
    script.write_text(f'''import sys
sys.path.insert(0, {str(TESTS)!r})
from publisher_fixture import factory
from mesh_plus.cli import main
raise SystemExit(main(publisher_factories={{{domain!r}: factory({domain!r})}}))
''')
    return [sys.executable, "-I", str(script)]


class PublisherTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fence = patch("builtins.__import__", side_effect=blocked_import)
        self.fence.start()
        self.addCleanup(self.fence.stop)

    def make(self, domain="tmux"):
        source = Source(domain, "local")
        return CachedPublisher(domain, "local", "default", source, profile=Profile(domain)), source

    async def test_snapshot_proof_ownership_and_remaining_leases(self):
        for domain in ("tmux", "agent"):
            publisher, source = self.make(domain)
            candidate = await publisher.snapshot({})
            original = copy.deepcopy(candidate)
            proof = await publisher.proof({"nonce": "a" * 32})
            self.assertEqual(source.reads, 2)
            self.assertEqual(proof["nonce"], "a" * 32)
            self.assertEqual(proof["ownerDigest"], digest(candidate["ownerFrame"]))
            self.assertEqual(proof["sequence"], candidate["sequence"] + 1)
            self.assertEqual(candidate["remaining"], [])
            source.fixture.frame["viewRevision"] += 1
            self.assertEqual(candidate, original)
            self.assertNotEqual((await publisher.proof({"nonce": "b" * 32}))["ownerDigest"], proof["ownerDigest"])
            for bad in ({}, {"nonce": "bad"}, {"nonce": "a" * 32, "extra": 1}, None):
                reads = source.reads
                with self.assertRaises(ProtocolError):
                    await publisher.proof(bad)
                self.assertEqual(source.reads, reads)

    async def test_counter_lease_clock_and_failed_admission(self):
        for domain in ("tmux", "agent"):
            publisher, source = self.make(domain)
            frame = source.fixture.frame
            receipt = frame["receipt"] if domain == "tmux" else frame["sources"][0]["components"][0]
            receipt["accepted"] = 2
            await publisher.snapshot({})
            receipt = frame["receipt"] if domain == "tmux" else frame["sources"][0]["components"][0]
            expiry = "expiresAt" if domain == "tmux" else "expiresBoottimeMs"
            for key, value, code in (("accepted", receipt["accepted"] - 1, "source_receipt_regression"),
                                     (expiry, receipt[expiry] + 1, "source_lease_renewal")):
                old = receipt[key]
                receipt[key] = value
                before = (publisher.sequence, copy.deepcopy(publisher._read_history.accepted), publisher._read_history.owner_binding)
                with self.assertRaisesRegex(ProtocolError, code):
                    await publisher.snapshot({})
                self.assertEqual(before, (publisher.sequence, publisher._read_history.accepted, publisher._read_history.owner_binding))
                receipt[key] = old
            with patch.object(publisher, "validate", side_effect=ProtocolError("test_reject")):
                before = publisher.sequence
                with self.assertRaises(ProtocolError):
                    await publisher.snapshot({})
                self.assertEqual(publisher.sequence, before)
            if domain == "tmux":
                frame["clock"]["timeNamespace"] = "time:999"
            else:
                frame["clockDomain"] = "time:[999]"
            with self.assertRaisesRegex(ProtocolError, "source_clock_context"):
                await publisher.snapshot({})

    async def test_cross_stream_completion_order_does_not_revoke_receipts(self):
        for domain in ("tmux", "agent"):
            publisher, source = self.make(domain)
            entered, release = asyncio.Event(), asyncio.Event()
            old = copy.deepcopy(source.fixture.frame)

            async def delayed_snapshot():
                entered.set()
                await release.wait()
                return old

            source.snapshot = delayed_snapshot
            read = asyncio.create_task(publisher.snapshot({}))
            await entered.wait()
            watch = publisher.watch()
            receipt = (source.fixture.frame["receipt"] if domain == "tmux"
                       else source.fixture.frame["sources"][0]["components"][0])
            receipt["accepted"] += 1
            publication = await anext(watch)
            release.set()
            result = await read
            self.assertEqual(result["ownerFrame"], old)
            self.assertLess(publication.payload["sequence"], result["sequence"])
            await watch.aclose()

    async def test_each_watch_checks_its_own_history_despite_newer_reads(self):
        for domain in ("tmux", "agent"):
            publisher, source = self.make(domain)
            receipt = (source.fixture.frame["receipt"] if domain == "tmux"
                       else source.fixture.frame["sources"][0]["components"][0])
            receipt["accepted"] = 2
            watch = publisher.watch()
            await anext(watch)
            original = receipt["accepted"]
            receipt["accepted"] = original + 1
            await publisher.proof({"nonce": "a" * 32})
            receipt["accepted"] = original
            source.fixture.changes.put_nowait(None)
            await anext(watch)  # Older than the independent proof, same watch receipt.
            expiry = "expiresAt" if domain == "tmux" else "expiresBoottimeMs"
            receipt[expiry] += 1
            source.fixture.changes.put_nowait(None)
            with self.assertRaisesRegex(ProtocolError, "source_lease_renewal"):
                await anext(watch)
            await watch.aclose()
            receipt[expiry] -= 1
            watch = publisher.watch()
            await anext(watch)
            receipt["accepted"] = original - 1
            source.fixture.changes.put_nowait(None)
            with self.assertRaisesRegex(ProtocolError, "source_receipt_regression"):
                await anext(watch)
            await watch.aclose()

    async def test_snapshot_and_proof_serialize_native_acquisition_and_cancel_waiters(self):
        publisher, source = self.make()
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def delayed():
            calls.append(len(calls))
            entered.set()
            await release.wait()
            return source.fixture.frame

        source.snapshot = delayed
        first = asyncio.create_task(publisher.snapshot({}))
        await entered.wait()
        cancelled = asyncio.create_task(publisher.proof({"nonce": "a" * 32}))
        await asyncio.sleep(0)
        self.assertEqual(len(calls), 1)
        cancelled.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await cancelled
        release.set()
        await first
        await publisher.proof({"nonce": "b" * 32})
        self.assertEqual(len(calls), 2)
        self.assertFalse(publisher._read_lock.locked())

    async def test_watch_epoch_barrier_ownership_and_cleanup(self):
        for domain in ("tmux", "agent"):
            publisher, source = self.make(domain)
            watch = publisher.watch()
            publication = await anext(watch)
            saved = copy.deepcopy(publication)
            source.fixture.frame["viewRevision"] += 1
            self.assertEqual(publication, saved)
            task = asyncio.create_task(anext(watch))
            await asyncio.sleep(.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await watch.aclose()
            self.assertEqual(source.fixture.watchers, 0)
            async def wrong():
                yield CachedPublication(source.fixture.frame, "wrong", {})
            source.watch = wrong
            watch = publisher.watch()
            with self.assertRaisesRegex(ProtocolError, "native_epoch_binding"):
                await anext(watch)
            await watch.aclose()

    async def test_repeated_cancellation_cannot_abandon_watch_retirement(self):
        publisher, source = self.make()
        started, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def native_watch():
            try:
                frame = source.fixture.frame
                yield CachedPublication(frame, source.fixture.codec.inspect_native(frame).publisher, {})
            finally:
                started.set()
                await release.wait()
                closed.set()
        source.watch = native_watch
        watch = publisher.watch()
        await anext(watch)
        task = asyncio.create_task(watch.aclose())
        try:
            await asyncio.wait_for(started.wait(), 1)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(.01)
                self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(closed.is_set())
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    async def test_factory_binding_failure_and_explicit_profile(self):
        with tempfile.TemporaryDirectory() as name:
            path = config(Path(name), "tmux")
            for value, code in ((lambda *a: None, "publisher_factory_binding"),
                                (lambda *a: SimpleNamespace(host="local", source="default",
                                   profile=Profile("tmux").descriptor.profile_id, capabilities=("actions",)),
                                 "publisher_factory_interface")):
                with self.assertRaisesRegex(ProtocolError, code):
                    configured_adapter(path, "default", publisher_factories={"tmux": value})
            selected = configured_adapter(path, "default", publisher_factories={"tmux": factory("tmux")})
            self.assertEqual(selected.host, "local")
            self.assertIsInstance(selected, CachedPublisher)
            def fail(*args):
                raise RuntimeError("selected factory failed")
            with self.assertRaisesRegex(RuntimeError, "selected factory failed"):
                configured_adapter(path, "default", publisher_factories={"tmux": fail})
            with self.assertRaisesRegex(ProtocolError, "publisher_profile_required"):
                CachedPublisher("tmux", "local", "default", Source("tmux", "local"), profile=None)
            mapping = {"tmux": factory("tmux")}
            captured = publisher_factory_map(mapping)
            mapping.clear()
            self.assertIn("tmux", captured)
            with self.assertRaisesRegex(ProtocolError, "publisher_factory_mapping"):
                publisher_factory_map({"anything": factory("tmux")})

    async def test_ipc_poll_push_and_restart(self):
        for domain in ("tmux", "agent"):
            with tempfile.TemporaryDirectory() as name:
                root = Path(name)
                publisher = configured_adapter(config(root, domain), "default", publisher_factories={domain: factory(domain)})
                server = await IPCServer(root / "mesh.sock", Bridge(publisher).serve).start()
                client = None
                try:
                    client = await Client.connect(await connect_ipc(root / "mesh.sock"), host="local", source="default",
                                                  profile=publisher.profile, codec=publisher.validate)
                    self.assertEqual((await client.request("snapshot", {}))["kind"], "candidate")
                    self.assertEqual((await client.request("proof", {"nonce": "a" * 32}))["nonce"], "a" * 32)
                    sub = await client.subscribe()
                    first = await asyncio.wait_for(anext(sub), 2)
                    self.assertEqual(first["kind"], "data")
                    frame = publisher.native.fixture.frame
                    frame["publisherId" if domain == "tmux" else "serviceId"] = "22222222-2222-4222-8222-222222222222"
                    publisher.native.fixture.changes.put_nowait(None)
                    with self.assertRaises(Exception):
                        while True:
                            await asyncio.wait_for(anext(sub), 2)
                    await sub.close()
                finally:
                    if client is not None:
                        await client.close()
                    await server.close()
                self.assertEqual(publisher.native.fixture.watchers, 0)


class PublisherCLITests(unittest.IsolatedAsyncioTestCase):
    async def test_installed_style_cli_serve_both_domains_and_sigterm_cleanup(self):
        for domain in ("tmux", "agent"):
            with tempfile.TemporaryDirectory() as name:
                root = Path(name)
                path = config(root, domain)
                command = launcher(root, domain, path)
                child = await asyncio.create_subprocess_exec(*command, "serve", "--source", "default", "--config", str(path),
                                                            "--socket", str(root / "mesh.sock"), stderr=asyncio.subprocess.PIPE)
                client = None
                try:
                    for _ in range(200):
                        if (root / "mesh.sock").exists() or child.returncode is not None:
                            break
                        await asyncio.sleep(.01)
                    self.assertIsNone(child.returncode)
                    client = await Client.connect(await connect_ipc(root / "mesh.sock"), host="local", source="default",
                                                  profile=Profile(domain).descriptor.profile_id, codec=lambda p: None)
                    self.assertEqual((await client.request("proof", {"nonce": "a" * 32}))["kind"], "proof")
                    sub = await client.subscribe()
                    self.assertEqual((await asyncio.wait_for(anext(sub), 2))["kind"], "data")
                    await sub.close()
                    await client.close()
                    client = None
                    child.send_signal(signal.SIGTERM)
                    _, stderr = await asyncio.wait_for(child.communicate(), 5)
                    self.assertEqual(child.returncode, 0, stderr)
                    self.assertFalse((root / "mesh.sock").exists())
                finally:
                    if client is not None:
                        await client.close()
                    if child.returncode is None:
                        child.kill()
                        await child.wait()

    async def test_default_omitted_domain_and_authority_fast_path(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = config(root, "agent")
            adapter = object()
            with patch("mesh_plus.observer.ObserverAdapter", return_value=adapter) as reference:
                self.assertIs(configured_adapter(path, "default", publisher_factories={"tmux": factory("tmux")}), adapter)
                reference.assert_called_once_with("agent", "local", "default", "/unused")
            # The authority branch must not import protocol/state/publisher or invoke factory code.
            with patch.object(sys, "argv", ["mesh-plus", "mesh", "list", "--json"]), \
                 patch("mesh_plus.authority_cli.main", return_value=0) as authority, \
                 patch("mesh_plus.cli.publisher_factory_map", side_effect=AssertionError("state imported")):
                from mesh_plus.cli import main
                self.assertEqual(main(publisher_factories={"tmux": None}), 0)
                authority.assert_called_once_with(["list", "--json"])


class PublisherConformanceTests(unittest.TestCase):
    def test_public_helper_passes_portable_profile_and_network_oracles(self):
        from publisher_fixture import KitPublisher

        from mesh_plus.testing import network_suite, profile_suite, run_suite

        for domain in ("tmux", "agent"):
            for suite in (profile_suite(Profile, domain=domain),
                          network_suite(Profile, domain=domain, publisher_factory=KitPublisher)):
                report = run_suite(suite, domain=domain)
                self.assertTrue(report["ok"], report)
