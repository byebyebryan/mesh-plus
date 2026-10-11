"""Owned publisher worker shared by matched IPC/SSH/WSS study topology."""

import argparse
import asyncio
import json
import signal
import sys
from pathlib import Path

from carrier import Listener
from fixtures import BroadcastPublisher, contexts, fingerprint

from mesh_plus.bridge import Bridge
from mesh_plus.transport import IPCServer


async def main(args):
    root = Path(args.root)
    publisher = BroadcastPublisher(args.domain, rows=args.rows)
    bridge = Bridge(publisher)
    channels = set()
    async def serve(channel):
        channels.add(channel)
        try:
            await bridge.serve(channel)
        finally:
            channels.discard(channel)
    if args.carrier == "wss":
        context, _ = contexts(root.parent)
        binding = [publisher.host, publisher.source, publisher.profile]
        async def policy():
            return {fingerprint(root.parent): binding}
        listener = await Listener(context, serve, policy, binding).start()
        address = listener.url
    else:
        listener = await IPCServer(root / "publisher.sock", serve).start()
        address = str(root / "publisher.sock")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    reader = asyncio.StreamReader(limit=1024)
    transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    async def controls():
        while raw := await reader.readline():
            value = json.loads(raw)
            if value == {"operation": "drop"}:
                await asyncio.gather(*(channel.close() for channel in list(channels)))
            else:
                raise ValueError("study_control")
        stop.set()
    async def updates():
        while True:
            await asyncio.sleep(1)
            publisher.update()
    jobs = [asyncio.create_task(controls())]
    if args.updates:
        jobs.append(asyncio.create_task(updates()))
    print(json.dumps({"address": address, "publisherId": publisher.codec.inspect_native(publisher.frame).publisher}), flush=True)
    try:
        await stop.wait()
    finally:
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        await listener.close()
        transport.close()
        if channels or publisher.watchers:
            raise RuntimeError("study_node_retained_resources")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--domain", choices=("tmux", "agent"), required=True)
    parser.add_argument("--carrier", choices=("ipc", "ssh", "wss"), required=True)
    parser.add_argument("--rows", type=int, default=0)
    parser.add_argument("--updates", action="store_true")
    asyncio.run(main(parser.parse_args()))
