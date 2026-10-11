"""Owned bounded native TLS/WebSocket carriage for cached Mesh state."""

import asyncio
import contextlib
import hashlib
import re
import secrets
import socket
import ssl
import time
from urllib.parse import urlsplit

from websockets.client import ClientProtocol
from websockets.frames import Frame, Opcode
from websockets.http11 import Request, Response
from websockets.protocol import State
from websockets.server import ServerProtocol
from websockets.uri import parse_uri

from mesh_plus.protocol import MAX_CONTROL, MAX_MESSAGE, PROTOCOL, check, decode, encode, validate
from mesh_plus.transport import boottime_ms, finish_owned, within_deadline


def endpoint_url(url):
    value = urlsplit(url)
    check(value.scheme == "wss" and value.hostname and value.path.startswith("/") and
          not value.username and not value.password and not value.query and not value.fragment,
          "wss_endpoint")
    check(value.path == "/mesh/state" and value.netloc.isascii(), "wss_path")
    check(len(url) <= 4096 and (value.port is None or 1 <= value.port <= 65535), "wss_endpoint")
    check(not any(c.isspace() or ord(c) < 32 for c in url), "wss_endpoint")
    return value


async def budget(awaitable, seconds):
    return await within_deadline(awaitable, boottime_ms() + int(seconds * 1000))


async def pause_until(deadline):
    """Notice BOOTTIME resume on the next runnable 100 ms tick."""
    while boottime_ms() < deadline:
        await asyncio.sleep(min(.1, (deadline - boottime_ms()) / 1000))


async def retire_writer(writer):
    writer.close()
    try:
        await budget(writer.wait_closed(), 1)
    except (Exception, asyncio.CancelledError):
        writer.transport.abort()


async def flush(protocol, writer):
    for data in protocol.data_to_send():
        if data:
            writer.write(data)
        else:
            writer.close()  # TLS cannot half-close.
    await budget(writer.drain(), 2)


async def header(protocol, reader):
    raw = await budget(reader.readuntil(b"\r\n\r\n"), 3)
    check(len(raw) <= MAX_CONTROL, "wss_http_capacity")
    protocol.receive_data(raw)
    events = protocol.events_received()
    check(len(events) == 1, "wss_handshake")
    return events[0]


