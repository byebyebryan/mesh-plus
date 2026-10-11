"""Real loopback TLS tests. No external host, source collector or deployment."""

import asyncio
import json
import socket
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from carrier import Listener, connect, endpoint_url, pause_until
from configuration import (
    BINDING,
    Selection,
    ServerConfiguration,
    StudyReader,
    policy_file,
    resolve,
    snapshot,
    tls_context,
)
from fixtures import BroadcastPublisher, certificates, contexts, fingerprint, write_policy
from websockets.asyncio.client import connect as peer_connect

from mesh_plus.api import Client, Endpoint, ReferenceProfile
from mesh_plus.bridge import Bridge
from mesh_plus.catalog import Catalog
from mesh_plus.evidence import digest
from mesh_plus.protocol import MAX_CONTROL, MAX_MESSAGE, PROTOCOL, ProtocolError, encode
from mesh_plus.transport import boottime_ms


class WSSCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mesh-wss-")
        self.root = Path(self.temp.name)
        await asyncio.to_thread(certificates, self.root)
        self.server_context, self.client_context = contexts(self.root)
        self.publisher = BroadcastPublisher("tmux")
        self.policy = {fingerprint(self.root): ["beta", "default", self.publisher.profile]}
        self.policy_path = self.root / "policy.json"
        write_policy(self.policy_path, self.policy)
        self.server_configuration = ServerConfiguration.load(self.root / "ca.pem", self.root / "server.pem",
                                                             self.root / "server.key", self.policy_path)
        self.listener = await Listener(self.server_context, Bridge(self.publisher).serve,
                                       self.server_configuration.authorize, self.policy[fingerprint(self.root)],
                                       policy_interval=.05).start()
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        await self.listener.close()
        self.assertFalse(self.listener.tasks)
        self.assertFalse(self.listener.channels)
        self.assertEqual(self.listener.unexpected, 0)
        self.assertEqual(self.publisher.watchers, 0)
        self.temp.cleanup()

    async def client(self, **kwargs):
        client = await Client.connect(await connect(self.listener.url, self.client_context),
                                      host=kwargs.get("host", "beta"), source=kwargs.get("source", "default"),
                                      profile=kwargs.get("profile", self.publisher.profile),
                                      codec=self.publisher.validate)
        self.clients.append(client)
        return client

    async def test_snapshot_proof_subscribe_and_independent_cancel(self):
        client = await self.client()
        sub = await client.subscribe()
        baseline = await asyncio.wait_for(anext(sub), 2)
        self.assertEqual(baseline["kind"], "data")
        proof = await client.request("proof", {"nonce": "a" * 32})
        self.assertEqual(proof["nonce"], "a" * 32)
        self.publisher.update()
        changed = await asyncio.wait_for(anext(sub), 2)
        self.assertEqual(changed["payload"]["ownerFrame"]["viewRevision"], self.publisher.frame["viewRevision"])
        await sub.close()
        self.assertEqual((await client.request())["hostId"], "beta")
        self.assertEqual(client.channel.inspect()["byteScope"], "completed-json-messages")

    async def test_wrong_binding_rejected_before_publisher_request(self):
        for argument in ({"host": "gamma"}, {"source": "other"}, {"profile": "agent-observer.mesh-candidate.v1"}):
            with self.subTest(argument=argument), self.assertRaises(Exception):
                await self.client(**argument)
        self.assertEqual(self.publisher.sequence, 0)

    async def test_untrusted_missing_expired_and_unknown_client(self):
        for name in ("unknown", "expired"):
            _, context = contexts(self.root, name)
            with self.subTest(name=name), self.assertRaises(Exception):
                await connect(self.listener.url, context)
        context = ssl.create_default_context(cafile=str(self.root / "ca.pem"))
        with self.assertRaises(Exception):
            await connect(self.listener.url, context)
        other = self.root / "untrusted"
        other.mkdir(mode=0o700)
        await asyncio.to_thread(certificates, other)
        # Trust the RIGHT server, but offer an allowlisted cert from the WRONG CA.
        # This isolates TLS client trust from fingerprint allowlist rejection.
        context = tls_context(self.root / "ca.pem", other / "client.pem", other / "client.key")
        self.policy[fingerprint(other)] = ["beta", "default", self.publisher.profile]
        write_policy(self.policy_path, self.policy)
        with self.assertRaises(Exception):
            await connect(self.listener.url, context)
        self.assertEqual(self.listener.dispatched, 0)

    async def test_server_trust_and_hostname(self):
        with self.assertRaises(Exception):
            await connect(self.listener.url, ssl.create_default_context())
        with self.assertRaises(Exception):
            await connect(self.listener.url, self.client_context, server_hostname="wrong.invalid")
        self.assertEqual(self.listener.dispatched, 0)

    async def test_origin_path_and_subprotocol(self):
        for options in ({"origin": "https://browser.invalid"}, {"subprotocols": ["other"]}):
            with self.subTest(options=options), self.assertRaises(Exception):
                async with peer_connect(self.listener.url, ssl=self.client_context, proxy=None,
                                        compression=None, **options):
                    pass
        with self.assertRaises(ProtocolError):
            endpoint_url(self.listener.url + "?token=secret")
        with self.assertRaises(Exception):
            async with peer_connect(self.listener.url.replace("/mesh/state", "/wrong"), ssl=self.client_context,
                                    proxy=None, compression=None, subprotocols=[PROTOCOL]):
                pass
        self.assertEqual(self.listener.dispatched, 0)

    async def test_rotation_overlap_removal_and_policy_failure(self):
        first = await self.client()
        rotated = fingerprint(self.root, "rotation")
        self.policy[rotated] = self.policy[fingerprint(self.root)]
        write_policy(self.policy_path, self.policy)
        # Any changed policy revokes previous active connections, requiring fresh admission.
        await asyncio.wait_for(first.reader_task, 2)
        _, second_context = contexts(self.root, "rotation")
        channel = await connect(self.listener.url, second_context)
        second = await Client.connect(channel, host="beta", source="default", profile=self.publisher.profile,
                                      codec=self.publisher.validate)
        self.clients.append(second)
        del self.policy[fingerprint(self.root)]
        write_policy(self.policy_path, self.policy)
        await asyncio.wait_for(second.reader_task, 2)
        third = await Client.connect(await connect(self.listener.url, second_context), host="beta", source="default",
                                     profile=self.publisher.profile, codec=self.publisher.validate)
        self.clients.append(third)
        self.policy_path.write_text("{")
        await asyncio.wait_for(third.reader_task, 2)
        self.assertTrue(third.channel.closed)

    async def test_active_certificate_expiry_wallclock(self):
        client = await self.client()
        with patch("carrier.time.time", return_value=4102444800):
            await asyncio.wait_for(client.reader_task, 2)
        self.assertTrue(client.channel.closed)

    async def test_active_listener_credentials_replacement_revokes(self):
        for name in ("ca.pem", "server.pem", "server.key"):
            original = (self.root / name).read_bytes()
            try:
                client = await self.client()
                (self.root / name).write_bytes(b"replacement")
                await asyncio.wait_for(client.reader_task, 2)
                self.assertTrue(client.channel.closed)
            finally:
                (self.root / name).write_bytes(original)

    async def test_owned_capture_path_replacement_and_private_policy(self):
        captured = tuple(snapshot(self.root / p) for p in ("ca.pem", "client.pem", "client.key"))
        (self.root / "client.key").write_text("replaced")
        context = tls_context(None, None, None, captured=captured)
        channel = await connect(self.listener.url, context)
        await channel.close()
        self.policy_path.chmod(0o644)
        with self.assertRaises(ProtocolError):
            await policy_file(self.policy_path)
        self.policy_path.chmod(0o600)
        (self.root / "link").symlink_to(self.policy_path)
        with self.assertRaises(OSError):
            snapshot(self.root / "link")

    async def test_composed_selection_monitors_catalog_registry_trust_credentials(self):
        from importlib.resources import files
        catalog = self.root / "catalog.json"
        catalog.write_text(files("mesh_plus.testing").joinpath("catalog.json").read_text())
        catalog.chmod(0o600)
        registry = self.root / "registry.json"
        registry.write_text(json.dumps({"protocol": BINDING, "endpoints": [{"hostId": "beta", "sourceId": "default",
            "profile": self.publisher.profile, "url": self.listener.url, "product": "state",
            "capabilities": ["snapshot", "proof", "subscribe"]}]}))
        registry.chmod(0o600)
        paths = (catalog, registry, self.root / "ca.pem", self.root / "client.pem", self.root / "client.key")
        selection = Selection.load(*paths)
        original_revision = selection.bindings[0].selection_revision
        self.assertEqual(await selection.check(), original_revision)
        for path in paths:
            original = path.read_bytes()
            try:
                if path == catalog:
                    data = json.loads(original)
                    data["meshRevision"] = "sha256:" + "a" * 64
                    path.write_text(json.dumps(data))
                    self.assertNotEqual(await selection.check(), original_revision)
                elif path == registry:
                    data = json.loads(original)
                    data["endpoints"][0]["sourceId"] = "other"
                    path.write_text(json.dumps(data))
                    self.assertNotEqual(await selection.check(), original_revision)
                else:
                    path.write_bytes(b"malformed")
                    with self.assertRaises(Exception):
                        await selection.check()
            finally:
                path.write_bytes(original)

    async def test_fragment_stall_binary_strict_json_and_empty_fragments(self):
        samples = ['{"kind":"hello","kind":"hello"}', '{"x":NaN}', '{} {}', b'\xff',
                   '[' * 70 + '0' + ']' * 70, '[' + ','.join('0' for _ in range(100001)) + ']']
        async def fragments():
            yield "{"
            await asyncio.sleep(3)
            yield "}"
        async def excessive():
            for _ in range(257):
                yield ""
        for payload in (*samples, fragments(), excessive()):
            with self.subTest(payload=type(payload).__name__):
                async with peer_connect(self.listener.url, ssl=self.client_context, proxy=None, compression=None,
                                        subprotocols=[PROTOCOL], close_timeout=.2) as peer:
                    sender = asyncio.create_task(peer.send(payload))
                    await asyncio.wait_for(peer.wait_closed(), 4)
                    sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
        self.assertEqual(self.publisher.sequence, 0)

    async def test_receive_cancel_safe_and_repeated_close_owned(self):
        channel = await connect(self.listener.url, self.client_context)
        pending = asyncio.create_task(channel.receive())
        await asyncio.sleep(.02)
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        self.assertFalse(channel.receiving)
        jobs = [asyncio.create_task(channel.close()) for _ in range(5)]
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        await channel.close()
        self.assertTrue(channel.pump.done())

    async def test_fragmented_valid_hello_and_control_capacity(self):
        root = Path(__file__).resolve().parents[2]
        hello = json.loads((root / "contracts/mesh-delivery-v1/examples/client-hello.json").read_text())
        hello.update(expectedHost="beta", sourceId="default", profile=self.publisher.profile)
        raw = encode(hello).decode()
        async with peer_connect(self.listener.url, ssl=self.client_context, proxy=None, compression=None,
                                subprotocols=[PROTOCOL]) as peer:
            await peer.send([raw[:9], raw[9:]])
            received = json.loads(await peer.recv())
            self.assertEqual(received["kind"], "hello")
            request = {"protocol": PROTOCOL, "version": 1, "sequence": 2, "kind": "request",
                       "channelId": received["channelId"], "requestId": "boundary", "operation": "snapshot",
                       "timeoutMs": 2000, "parameters": {"padding": ""}}
            request["parameters"]["padding"] = "x" * (MAX_CONTROL - len(encode(request)))
            exact = encode(request)
            self.assertEqual(len(exact), MAX_CONTROL)
            await peer.send(exact.decode())
            response = json.loads(await peer.recv())
            self.assertEqual(response["kind"], "result")
            self.assertEqual(response["outcome"], "ok")
        async with peer_connect(self.listener.url, ssl=self.client_context, proxy=None, compression=None,
                                subprotocols=[PROTOCOL], close_timeout=.2) as peer:
            await peer.send(" " * (MAX_CONTROL + 1))
            await asyncio.wait_for(peer.wait_closed(), 2)

    async def test_utf8_exact_negotiated_ceiling_and_large_fragments(self):
        # Transport-only server values; native acceptance is a separate gate.
        result = {"protocol": PROTOCOL, "version": 1, "sequence": 1, "kind": "result",
                  "channelId": "00000000-0000-0000-0000-000000000000", "requestId": "test",
                  "outcome": "ok", "payload": {"text": ""}, "error": None}
        overhead = len(encode(result))
        result["payload"]["text"] = "ü" * ((MAX_MESSAGE - overhead) // 2)
        raw = encode(result)
        self.assertEqual(len(raw), MAX_MESSAGE - ((MAX_MESSAGE - overhead) % 2))
        async def output(channel):
            async with channel.lock:
                channel.protocol.send_text(raw[:65536], fin=False)
                for offset in range(65536, len(raw), 65536):
                    end = min(len(raw), offset + 65536)
                    channel.protocol.send_continuation(raw[offset:end], fin=end == len(raw))
                    await channel._flush()
            await channel.receive()
        await self.listener.close()
        self.listener = await Listener(self.server_context, output, lambda: policy_file(self.policy_path),
                                       self.policy[fingerprint(self.root)]).start()
        channel = await connect(self.listener.url, self.client_context)
        try:
            value, size = await asyncio.wait_for(channel.receive(), 4)
            self.assertEqual(size, len(raw))
            self.assertEqual(value, result)
            self.assertGreater(channel.inspect()["peakFragments"], 1)
            channel.maximum = size - 1
            with self.assertRaises(ProtocolError):
                # Negotiated direction uses the same UTF-8 byte parser ceiling.
                from mesh_plus.protocol import decode
                decode(raw, "server", channel.maximum)
        finally:
            await channel.close()

    async def test_pre_tls_admission_and_cleanup(self):
        sockets = []
        try:
            for _ in range(8):
                sock = socket.socket()
                sock.setblocking(False)
                await asyncio.wait_for(asyncio.get_running_loop().sock_connect(sock, ("127.0.0.1", self.listener.port)), 1)
                sockets.append(sock)
            await asyncio.sleep(.1)
            self.assertEqual(self.listener.peak_admitted, 4)
            self.assertEqual(len(self.listener.tasks), 4)
            self.assertEqual(self.listener.dispatched, 0)
        finally:
            for sock in sockets:
                sock.close()

    async def test_redirect_is_rejected_without_second_destination(self):
        calls = 0
        async def redirect(reader, writer):
            nonlocal calls
            calls += 1
            try:
                await reader.readuntil(b"\r\n\r\n")
                writer.write(("HTTP/1.1 302 Found\r\nLocation: " + self.listener.url +
                              "\r\nContent-Length: 0\r\n\r\n").encode())
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        server = await asyncio.start_server(redirect, "127.0.0.1", 0, ssl=self.server_context)
        try:
            port = server.sockets[0].getsockname()[1]
            with self.assertRaises(Exception):
                await connect(f"wss://localhost:{port}/mesh/state", self.client_context)
            self.assertEqual(calls, 1)
            self.assertEqual(self.listener.dispatched, 0)
        finally:
            server.close()
            await server.wait_closed()

    async def test_complete_message_queue_overload_closes_without_unbounded_retention(self):
        admitted = []
        async def slow(channel):
            admitted.append(channel)
            await channel.pump
        await self.listener.close()
        self.listener = await Listener(self.server_context, slow, self.server_configuration.authorize,
                                       self.policy[fingerprint(self.root)]).start()
        root = Path(__file__).resolve().parents[2]
        raw = (root / "contracts/mesh-delivery-v1/examples/client-hello.json").read_text()
        async with peer_connect(self.listener.url, ssl=self.client_context, proxy=None, compression=None,
                                subprotocols=[PROTOCOL], close_timeout=.2) as peer:
            for _ in range(4):
                await peer.send(raw)
            await asyncio.wait_for(peer.wait_closed(), 4)
        self.assertEqual(admitted[0].inspect()["peakQueueFrames"], 2)
        await asyncio.wait_for(admitted[0].pump, 2)
        self.assertTrue(admitted[0].pump.done())

    async def test_repeated_send_cancellation_retires_owned_channel(self):
        client = await self.client()
        entered = asyncio.Event()
        async def stalled():
            entered.set()
            await asyncio.Event().wait()
        with patch.object(client.channel.writer, "drain", stalled):
            request = asyncio.create_task(client.request())
            await asyncio.wait_for(entered.wait(), 1)
            for _ in range(5):
                request.cancel()
                await asyncio.sleep(0)
            await asyncio.gather(request, return_exceptions=True)
        await client.channel.close()
        self.assertTrue(client.channel.closed)
        self.assertTrue(client.channel.pump.done())
        self.assertTrue(client.channel.retirement.done())

    async def test_repeated_setup_cancellation_closes_tls_writer(self):
        admitted = asyncio.Event()
        retired = asyncio.Event()
        async def stall(reader, writer):
            try:
                await reader.readuntil(b"\r\n\r\n")
                admitted.set()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                retired.set()
        server = await asyncio.start_server(stall, "127.0.0.1", 0, ssl=self.server_context)
        try:
            port = server.sockets[0].getsockname()[1]
            opening = asyncio.create_task(connect(f"wss://localhost:{port}/mesh/state", self.client_context))
            await asyncio.wait_for(admitted.wait(), 2)
            for _ in range(5):
                opening.cancel()
                await asyncio.sleep(0)
            await asyncio.gather(opening, return_exceptions=True)
            await asyncio.wait_for(retired.wait(), 2)
        finally:
            server.close()
            await server.wait_closed()

    async def test_graceful_websocket_close_and_late_validation_rejection(self):
        import time

        from carrier import decode as strict_decode
        async with peer_connect(self.listener.url, ssl=self.client_context, proxy=None, compression=None,
                                subprotocols=[PROTOCOL]) as peer:
            channel = next(iter(self.listener.channels))
            await channel.close()
            await asyncio.wait_for(peer.wait_closed(), 2)
            self.assertEqual(peer.close_code, 1000)
        channel = await connect(self.listener.url, self.client_context)
        channel.assembly_timeout = .01
        def late(raw, direction, maximum):
            time.sleep(.025)
            return strict_decode(raw, direction, maximum)
        with patch("carrier.decode", late), self.assertRaises(ProtocolError):
            await Client.connect(channel, host="beta", source="default", profile=self.publisher.profile,
                                 codec=self.publisher.validate)
        self.assertTrue(channel.pump.done())

    async def test_partial_header_deadline_and_boottime_resume_tick(self):
        original = self.listener.handler
        async def fast(channel):
            channel.assembly_timeout = .05
            await original(channel)
        self.listener.handler = fast
        channel = await connect(self.listener.url, self.client_context)
        try:
            channel.writer.write(b"\x81")
            await channel.writer.drain()
            await asyncio.wait_for(channel.pump, 1)
            self.assertTrue(channel.closed)
        finally:
            await channel.close()
        now = boottime_ms()
        sleeper = asyncio.create_task(pause_until(now + 5000))
        await asyncio.sleep(.02)
        with patch("carrier.boottime_ms", return_value=now + 10000):
            await asyncio.wait_for(sleeper, .3)


class BindingCase(unittest.IsolatedAsyncioTestCase):
    def registry(self, url="wss://localhost:443/mesh/state"):
        return {"protocol": BINDING, "endpoints": [{"hostId": "beta", "sourceId": "default",
                "profile": "tmux-observer.mesh-candidate.v1", "url": url, "product": "state",
                "capabilities": ["snapshot", "proof", "subscribe"]}]}

    def catalog(self):
        from importlib.resources import files
        return Catalog(json.loads(files("mesh_plus.testing").joinpath("catalog.json").read_text()))

    async def test_immutable_revision_token_binding_and_invalid_registry(self):
        registry = self.registry()
        first = resolve(self.catalog(), registry, digest({"trust": 1}))[0]
        second = resolve(self.catalog(), registry, digest({"trust": 2}))[0]
        self.assertNotEqual(first.token, second.token)
        registry["endpoints"][0]["sourceId"] = "other"
        self.assertEqual(first.source, "default")
        for field, value in (("hostId", "beta-native"), ("sourceId", "../file"), ("product", "events"),
                             ("capabilities", ["actions"]), ("url", "wss://u:p@localhost/mesh/state")):
            bad = self.registry()
            bad["endpoints"][0][field] = value
            with self.subTest(field=field), self.assertRaises(Exception):
                resolve(self.catalog(), bad, digest({"trust": 1}))

    async def test_snapshot_scope_change_prevents_any_dispatch(self):
        binding = resolve(self.catalog(), self.registry(), digest({"trust": 1}))[0]
        attempted = False
        async def open_client():
            nonlocal attempted
            attempted = True
        async def changed():
            return digest({"trust": 2})
        reader = StudyReader("tmux", [Endpoint("beta", False, binding.token, open_client)],
                             local_host="alpha", catalog_revision=binding.selection_revision,
                             catalog_check=changed, profile=ReferenceProfile("tmux"), bindings=(binding,))
        with self.assertRaises(ProtocolError):
            await reader.snapshot()
        self.assertFalse(attempted)


if __name__ == "__main__":
    unittest.main()
