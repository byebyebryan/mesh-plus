import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from test_protocol import example

from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import IPCServer, connect_ipc


class TransportTests(unittest.IsolatedAsyncioTestCase):
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