class Channel:
    """Single owned parser/pump with bounded application queue and fragment work.

    The two-byte RFC header/length admission rejects oversized allocations before
    readexactly. websockets performs masking, opcode, control and framing checks.
    No private library buffers or asyncio protocol hooks are inspected.
    """

    framing_bytes = 0

    def __init__(self, reader, writer, protocol, incoming, *, assembly_timeout=2):
        self.reader, self.writer, self.protocol = reader, writer, protocol
        self.incoming = incoming
        self.outgoing = "server" if incoming == "client" else "client"
        self.maximum = MAX_MESSAGE
        self.closed = False
        self.assembly_timeout = assembly_timeout
        self.queue = asyncio.Queue(maxsize=2)
        self.wakeup = asyncio.Event()
        self.lock = asyncio.Lock()
        self.receiving = False
        self.failure = EOFError("channel_closed")
        self.retirement = None
        self.metrics = dict(sentFrames=0, receivedFrames=0, sentBytes=0, receivedBytes=0,
                            websocketSentBytes=0, websocketReceivedBytes=0, peakQueueFrames=0,
                            peakAssemblyBytes=0, peakFragments=0)
        self.by_kind = {"sent": {}, "received": {}}
        self.pending_ping = None
        tls = writer.get_extra_info("ssl_object")
        self.peer_expiry = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
        self.peer_start = ssl.cert_time_to_seconds(tls.getpeercert()["notBefore"])
        self.pump = asyncio.create_task(self._pump())
        self.liveness = asyncio.create_task(self._liveness())

    async def _liveness(self):
        try:
            while True:
                await pause_until(boottime_ms() + 5000)
                check(self.peer_start <= time.time() < self.peer_expiry, "wss_certificate_expired")
                if self.pending_ping:
                    check(boottime_ms() - self.pending_ping[1] < 5000, "wss_ping_timeout")
                async with self.lock:
                    payload = secrets.token_bytes(8)
                    self.pending_ping = (payload, boottime_ms())
                    self.protocol.send_ping(payload)
                    await self._flush()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failure = error
            self.closed = True
            self.wakeup.set()
            self.writer.transport.abort()

    def count(self, direction, value, size):
        self.metrics[direction + "Frames"] += 1
        self.metrics[direction + "Bytes"] += size
        item = self.by_kind[direction].setdefault(value["kind"], {"frames": 0, "bytes": 0})
        item["frames"] += 1
        item["bytes"] += size

    async def _flush(self):
        for data in self.protocol.data_to_send():
            if data:
                self.metrics["websocketSentBytes"] += len(data)
                self.writer.write(data)
            else:
                self.writer.close()
        await budget(self.writer.drain(), 2)

    async def _frame(self, deadline):
        # First wire byte starts the assembly budget, even for an incomplete
        # header. Fragment/control trickling cannot reset an existing deadline.
        first = await self.reader.readexactly(1) if deadline is None else await within_deadline(
            self.reader.readexactly(1), deadline)
        deadline = deadline or boottime_ms() + int(1000 * self.assembly_timeout)
        second = await within_deadline(self.reader.readexactly(1), deadline)
        prefix = first + second
        length = second[0] & 127
        if length in (126, 127):
            extra = await within_deadline(self.reader.readexactly(2 if length == 126 else 8), deadline)
            prefix += extra
            length = int.from_bytes(extra, "big")
        maximum = min(MAX_CONTROL, self.maximum) if self.incoming == "client" else self.maximum
        check(length <= maximum, "message_capacity")
        if second[0] & 128:
            prefix += await within_deadline(self.reader.readexactly(4), deadline)
        payload = await within_deadline(self.reader.readexactly(length), deadline)
        raw = prefix + payload
        self.metrics["websocketReceivedBytes"] += len(raw)
        self.protocol.receive_data(raw)
        events = self.protocol.events_received()
        async with self.lock:
            await self._flush()
        check(len(events) == 1 and isinstance(events[0], Frame), "wss_frame")
        return events[0], deadline

    async def _pump(self):
        assembly = bytearray()
        fragments, deadline = 0, None
        try:
            while True:
                frame, started = await self._frame(deadline)
                if frame.opcode in (Opcode.PING, Opcode.PONG):
                    if frame.opcode == Opcode.PONG and self.pending_ping and frame.data == self.pending_ping[0]:
                        self.pending_ping = None
                    continue
                check(frame.opcode != Opcode.CLOSE, "channel_closed")
                check(frame.opcode in (Opcode.TEXT, Opcode.CONT), "wss_text_only")
                check((frame.opcode == Opcode.TEXT) == (fragments == 0), "wss_fragment_order")
                deadline = started
                fragments += 1
                check(fragments <= 256, "wss_fragment_capacity")
                maximum = min(self.maximum, MAX_CONTROL) if self.incoming == "client" else self.maximum
                check(len(assembly) + len(frame.data) <= maximum, "message_capacity")
                assembly.extend(frame.data)
                self.metrics["peakAssemblyBytes"] = max(self.metrics["peakAssemblyBytes"], len(assembly))
                self.metrics["peakFragments"] = max(self.metrics["peakFragments"], fragments)
                if not frame.fin:
                    continue
                value = decode(bytes(assembly), self.incoming, maximum)
                check(boottime_ms() < deadline, "frame_deadline")
                self.count("received", value, len(assembly))
                await budget(self.queue.put((value, len(assembly))), 2)
                self.metrics["peakQueueFrames"] = max(self.metrics["peakQueueFrames"], self.queue.qsize())
                self.wakeup.set()
                assembly.clear()
                fragments, deadline = 0, None
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failure = error
        finally:
            self.closed = True
            self.wakeup.set()
            self.liveness.cancel()
            await asyncio.gather(self.liveness, return_exceptions=True)
            while not self.queue.empty():
                self.queue.get_nowait()
            await retire_writer(self.writer)

    async def receive(self):
        check(not self.receiving, "concurrent_receive")
        self.receiving = True
        try:
            while self.queue.empty():
                if self.closed:
                    raise self.failure
                self.wakeup.clear()
                await self.wakeup.wait()
            return self.queue.get_nowait()
        finally:
            self.receiving = False

    async def send(self, value):
        deadline = boottime_ms() + 2000
        try:
            raw = encode(value)
            validate(value, self.outgoing, len(raw), self.maximum)
            check(boottime_ms() < deadline, "frame_deadline")
            async def write():
                async with self.lock:
                    check(not self.closed, "channel_closed")
                    self.protocol.send_text(raw)
                    await self._flush()
                    self.count("sent", value, len(raw))
            await within_deadline(write(), deadline)
        except BaseException:
            await self.close()
            raise
        return len(raw)

    async def _retire(self):
        deadline = boottime_ms() + 3000
        self.closed = True
        self.wakeup.set()
        if not self.pump.done() and self.protocol.state == State.OPEN:
            async def graceful():
                async with self.lock:
                    self.protocol.send_close(1000)
                    await self._flush()
                await asyncio.shield(self.pump)
            with contextlib.suppress(Exception):
                await budget(graceful(), 1)
        self.pump.cancel()
        self.liveness.cancel()
        await asyncio.gather(self.pump, return_exceptions=True)
        await asyncio.gather(self.liveness, return_exceptions=True)
        if boottime_ms() >= deadline:
            self.writer.transport.abort()
        else:
            try:
                await within_deadline(retire_writer(self.writer), deadline)
            except TimeoutError:
                self.writer.transport.abort()
        # Application values must not outlive a closed owned connection.
        while not self.queue.empty():
            self.queue.get_nowait()

    async def close(self):
        if self.retirement is None:
            self.retirement = asyncio.create_task(self._retire())
        await finish_owned(self.retirement)

    def inspect(self):
        return {**self.metrics, "closed": self.closed, "byteScope": "completed-json-messages",
                "transportByteScope": "websocket-framing-before-TLS", "byKind": {
                    side: {kind: item.copy() for kind, item in kinds.items()}
                    for side, kinds in self.by_kind.items()}}


