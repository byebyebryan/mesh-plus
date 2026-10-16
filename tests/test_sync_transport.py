import json
import tempfile
import unittest
from pathlib import Path

from mesh_plus.protocol import ProtocolError, check
from mesh_plus.sync.canonical import canonical, decode
from mesh_plus.transport import IPCServer, connect_ipc, ssh_argv


class ProbeCodec:
    """A distinct opt-in codec; no use of Delivery 1 validation/fallback."""

    def encode(self, value):
        return canonical(value)

    def validate(self, value, direction, size, maximum):
        check(type(value) is dict and set(value) == {"protocol", "kind", "value"} and
              value["protocol"] == "sync-probe/1" and value["kind"] == "probe", "probe_protocol")
        check(type(value["value"]) is int and size <= maximum, "probe_capacity")

    def decode(self, raw, direction, maximum):
        value = decode(raw, maximum)
        self.validate(value, direction, len(raw), maximum)
        return value


class CodecTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_codec_uses_owned_ipc_and_existing_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sync.sock"
            codec = ProbeCodec()

            async def serve(channel):
                value, _ = await channel.receive()
                await channel.send({**value, "value": value["value"] + 1})

            server = await IPCServer(path, serve, codec=codec).start()
            channel = await connect_ipc(path, codec=codec)
            try:
                await channel.send({"protocol": "sync-probe/1", "kind": "probe", "value": 1})
                result, size = await channel.receive()
                self.assertEqual(result["value"], 2)
                self.assertEqual(size, len(canonical(result)))
                self.assertEqual(channel.inspect()["receivedFrames"], 1)
                self.assertEqual(channel.inspect()["byKind"]["received"]["probe"]["frames"], 1)
            finally:
                await channel.close()
                await server.close()
            self.assertFalse(path.exists())

    async def test_legacy_shape_is_rejected_without_codec_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sync.sock"

            async def serve(channel):
                await channel.receive()
                self.fail("legacy delivery reached the new codec handler")

            server = await IPCServer(path, serve, codec=ProbeCodec()).start()
            channel = await connect_ipc(path, codec=ProbeCodec())
            try:
                # Test-owned raw sender bypasses its own codec, so the server
                # actually exercises the receiving boundary and closes it.
                channel.writer.write(json.dumps({"kind": "hello", "protocol": "mesh.delivery/1"}).encode() + b"\n")
                await channel.writer.drain()
                with self.assertRaises(EOFError):
                    await channel.receive()
            finally:
                await channel.close()
                await server.close()


class FixedSyncSSHTests(unittest.TestCase):
    def test_sync_selects_only_fixed_new_command_and_preserves_ssh_policy(self):
        old = ssh_argv("host", "agents")
        new = ssh_argv("host", "agents", sync=True)
        self.assertEqual(old[:-1], new[:-1])
        self.assertEqual(new[-1], "mesh-plus sync-bridge --source agents --stdio")
        self.assertEqual(old[-1], "mesh-plus bridge --source agents --stdio")
        with self.assertRaisesRegex(ProtocolError, "bridge_command"):
            ssh_argv("host", "agents", sync="yes")


if __name__ == "__main__":
    unittest.main()
