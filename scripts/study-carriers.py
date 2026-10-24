"""Disposable synthetic carrier experiment; not a Mesh runtime or provider test.

Owns temporary IPC/TLS/SSH endpoints and keys. Nothing is installed or deployed.
Never loads Observer modules, reads sessions, or changes user SSH configuration.
"""

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import pwd
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from delivery_model import BASE, MAX_MESSAGE, ROOT, Session, encoded, parse, require
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

sys.dont_write_bytecode = True
PROTOCOL = "mesh-plus.delivery-candidate.v1"


class Stream:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer

    async def recv(self):
        value = await self.reader.readline()
        if not value:
            raise EOFError
        return value[:-1], parse(value, "client-frame", line=True)

    async def send(self, value):
        self.writer.write(encoded(value) + b"\n")
        await self.writer.drain()


class Stdio:
    async def recv(self):
        raw = await asyncio.to_thread(sys.stdin.buffer.readline, MAX_MESSAGE + 2)
        if not raw:
            raise EOFError
        return raw[:-1], parse(raw, "client-frame", line=True)

    async def send(self, value):
        raw = encoded(value) + b"\n"
        await asyncio.to_thread(self.write, raw)

    @staticmethod
    def write(raw):
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()


class WebSocket:
    def __init__(self, websocket):
        self.websocket = websocket

    async def recv(self):
        raw = await self.websocket.recv()
        require(isinstance(raw, str), "websocket_text_binding")
        data = raw.encode("utf-8")
        return data, parse(data, "client-frame")

    async def send(self, value):
        await self.websocket.send(encoded(value).decode("utf-8"))


async def publisher(carrier):
    """Fixture source with timer publications independent of client requests."""
    sequence = 0
    channel = str(uuid.uuid4())
    lock = asyncio.Lock()
    subscriptions = {}

    async def emit(kind, **fields):
        nonlocal sequence
        async with lock:
            sequence += 1
            await carrier.send({"protocol": PROTOCOL, "version": 1, "sequence": sequence, "channelId": channel, "kind": kind, **fields})

    async def pushed(subscription, stopped):
        for index in range(1, 33):
            if stopped.is_set():
                return
            await emit("data", subscriptionId=subscription, streamSequence=index,
                       publisherEpoch="publisher_1", deliveryKind="view", cursor=None,
                       payload={"synthetic": True, "view": index, "publisherPid": os.getpid()})
            try:
                await asyncio.wait_for(stopped.wait(), 0.1)
            except TimeoutError:
                pass

    try:
        _, hello = await carrier.recv()
        require(hello["kind"] == "hello", "initial_hello")
        await emit("hello", helloNonce=hello["helloNonce"], hostId=hello["expectedHost"],
                   sourceId=hello["sourceId"], product=hello["product"], profile=hello["profile"],
                   capabilities=["snapshot", "subscribe"], limits=hello["limits"])
        expected_sequence = 2
        while True:
            _, frame = await carrier.recv()
            require(frame["channelId"] == channel and frame["sequence"] == expected_sequence, "client_binding")
            expected_sequence += 1
            if frame["kind"] == "subscribe":
                subscription = frame["subscriptionId"]
                require(subscription not in subscriptions and len(subscriptions) < 2, "study_subscription_limit")
                await emit("subscribed", subscriptionId=subscription, start=frame["start"],
                           barrier={"view": 1}, publisherEpoch="publisher_1")
                stopped = asyncio.Event()
                subscriptions[subscription] = (stopped, asyncio.create_task(pushed(subscription, stopped)))
            elif frame["kind"] == "request":
                size = frame["parameters"]["syntheticBytes"]
                require(frame["operation"] == "snapshot" and size in [1024, 65536, 8 * 1024 * 1024], "study_request_scope")
                await emit("result", requestId=frame["requestId"], outcome="ok", error=None,
                           payload={"synthetic": True, "publisherPid": os.getpid(), "pad": "x" * size})
            elif frame["kind"] == "cancel":
                stopped, task = subscriptions[frame["handleId"]]
                stopped.set()
                await task  # Finish any started frame before the terminal barrier.
                await emit("ended", handleId=frame["handleId"], handleType="subscription", reason="cancelled", cursor=None)
            elif frame["kind"] == "close":
                break
            else:
                raise ValueError("study_operation")
    except (EOFError, ConnectionError):
        pass
    finally:
        for stopped, _ in subscriptions.values():
            stopped.set()
        await asyncio.gather(*(task for _, task in subscriptions.values()), return_exceptions=True)


