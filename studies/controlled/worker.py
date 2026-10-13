"""Owned fixture cache, native-source proxy and publisher processes; no collectors."""

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace import Trace, canonical  # noqa: E402

from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402

from mesh_plus.api import Bridge, CachedPublication, CachedPublisher  # noqa: E402
from mesh_plus.cli import stdio_channel  # noqa: E402
from mesh_plus.transport import IPCServer, peer_uid  # noqa: E402


async def rpc(path, request):
    reader, writer = await asyncio.open_unix_connection(path, limit=8388609)
    try:
        writer.write((canonical(request) + "\n").encode())
        await writer.drain()
        async with asyncio.timeout(5):
            return json.loads(await reader.readline())
    finally:
        writer.close()
        await writer.wait_closed()


class Native:
    def __init__(self, root):
        self.path = root / "native.sock"

    async def snapshot(self):
        return await rpc(self.path, {"operation": "snapshot"})

    async def watch(self):
        reader, writer = await asyncio.open_unix_connection(self.path, limit=8388609)
        try:
            writer.write(b'{"operation":"watch"}\n')
            await writer.drain()
            while raw := await reader.readline():
                frame = json.loads(raw)
                yield CachedPublication(frame, frame["publisherId"], {"revision": frame["viewRevision"]})
        finally:
            writer.close()
            await writer.wait_closed()


async def hub(args, stopped):
    trace = Trace(args.rows, expired=args.expired)
    mailboxes, tasks = set(), set()
    counts = {"snapshot": 0, "watch": 0, "steps": 0}

    async def handler(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        mailbox = None
        try:
            if peer_uid(writer) != os.getuid():
                raise ValueError("fixture_peer_uid")
            request = json.loads(await reader.readline())
            operation = request["operation"]
            if operation == "snapshot":
                counts[operation] += 1
                reply = trace.frame
            elif operation == "step":
                trace.advance(request["step"])
                counts["steps"] += 1
                for queue in mailboxes:
                    queue.put_nowait(trace.frame)
                reply = trace.describe()
            elif operation == "inspect":
                reply = {**trace.describe(), "counts": counts, "watchers": len(mailboxes)}
            elif operation == "watch":
                counts[operation] += 1
                mailbox = asyncio.Queue(maxsize=1)
                mailboxes.add(mailbox)
                writer.write((canonical(trace.frame) + "\n").encode())
                await writer.drain()
                eof = asyncio.create_task(reader.read())
                try:
                    while not eof.done():
                        item = asyncio.create_task(mailbox.get())
                        done, _ = await asyncio.wait({item, eof}, return_when=asyncio.FIRST_COMPLETED)
                        if item not in done:
                            item.cancel()
                            await asyncio.gather(item, return_exceptions=True)
                            break
                        writer.write((canonical(item.result()) + "\n").encode())
                        await writer.drain()
                finally:
                    eof.cancel()
                    await asyncio.gather(eof, return_exceptions=True)
                return
            else:
                raise ValueError("fixture_operation")
            writer.write((canonical(reply) + "\n").encode())
            await writer.drain()
        finally:
            if mailbox is not None:
                mailboxes.discard(mailbox)
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    path = args.root / "native.sock"
    server = await asyncio.start_unix_server(handler, path, limit=4096)
    path.chmod(0o600)
    try:
        print(canonical({"ready": True, "pid": os.getpid(), "trace": trace.describe()}), flush=True)
        await stopped.wait()
    finally:
        server.close()
        await server.wait_closed()
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        path.unlink(missing_ok=True)


async def publisher(args, stopped):
    pub = CachedPublisher("tmux", "beta", "controlled", Native(args.root), profile=TmuxMeshProfile())
    bridge = Bridge(pub)
    if args.mode == "bridge":
        await bridge.serve(await stdio_channel())
        return
    server = None
    configuration = None
    try:
        if args.carrier == "ipc":
            server = await IPCServer(args.root / "mesh.sock", bridge.serve, max_clients=4).start()
            port = None
        else:
            from mesh_plus.wss import Listener, ServerConfiguration
            cert = args.root / "cert"
            configuration = ServerConfiguration.load(cert / "ca.pem", cert / "server.pem", cert / "server.key", cert / "policy.json")
            server = await Listener(configuration.context, bridge.serve, configuration.authorize,
                                    (pub.host, pub.source, pub.profile)).start()
            port = server.port
        print(canonical({"ready": True, "pid": os.getpid(), "port": port}), flush=True)
        await stopped.wait()
    finally:
        if server is not None:
            await server.close()
        if configuration is not None:
            configuration.close()


async def main(args):
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    await (hub(args, stopped) if args.mode == "hub" else publisher(args, stopped))


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("hub", "publisher", "bridge"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--carrier", choices=("ipc", "wss"), default="ipc")
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--expired", action="store_true")
    args = parser.parse_args()
    if not args.root.is_absolute() or args.root.resolve() != args.root or args.root.stat().st_mode & 0o077:
        parser.error("private_canonical_root")
    asyncio.run(main(args))
