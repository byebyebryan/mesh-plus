import asyncio
import fcntl
import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mesh_plus.authority import route_health_path
from mesh_plus.authority_cli import main
from mesh_plus.library_authority import LibraryMeshAuthority
from mesh_plus.protocol import ProtocolError


class LibraryAuthorityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = {"XDG_CONFIG_HOME": str(self.root / "config"),
                            "XDG_STATE_HOME": str(self.root / "state")}
        self.environment_patch = patch.dict(os.environ, self.environment)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.addCleanup(self.temporary.cleanup)
        self.config = self.root / "config/rofi-ssh-plus/config.toml"
        self.config.parent.mkdir(parents=True)
        self.config.write_text('schema_version = 1\nlocal_id = "snap"\n'
                               '[[hosts]]\nid = "starship"\nroutes = ["starship"]\n')

    async def asyncSetUp(self):
        self.loop_errors = []
        loop = asyncio.get_running_loop()
        original = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, error: self.loop_errors.append(error))
        self.addCleanup(loop.set_exception_handler, original)

    async def asyncTearDown(self):
        await asyncio.sleep(.01)
        self.assertEqual(self.loop_errors, [])

    def authority(self, **kwargs):
        value = LibraryMeshAuthority(**kwargs)
        self.addCleanup(value.close)
        return value

    async def test_same_native_config_health_and_revision_as_public_cli(self):
        authority = self.authority()
        with patch("mesh_plus.catalog.bounded_command", side_effect=AssertionError("unexpected process")):
            first = await authority.load()
            stream = io.StringIO()
            self.assertEqual(main(["list", "--json"], stdout=stream), 0)
            expected = json.loads(stream.getvalue())
            actual = first.payload.copy()
            expected.pop("generatedAt")
            actual.pop("generatedAt")
            self.assertEqual(actual, expected)
            self.config.write_text(self.config.read_text().replace('id = "starship"', 'id = "other"'))
            self.assertNotEqual((await authority.load()).revision, first.revision)
            self.config.write_text("invalid = true\n")
            with self.assertRaises(ValueError):
                await authority.load()

    async def test_special_source_and_capacity_do_not_block_or_synthesize_fallback(self):
        authority = self.authority()
        self.config.unlink()
        os.mkfifo(self.config)
        with self.assertRaisesRegex(ProtocolError, "catalog_source_policy"):
            await authority.load()
        self.config.unlink()
        self.config.write_bytes(b" " * (4 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ProtocolError, "catalog_source_capacity"):
            await authority.load()

    async def test_health_lock_deadline_reaps_job_and_keeps_event_loop_responsive(self):
        authority = self.authority(timeout_ms=150)
        health = route_health_path(self.environment)
        health.parent.mkdir(parents=True)
        descriptor = os.open(health.with_name("." + health.name + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            operation = asyncio.create_task(authority.load())
            started = time.monotonic()
            ticks = 0
            while not operation.done():
                ticks += 1
                await asyncio.sleep(.01)
            with self.assertRaises((TimeoutError, ProtocolError)):
                await operation
            self.assertGreater(ticks, 3)
            self.assertLess(time.monotonic() - started, .7)
            authority.thread.join(timeout=1)
            self.assertFalse(authority.thread.is_alive())
        finally:
            os.close(descriptor)
        self.assertEqual((await authority.load()).local_host, "snap")

    async def test_cancelled_read_has_one_job_no_queued_replacement_or_late_result(self):
        authority = self.authority()
        entered, release = threading.Event(), threading.Event()
        original = authority._read
        def blocked(*args):
            entered.set()
            release.wait(2)
            return original(*args)
        with patch.object(authority, "_read", side_effect=blocked):
            operation = asyncio.create_task(authority.load())
            while not entered.is_set():
                await asyncio.sleep(.01)
            operation.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await operation
            with self.assertRaisesRegex(ProtocolError, "catalog_busy"):
                await authority.load()
            with self.assertRaisesRegex(ProtocolError, "catalog_busy"):
                authority.close(timeout=0)
            release.set()
            authority.thread.join(timeout=1)
            self.assertFalse(authority.thread.is_alive())
            with self.assertRaisesRegex(ProtocolError, "catalog_closed"):
                await authority.load()
            await asyncio.sleep(.01)