class Client:
    def __init__(self, receive, send):
        self.receive_raw, self.send_raw = receive, send
        self.guard = None
        self.messages = []
        self.bytes = 0

    async def recv(self):
        raw = await asyncio.wait_for(self.receive_raw(), 10)
        value = parse(raw, "server-frame")
        self.guard.receive(value, len(raw))
        self.messages.append(value)
        self.bytes += len(raw)
        return value

    async def until(self, predicate):
        while True:
            value = await self.recv()
            if predicate(value):
                return value

    async def send(self, kind, **fields):
        frame = {"protocol": PROTOCOL, "version": 1, "sequence": self.guard.client_sequence + 1,
                 "channelId": self.guard.channel, "kind": kind, **fields}
        self.guard.send(frame)
        await self.send_raw(encoded(frame))

    async def run(self):
        hello = json.loads((BASE / "examples/client-hello.json").read_text())
        hello["helloNonce"] = uuid.uuid4().hex
        self.guard = Session(hello)
        await self.send_raw(encoded(hello))
        await self.recv()
        for subscription in ["s1", "s2"]:
            await self.send("subscribe", subscriptionId=subscription, start={"mode": "baseline", "cursor": None}, credit={"frames": 32, "bytes": 2 * MAX_MESSAGE})
            await self.until(lambda v, s=subscription: v.get("kind") == "data" and v.get("subscriptionId") == s)
        timings = []
        for i, size in enumerate([1024, 65536, 8 * 1024 * 1024]):
            start = time.perf_counter()
            await self.send("request", requestId="r" + str(i), operation="snapshot", timeoutMs=10000, parameters={"syntheticBytes": size})
            result = await self.until(lambda v, r="r" + str(i): v.get("requestId") == r)
            require(len(result["payload"]["pad"]) == size, "payload_roundtrip")
            timings.append({"payloadBytes": size, "requestRoundtripMs": round((time.perf_counter() - start) * 1000, 3)})
        await self.send("cancel", handleId="s1", handleType="subscription")
        await self.until(lambda v: v.get("kind") == "ended" and v.get("handleId") == "s1")
        await self.until(lambda v: v.get("kind") == "data" and v.get("subscriptionId") == "s2")
        # Even if all timer publications have arrived, a second request proves
        # cancellation did not close the shared channel. A live sibling remains.
        await self.send("request", requestId="after_cancel", operation="snapshot", timeoutMs=10000, parameters={"syntheticBytes": 1024})
        await self.until(lambda v: v.get("requestId") == "after_cancel")
        require(self.guard.handles["s2"]["phase"] == "active", "sibling_remains_active")
        await self.send("cancel", handleId="s2", handleType="subscription")
        await self.until(lambda v: v.get("kind") == "ended" and v.get("handleId") == "s2")
        await self.send("close", reason="client_done")
        pids = {v["payload"]["publisherPid"] for v in self.messages if v.get("kind") in ["data", "result"]}
        require(len(pids) == 1, "one_publisher_process")
        return {"status": "passed", "scenario": "two timer-push subscriptions, interleaved cached requests, 8 MiB response and independent cancellation", "requestSamples": timings,
                "encodedJsonBytesReceived": self.bytes, "pushFramesReceived": sum(v["kind"] == "data" for v in self.messages), "onePublisherProcess": True, "channelFramesValidated": len(self.messages)}


