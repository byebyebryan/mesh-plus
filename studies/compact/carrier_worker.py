"""Separate fixture and publisher roles for full-proof WSS/TCP study."""

import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "controlled"))
from worker import Native, hub  # noqa: E402

sys.path.insert(0, str(ROOT))
from tcp_stream import ALPN  # noqa: E402
from tcp_stream import Listener as TCPListener  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402

from mesh_plus.api import Bridge, CachedPublisher  # noqa: E402
from mesh_plus.wss import Listener, ServerConfiguration  # noqa: E402


async def main(args):
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for selected in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(selected, stopped.set)
    if args.mode == "hub":
        await hub(args, stopped)
        return
    pub = CachedPublisher("tmux", "beta", "controlled", Native(args.root), profile=TmuxMeshProfile())
    cert = args.root / "cert"
    configuration = ServerConfiguration.load(cert / "ca.pem", cert / "server.pem", cert / "server.key", cert / "policy.json")
    listener = None
    try:
        selected = Listener if args.carrier == "wss" else TCPListener
        if args.carrier == "tcp":
            configuration.context.set_alpn_protocols([ALPN])
        listener = await selected(configuration.context, Bridge(pub).serve, configuration.authorize,
                                  (pub.host, pub.source, pub.profile)).start()
        print(json.dumps({"ready": True, "pid": os.getpid(), "port": listener.port}), flush=True)
        await stopped.wait()
    finally:
        if listener is not None:
            await listener.close()
        configuration.close()


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("hub", "publisher"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--carrier", choices=("tcp", "wss"), default="wss")
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--expired", action="store_true")
    args = parser.parse_args()
    if not args.root.is_absolute() or args.root.resolve() != args.root or args.root.stat().st_mode & 0o077:
        parser.error("private_canonical_root")
    asyncio.run(main(args))