async def _connect(url, context, *, server_hostname=None):
    target = endpoint_url(url)
    check(context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname, "wss_server_trust")
    reader, writer = await budget(asyncio.open_connection(
        target.hostname, target.port or 443, ssl=context,
        server_hostname=server_hostname or target.hostname, ssl_handshake_timeout=3,
        ssl_shutdown_timeout=1, limit=MAX_CONTROL), 3)
    try:
        protocol = ClientProtocol(parse_uri(url), subprotocols=[PROTOCOL], max_size=MAX_MESSAGE)
        protocol.send_request(protocol.connect())
        await flush(protocol, writer)
        response = await header(protocol, reader)
        check(isinstance(response, Response) and response.status_code == 101 and
              protocol.subprotocol == PROTOCOL, "wss_handshake")
        writer.transport.set_write_buffer_limits(high=65536, low=16384)
        return Channel(reader, writer, protocol, "server")
    except BaseException:
        await finish_owned(asyncio.create_task(retire_writer(writer)))
        raise


async def connect(url, context, *, server_hostname=None):
    """One aggregate setup budget, including TLS, HTTP and validation."""
    return await budget(_connect(url, context, server_hostname=server_hostname), 15)


class Listener:
    """Explicit numeric bind address, pre-TLS admission and fixed-source policy."""

    def __init__(self, context, handler, policy, binding, *, max_clients=4, policy_interval=5):
        check(context.verify_mode == ssl.CERT_REQUIRED, "wss_client_trust")
        check(0 < policy_interval <= 5 and 1 <= max_clients <= 4, "wss_listener_limits")
        self.context, self.handler, self.policy, self.binding = context, handler, policy, tuple(binding)
        self.slots = asyncio.Semaphore(max_clients)
        self.policy_interval = policy_interval
        self.tasks, self.channels = set(), set()
        self.acceptor, self.sock = None, None
        self.peak_admitted = 0
        self.dispatched = 0
        self.failures = 0
        self.unexpected = 0
        self.closed = False
        self.retirement = None

    async def start(self, port=0, *, address="127.0.0.1"):
        import ipaddress
        check(not self.closed and self.sock is None, "wss_listener_state")
        check(type(port) is int and 0 <= port <= 65535, "wss_listener_port")
        selected = ipaddress.ip_address(address)
        self.sock = socket.socket(socket.AF_INET6 if selected.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((address, port))
        except BaseException:
            self.sock.close()
            self.sock = None
            raise
        self.sock.listen(4)
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        hostname = "localhost" if selected.is_loopback else (f"[{address}]" if selected.version == 6 else address)
        self.url = f"wss://{hostname}:{self.port}/mesh/state"
        self.acceptor = asyncio.create_task(self._accept())
        return self

    async def _accept(self):
        loop = asyncio.get_running_loop()
        while True:
            await self.slots.acquire()
            try:
                sock, _ = await loop.sock_accept(self.sock)
            except BaseException:
                self.slots.release()
                raise
            task = asyncio.create_task(self._serve(sock))
            self.tasks.add(task)
            task.add_done_callback(self._completed)
            self.peak_admitted = max(self.peak_admitted, len(self.tasks))

    def _completed(self, task):
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            self.unexpected += 1

    async def _authorize(self, fingerprint, not_after):
        check(time.time() < not_after, "wss_certificate_expired")
        allowed = await budget(self.policy(), 5)
        check(isinstance(allowed, dict) and len(allowed) <= 128 and all(
            re.fullmatch(r"[0-9a-f]{64}", principal) and isinstance(binding, list) and len(binding) == 3 and
            all(isinstance(v, str) for v in binding) and re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,16383}", binding[0]) and
            re.fullmatch(r"[a-z][a-z0-9_]{0,127}", binding[1]) and
            binding[2] in {"tmux-observer.mesh-candidate.v1", "agent-observer.mesh-candidate.v1"}
            for principal, binding in allowed.items()), "wss_policy")
        check(allowed.get(fingerprint) == list(self.binding),
              "wss_principal_denied")
        return allowed

    async def _monitor(self, fingerprint, not_after, channel, admitted):
        while True:
            started = boottime_ms()
            try:
                current = await self._authorize(fingerprint, not_after)
                check(current == admitted, "wss_policy_changed")
            except Exception:
                await channel.close()
                return
            await pause_until(started + int(self.policy_interval * 1000))

    async def _serve(self, sock):
        writer, channel, monitor = None, None, None
        deadline = boottime_ms() + 15000
        try:
            loop = asyncio.get_running_loop()
            reader = asyncio.StreamReader(limit=MAX_CONTROL)
            protocol = asyncio.StreamReaderProtocol(reader)
            transport, _ = await within_deadline(loop.connect_accepted_socket(
                lambda: protocol, sock, ssl=self.context, ssl_handshake_timeout=3,
                ssl_shutdown_timeout=1), min(deadline, boottime_ms() + 3000))
            writer = asyncio.StreamWriter(transport, protocol, reader, loop)
            transport.set_write_buffer_limits(high=65536, low=16384)
            tls = writer.get_extra_info("ssl_object")
            fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
            not_after = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
            admitted = await within_deadline(self._authorize(fingerprint, not_after), deadline)
            websocket = ServerProtocol(subprotocols=[PROTOCOL], max_size=MAX_CONTROL)
            request = await within_deadline(header(websocket, reader), deadline)
            check(isinstance(request, Request) and request.path == "/mesh/state" and
                  "Origin" not in request.headers, "wss_request_policy")
            response = websocket.accept(request)
            check(response.status_code == 101 and websocket.subprotocol == PROTOCOL, "wss_handshake")
            # Recheck after handshake parsing, immediately before fixed source dispatch.
            check(await within_deadline(self._authorize(fingerprint, not_after), deadline) == admitted, "wss_policy_changed")
            websocket.send_response(response)
            await within_deadline(flush(websocket, writer), deadline)
            channel = Channel(reader, writer, websocket, "client")
            self.channels.add(channel)
            monitor = asyncio.create_task(self._monitor(fingerprint, not_after, channel, admitted))
            self.dispatched += 1
            await self.handler(channel)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.failures += 1  # Redacted counters only, no peer/credential logging.
        finally:
            async def cleanup():
                try:
                    if monitor:
                        monitor.cancel()
                        await asyncio.gather(monitor, return_exceptions=True)
                    if channel:
                        await channel.close()
                    elif writer:
                        await retire_writer(writer)
                    else:
                        sock.close()
                finally:
                    if channel:
                        self.channels.discard(channel)
                    self.slots.release()
            await finish_owned(asyncio.create_task(cleanup()))

    async def _retire(self):
        self.closed = True
        if self.acceptor:
            self.acceptor.cancel()
            await asyncio.gather(self.acceptor, return_exceptions=True)
        if self.sock:
            self.sock.close()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        if self.retirement is None:
            self.retirement = asyncio.create_task(self._retire())
        await finish_owned(self.retirement)