async def stream_client(reader, writer):
    async def recv():
        raw = await reader.readline()
        require(bool(raw), "unexpected_eof")
        require(raw.endswith(b"\n"), "line_framing")
        return raw[:-1]

    async def send(raw):
        writer.write(raw + b"\n")
        await writer.drain()

    return await Client(recv, send).run()


async def drain_stderr(reader):
    count = 0
    retained = bytearray()
    while data := await reader.read(4096):
        count += len(data)
        retained.extend(data[:max(0, 4096 - len(retained))])
    return count, retained.decode("utf-8", errors="replace")


async def command_client(argv):
    process = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_MESSAGE + 2)
    drain = asyncio.create_task(drain_stderr(process.stderr))
    try:
        result = await stream_client(process.stdout, process.stdin)
        process.stdin.close()
        await asyncio.wait_for(process.wait(), 3)
        require(process.returncode == 0, "carrier_child_exit")
        result["stderrBytesDrained"] = (await drain)[0]
        return result
    except (EOFError, ValueError) as error:
        await asyncio.wait_for(process.wait(), 3)
        _, message = await drain
        raise RuntimeError(str(error) + ": " + message) from error
    finally:
        if process.returncode is None:
            process.terminate()
            await asyncio.wait_for(process.wait(), 3)
        await drain


def run_owned(argv):
    result = subprocess.run(argv, capture_output=True, check=False, timeout=10)
    require(result.returncode == 0, "owned_setup_failed")


