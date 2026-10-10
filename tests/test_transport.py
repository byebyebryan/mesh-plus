import asyncio
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from test_protocol import example

from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import IPCServer, LineChannel, connect_ipc, subprocess_channel


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_reached_marker_split_removed_and_duplicate_revokes(self):
        channel = LineChannel(None, None, "server", reached_nonce="a" * 32)
        marker = ("\x1eROFI_PLUS_REACHED_V1:" + "a" * 32 + "\x1f\n").encode()
        wrong = marker.replace(b"aaa", b"bbb", 1)
        channel._stderr_block(b"diagnostic" + wrong + marker[:11])
        self.assertFalse(channel.reached)
        channel._stderr_block(marker[11:] + b"after" * 20)
        self.assertTrue(channel.reached)
        observed = channel.reached_observed_at
        self.assertIsInstance(observed, int)
        self.assertNotIn(marker, channel.stderr_tail)
        self.assertIn(wrong, channel.stderr_tail)
        channel._stderr_block(marker)
        self.assertFalse(channel.reached)
        self.assertEqual(channel.reached_count, 2)
        self.assertEqual(channel.reached_observed_at, observed)

    async def test_duplex_ipc_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            completed = asyncio.Event()

            async def handler(channel):
                frame, _ = await channel.receive()
                self.assertEqual(frame["kind"], "hello")
                await channel.send(example("server-hello"))
                completed.set()

            server = await IPCServer(path, handler).start()
            try:
                client = await connect_ipc(path)
                try:
                    await client.send(example("client-hello"))
                    frame, _ = await client.receive()
                    self.assertEqual(frame["kind"], "hello")
                    await asyncio.wait_for(completed.wait(), 1)
                finally:
                    await client.close()
            finally:
                await server.close()
            self.assertFalse(path.exists())
            self.assertFalse(server.tasks)

    async def test_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            path.write_text("preserve")
            server = IPCServer(path, None)
            with self.assertRaisesRegex(ProtocolError, "ipc_path_exists"):
                await server.start()
            self.assertEqual(path.read_text(), "preserve")

    async def test_public_directory_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o755)
            with self.assertRaisesRegex(ProtocolError, "ipc_directory_policy"):
                await IPCServer(Path(directory) / "mesh.sock", None).start()

    async def test_abandoned_owned_socket_recovers_but_duplicate_lease_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as abandoned:
                abandoned.bind(str(path))
                path.chmod(0o600)
            server = await IPCServer(path, None).start()
            duplicate = IPCServer(path, None)
            try:
                with self.assertRaisesRegex(ProtocolError, "ipc_publisher_running"):
                    await duplicate.start()
                self.assertIsNone(duplicate.lease)
                self.assertTrue(path.is_socket())
            finally:
                await server.close()
            self.assertIsNone(server.lease)

    async def test_repeated_close_preserves_new_publisher(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            old = await IPCServer(path, None).start()
            await old.close()
            new = await IPCServer(path, None).start()
            try:
                await old.close()
                self.assertTrue(path.is_socket())
            finally:
                await new.close()

    async def test_owned_child_close_drains_paused_stdout(self):
        program = "import os,time\nfor _ in range(400): os.write(1,b'x'*65536)\ntime.sleep(30)"
        channel = await subprocess_channel([sys.executable, "-c", program])
        await asyncio.sleep(.1)
        await asyncio.wait_for(channel.close(), 3)
        self.assertIsNotNone(channel.process.returncode)

    async def test_channel_close_wakes_idle_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            async def idle(channel):
                await asyncio.Event().wait()
            server = await IPCServer(path, idle).start()
            channel = await connect_ipc(path)
            pending = asyncio.create_task(channel.receive())
            try:
                await asyncio.sleep(.01)
                await channel.close()
                with self.assertRaises(EOFError):
                    await asyncio.wait_for(pending, .1)
            finally:
                await server.close()
