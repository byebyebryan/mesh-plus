"""Study-only length-framed mTLS carrier. Not an accepted Mesh backend."""

import asyncio
import hashlib
import secrets
import ssl
import time

from mesh_plus.protocol import MAX_CONTROL, MAX_MESSAGE, check, decode, encode, validate
from mesh_plus.transport import boottime_ms, finish_owned, within_deadline
from mesh_plus.wss.carrier import Listener as WSSListener
from mesh_plus.wss.carrier import budget, pause_until, retire_writer

ALPN = "mesh-study-tcp-json-1"
DATA, PING, PONG, CLOSE = range(4)


class Channel:
    """One u8 tag + u32 network-order length + bounded payload per record."""

    def __init__(self, reader, writer, incoming):
        self.reader, self.writer, self.incoming = reader, writer, incoming
        self.outgoing = "client" if incoming == "server" else "server"
        self.maximum, self.closed = MAX_MESSAGE, False
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue(maxsize=2)
        self.wakeup = asyncio.Event()
        self.receiving = False
        self.failure = EOFError("channel_closed")
        self.retirement = None
        self.pending_ping = None
        tls = writer.get_extra_info("ssl_object")
        self.peer_start = ssl.cert_time_to_seconds(tls.getpeercert()["notBefore"])
        self.peer_expiry = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
        self.metrics = dict(sentFrames=0, receivedFrames=0, sentBytes=0, receivedBytes=0,
                            framedSentBytes=0, framedReceivedBytes=0)
        self.by_kind = {"sent": {}, "received": {}}
        self.pump = asyncio.create_task(self._pump())
        self.liveness = asyncio.create_task(self._liveness())

    def count(self, direction, value, size):
        self.metrics[direction + "Frames"] += 1
        self.metrics[direction + "Bytes"] += size
        item = self.by_kind[direction].setdefault(value["kind"], {"frames": 0, "bytes": 0})
        item["frames"] += 1
        item["bytes"] += size

    async def _write(self, tag, payload):
        async with self.lock:
            check(not self.closed, "study_tcp_closed")
            self.writer.write(bytes([tag]) + len(payload).to_bytes(4, "big") + payload)
            await budget(self.writer.drain(), 2)
            self.metrics["framedSentBytes"] += 5 + len(payload)

    async def _pump(self):
        try:
            while True:
                first = await self.reader.readexactly(1)
                deadline = boottime_ms() + 2000
                tag = first[0]
                check(tag in (DATA, PING, PONG, CLOSE), "study_tcp_tag")
                length = int.from_bytes(await within_deadline(self.reader.readexactly(4), deadline), "big")
                maximum = min(self.maximum, MAX_CONTROL) if self.incoming == "client" else self.maximum
                check(length <= maximum if tag == DATA else length == (0 if tag == CLOSE else 8), "study_tcp_capacity")
                raw = await within_deadline(self.reader.readexactly(length), deadline)
                self.metrics["framedReceivedBytes"] += 5 + length
                if tag == DATA:
                    value = decode(raw, self.incoming, maximum)
                    check(boottime_ms() < deadline, "study_tcp_decode_deadline")
                    self.count("received", value, length)
                    self.queue.put_nowait((value, length))
                    self.wakeup.set()
                elif tag == PING:
                    await self._write(PONG, raw)
                elif tag == PONG:
                    check(self.pending_ping is not None and raw == self.pending_ping[0], "study_tcp_pong")
                    self.pending_ping = None
                else:
                    raise EOFError("channel_closed")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failure = error
            self.closed = True
            self.wakeup.set()
            self.writer.transport.abort()

    async def _liveness(self):
        try:
            while True:
                await pause_until(boottime_ms() + 5000)
                check(self.peer_start <= time.time() < self.peer_expiry, "study_tcp_certificate_expired")
                if self.pending_ping is not None:
                    check(boottime_ms() - self.pending_ping[1] < 5000, "study_tcp_ping_timeout")
                payload = secrets.token_bytes(8)
                self.pending_ping = payload, boottime_ms()
                await self._write(PING, payload)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failure = error
            self.closed = True
            self.wakeup.set()
            self.writer.transport.abort()

    async def receive(self):
        check(not self.receiving, "concurrent_read")
        self.receiving = True
        try:
            while True:
                if self.closed:
                    raise self.failure
                if not self.queue.empty():
                    return self.queue.get_nowait()
                self.wakeup.clear()
                await self.wakeup.wait()
        finally:
            self.receiving = False

    async def send(self, value):
        deadline = boottime_ms() + 2000
        raw = encode(value)
        validate(value, self.outgoing, len(raw), self.maximum)
        await within_deadline(self._write(DATA, raw), deadline)
        self.count("sent", value, len(raw))
        return len(raw)

    def inspect(self):
        return {**self.metrics, "closed": self.closed, "byteScope": "completed-json-messages",
                "byKind": {direction: {kind: value.copy() for kind, value in counts.items()} for direction, counts in self.by_kind.items()}}

    async def _retire(self):
        try:
            if not self.closed:
                try:
                    await self._write(CLOSE, b"")
                except Exception:
                    pass
            self.closed = True
            self.wakeup.set()
            for task in (self.pump, self.liveness):
                task.cancel()
            await asyncio.gather(self.pump, self.liveness, return_exceptions=True)
            await retire_writer(self.writer)
        finally:
            self.writer.transport.abort()

    async def close(self):
        if self.retirement is None:
            self.retirement = asyncio.create_task(self._retire())
        await finish_owned(self.retirement)


class Listener(WSSListener):
    """Reuse reviewed pre-TLS admission, policy monitoring and owned retirement."""

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
            check(tls.selected_alpn_protocol() == ALPN, "study_tcp_alpn")
            fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
            expiry = ssl.cert_time_to_seconds(tls.getpeercert()["notAfter"])
            admitted = await within_deadline(self._authorize(fingerprint, expiry), deadline)
            check(await within_deadline(self._authorize(fingerprint, expiry), deadline) == admitted, "study_tcp_policy_changed")
            channel = Channel(reader, writer, "client")
            self.channels.add(channel)
            monitor = asyncio.create_task(self._monitor(fingerprint, expiry, channel, admitted))
            self.dispatched += 1
            await self.handler(channel)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.failures += 1
        finally:
            async def cleanup():
                try:
                    if monitor is not None:
                        monitor.cancel()
                        await asyncio.gather(monitor, return_exceptions=True)
                    if channel is not None:
                        await channel.close()
                    elif writer is not None:
                        await retire_writer(writer)
                    else:
                        sock.close()
                finally:
                    if channel is not None:
                        self.channels.discard(channel)
                    self.slots.release()
            await finish_owned(asyncio.create_task(cleanup()))


async def connect(port, context):
    context.set_alpn_protocols([ALPN])
    reader, writer = await budget(asyncio.open_connection("127.0.0.1", port, ssl=context, server_hostname="localhost",
                                                        ssl_handshake_timeout=3, ssl_shutdown_timeout=1), 3)
    try:
        writer.transport.set_write_buffer_limits(high=65536, low=16384)
        check(writer.get_extra_info("ssl_object").selected_alpn_protocol() == ALPN, "study_tcp_alpn")
        return Channel(reader, writer, "server")
    except BaseException:
        await retire_writer(writer)
        raise