async def study_ssh(directory):
    if not all(shutil.which(tool) for tool in ["ssh", "sshd", "ssh-keygen"]):
        return {"status": "not_run", "reason": "SSH tools unavailable"}
    for name in ["host", "client"]:
        run_owned(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(directory / name)])
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), "--stdio"])
    authorized = directory / "authorized_keys"
    authorized.write_text("restrict,command=" + json.dumps(command) + " " + (directory / "client.pub").read_text())
    authorized.chmod(0o600)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = directory / "sshd.conf"
    config.write_text(f"Port {port}\nListenAddress 127.0.0.1\nHostKey {directory / 'host'}\nPidFile {directory / 'sshd.pid'}\nAuthorizedKeysFile {authorized}\nUsePAM no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPubkeyAuthentication yes\nStrictModes yes\nPermitRootLogin no\nAllowUsers {pwd.getpwuid(os.getuid()).pw_name}\nAllowTcpForwarding no\nAllowAgentForwarding no\nX11Forwarding no\nPermitTTY no\nLogLevel DEBUG3\n")
    host_key = (directory / "host.pub").read_text().split()
    known = directory / "known_hosts"
    known.write_text(f"[127.0.0.1]:{port} {host_key[0]} {host_key[1]}\n")
    log = directory / "sshd.log"
    process = await asyncio.create_subprocess_exec(shutil.which("sshd"), "-D", "-f", str(config), "-E", str(log), stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    try:
        ready = False
        for _ in range(60):
            if process.returncode is not None:
                break
            try:
                _reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close(); await writer.wait_closed()
                ready = True
                break
            except OSError:
                await asyncio.sleep(0.025)
        if not ready:
            reason = log.read_text()[:1024] if log.exists() else "isolated sshd did not start"
            # Never change /run/sshd, use sudo, or fall back to operational sshd.
            return {"status": "not_run", "reason": reason.replace(str(directory), "<temporary-directory>").strip()}
        argv = ["ssh", "-F", "/dev/null", "-T", "-p", str(port), "-i", str(directory / "client"), "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-o", "ControlMaster=no", "-o", "ControlPath=none", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + str(known), "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ClearAllForwardings=yes", "-o", "ForwardAgent=no", "-o", "ConnectTimeout=3", pwd.getpwuid(os.getuid()).pw_name + "@127.0.0.1", "mesh-study"]
        try:
            return await command_client(argv)
        except RuntimeError as error:
            detail = log.read_text()[-6000:] if log.exists() else ""
            return {"status": "failed", "reason": (str(error) + detail).replace(str(directory), "<temporary-directory>").strip()}
    finally:
        if process.returncode is None:
            process.terminate()
            await asyncio.wait_for(process.wait(), 3)


async def study_wss(directory):
    cert, key = directory / "server.crt", directory / "server.key"
    run_owned(["openssl", "req", "-x509", "-newkey", "ed25519", "-nodes", "-days", "1", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost", "-keyout", str(key), "-out", str(cert)])
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(cert, key)
    client_tls = ssl.create_default_context(cafile=str(cert))
    async with serve(lambda ws: publisher(WebSocket(ws)), "127.0.0.1", 0, ssl=server_tls, compression=None, max_size=MAX_MESSAGE, max_queue=2, write_limit=65536, subprotocols=[PROTOCOL]) as server:
        port = server.sockets[0].getsockname()[1]
        uri = f"wss://localhost:{port}"
        async with connect(uri, ssl=client_tls, compression=None, proxy=None, max_size=MAX_MESSAGE, max_queue=2, write_limit=65536, subprotocols=[PROTOCOL]) as ws:
            require(ws.subprotocol == PROTOCOL, "websocket_subprotocol")

            async def receive():
                raw = await ws.recv()
                require(isinstance(raw, str), "websocket_text_binding")
                return raw.encode("utf-8")

            result = await Client(receive, lambda raw: ws.send(raw.decode("utf-8"))).run()
        try:
            async with connect(uri, ssl=ssl.create_default_context(), proxy=None, open_timeout=2):
                raise AssertionError("accepted untrusted certificate")
        except ssl.SSLCertVerificationError:
            result["untrustedServerCertificateRejected"] = True
        result["clientAuthorizationTested"] = False
        return result


async def studies(report_path):
    results = {}
    with tempfile.TemporaryDirectory(prefix="mesh-carrier-study-", dir=ROOT / ".venv-design") as tmp:
        directory = Path(tmp)
        async def accept(reader, writer):
            try:
                await publisher(Stream(reader, writer))
            finally:
                writer.close()
                with contextlib.suppress(ConnectionError):
                    await writer.wait_closed()
        path = directory / "mesh.sock"
        server = await asyncio.start_unix_server(accept, str(path), limit=MAX_MESSAGE + 2)
        async with server:
            reader, writer = await asyncio.open_unix_connection(str(path), limit=MAX_MESSAGE + 2)
            results["unix-ipc"] = await stream_client(reader, writer)
            writer.close(); await writer.wait_closed()
        results["subprocess-stdio"] = await command_client([sys.executable, str(Path(__file__).resolve()), "--stdio"])
        results["ssh-stdio"] = await study_ssh(directory)
        results["wss"] = await study_wss(directory)
    status = "passed" if all(r["status"] == "passed" for r in results.values()) else "partial"
    ssh_version = await asyncio.to_thread(subprocess.run, ["ssh", "-V"], capture_output=True, text=True, check=False)
    report = {"status": status, "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "environment": {"python": sys.version.split()[0], "websockets": __import__("websockets").__version__, "ssh": ssh_version.stderr.strip()},
              "validationScope": "owned synthetic endpoints: Unix IPC, subprocess stdio, disposable loopback SSH and WSS with verified server certificate; no native Observer, fleet, production auth or performance acceptance", "results": results,
              "cleanup": "temporary directory removed; owned listeners/children closed; operational SSH config, services and providers untouched",
              "limits": "Single warm-channel sample per payload size, no CPU/RSS benchmark; WSS user authorization and peer-credential IPC acceptance remain untested"}
    inputs = [Path(__file__).resolve(), ROOT / "scripts/delivery_model.py", *sorted(BASE.glob("*.schema.json"))]
    report["inputDigests"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / ".cache/carrier-study.json")
    args = parser.parse_args()
    if args.stdio:
        asyncio.run(publisher(Stdio()))
    else:
        asyncio.run(studies(args.report))


if __name__ == "__main__":
    main()
