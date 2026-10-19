import asyncio
import contextlib
import json
import os
import signal
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

from test_protocol import example

from mesh_plus.client import Client
from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import IPCServer, LineChannel, connect_ipc, finish_owned, subprocess_channel

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"

_BRIDGE_CHILD = r"""
import asyncio
import gc
import sys
sys.path.insert(0, sys.argv[1])
gc.disable()
from mesh_plus.bridge import Bridge
from mesh_plus.protocol import MAX_MESSAGE, check
from mesh_plus.transport import LineChannel

class Source:
    host = "fixture-host"
    source = "synthetic"
    profile = "mesh-plus.synthetic.state.v1"
    capabilities = ("snapshot",)
    def validate(self, value):
        check(type(value) is dict and type(value.get("value")) is int, "fixture_payload")
    async def snapshot(self, parameters):
        return {"value": 7}

async def pipe_channel():
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_MESSAGE + 1)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer)
    protocol = asyncio.streams.FlowControlMixin(loop=loop)
    transport, protocol = await loop.connect_write_pipe(lambda: protocol, sys.stdout.buffer)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return LineChannel(reader, writer, "client")

async def main():
    await Bridge(Source()).serve(await pipe_channel())

asyncio.run(main())
"""

_DELAYED_RELAY = r"""
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time

gc.disable()
source_root, receipt_path, bridge_code = sys.argv[1:]
child = subprocess.Popen([sys.executable, "-I", "-B", "-c", bridge_code, source_root],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        bufsize=0, close_fds=True)
close_observed = None

def terminate_relay(signum, _frame):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, terminate_relay)
try:
    for line in sys.stdin.buffer:
        frame = json.loads(line)
        if frame.get("kind") == "close":
            close_observed = {"kind": frame["kind"], "reason": frame["reason"],
                              "lineBytes": len(line), "lineSha256": hashlib.sha256(line).hexdigest()}
            time.sleep(.05)
        child.stdin.write(line)
        child.stdin.flush()
        if frame.get("kind") in {"hello", "request"}:
            response = child.stdout.readline()
            if not response:
                break
            sys.stdout.buffer.write(response)
            sys.stdout.buffer.flush()
finally:
    try:
        child.stdin.close()
    except Exception:
        pass
    try:
        bridge_returncode = child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        child.kill()
        bridge_returncode = child.wait(timeout=1)
    report = {"closeForwarded": close_observed, "bridgeReturncode": bridge_returncode,
              "bridgePid": child.pid, "bridgeReaped": child.returncode is not None}
    target = Path(receipt_path)
    temporary = target.with_name(target.name + ".tmp." + str(os.getpid()))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(report, output, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.link(temporary, target)
    temporary.unlink()
"""


async def _retire_test_channel(channel, client=None, close_task=None):
    if channel is None:
        return
    if close_task is None:
        operation = client.close() if client is not None else channel.close()
        close_task = asyncio.create_task(operation)
    try:
        await asyncio.wait_for(asyncio.shield(close_task), 4)
    except TimeoutError:
        pass
    finally:
        process = channel.process
        if process is not None and process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await asyncio.wait_for(process.wait(), 1)
        await finish_owned(close_task)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_cancellation_retires_owned_io_before_propagating(self):
        released = asyncio.Event()
        finished = asyncio.Event()
        async def io():
            await released.wait()
            finished.set()
        operation = asyncio.create_task(io())
        owner = asyncio.create_task(finish_owned(operation))
        await asyncio.sleep(0)
        for _ in range(3):
            owner.cancel()
            await asyncio.sleep(0)
            self.assertFalse(operation.done())
            self.assertFalse(owner.done())
        released.set()
        with self.assertRaises(asyncio.CancelledError):
            await owner
        self.assertTrue(finished.is_set())
        self.assertFalse(operation.cancelled())

    async def test_cancelled_owner_observes_late_io_failure_without_background_log(self):
        loop = asyncio.get_running_loop()
        errors = []
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, context: errors.append(context))
        released = asyncio.Event()
        async def io():
            await released.wait()
            raise ConnectionResetError("owned fixture reset")
        try:
            operation = asyncio.create_task(io())
            owner = asyncio.create_task(finish_owned(operation))
            await asyncio.sleep(0)
            owner.cancel()
            await asyncio.sleep(0)
            released.set()
            with self.assertRaises(ConnectionResetError):
                await owner
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            self.assertTrue(operation.done())
            self.assertEqual(errors, [])
        finally:
            loop.set_exception_handler(previous)

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

    async def test_client_close_reaches_bridge_after_delayed_forward_and_exits_normally(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "close-receipt.json"
            channel = client = close_task = None
            try:
                channel = await subprocess_channel([
                    sys.executable, "-I", "-B", "-c", _DELAYED_RELAY,
                    str(SOURCE_ROOT), str(receipt), _BRIDGE_CHILD,
                ])
                client = await Client.connect(channel, host="fixture-host", source="synthetic",
                                              profile="mesh-plus.synthetic.state.v1",
                                              codec=lambda value: self.assertEqual(value, {"value": 7}),
                                              required=("snapshot",))
                self.assertEqual(await client.request(timeout_ms=2000), {"value": 7})
                close_task = asyncio.create_task(client.close())
                await asyncio.wait_for(asyncio.shield(close_task), 2)

                report = json.loads(receipt.read_text())
                self.assertEqual(channel.process.returncode, 0,
                                 f"wrapperReturnCode={channel.process.returncode}, "
                                 f"bridgeReturncode={report['bridgeReturncode']}, "
                                 f"closeForwarded={report['closeForwarded'] is not None}, "
                                 f"bridgeReaped={report['bridgeReaped']}")
                self.assertEqual(report["closeForwarded"]["kind"], "close")
                self.assertEqual(report["closeForwarded"]["reason"], "client_done")
                self.assertGreater(report["closeForwarded"]["lineBytes"], 0)
                self.assertEqual(report["bridgeReturncode"], 0)
                self.assertIsInstance(report["bridgePid"], int)
            finally:
                await _retire_test_channel(channel, client, close_task)
                if channel is not None:
                    self.assertTrue(receipt.is_file())
                    report = json.loads(receipt.read_text())
                    self.assertIsInstance(report["bridgeReturncode"], int)
                    self.assertIsInstance(report["bridgePid"], int)
                    self.assertTrue(report["bridgeReaped"])

    async def test_owned_child_ignoring_term_is_killed_and_reaped_within_close_bounds(self):
        program = (
            "import os,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "os.write(1,b'ready\\n'); "
            "time.sleep(30)"
        )
        channel = close_task = None
        try:
            channel = await subprocess_channel([sys.executable, "-c", program])
            self.assertEqual(await asyncio.wait_for(channel.reader.readline(), 1), b"ready\n")
            started = time.monotonic()
            close_task = asyncio.create_task(channel.close())
            await asyncio.wait_for(asyncio.shield(close_task), 3)
            elapsed = time.monotonic() - started
            self.assertEqual(channel.process.returncode, -signal.SIGKILL)
            self.assertLess(elapsed, 2.4)
        finally:
            await _retire_test_channel(channel, close_task=close_task)
            if channel is not None:
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
