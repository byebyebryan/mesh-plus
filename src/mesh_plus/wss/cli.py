"""Explicit optional WSS listener and cached-state diagnostics."""

import argparse
import asyncio
import importlib.metadata
import json
import signal
import sys
from pathlib import Path

from mesh_plus.bridge import Bridge
from mesh_plus.cli import configured_adapter
from mesh_plus.diagnostics import failure_code, probe

from .carrier import Listener
from .configuration import Selection, ServerConfiguration
from .configured_read import configured_reader


async def run(args):
    if args.command == "doctor":
        report = {"ok": True, "backend": "wss", "networkContacted": False,
                  "version": importlib.metadata.version("mesh-plus"),
                  "websockets": importlib.metadata.version("websockets")}
        print(json.dumps(report, separators=(",", ":")))
        return 0
    if args.command == "serve":
        adapter = configured_adapter(args.config, args.source)
        configuration = ServerConfiguration.load(args.ca, args.certificate, args.key, args.authorization)
        server = None
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for selected in signals:
            loop.add_signal_handler(selected, stopped.set)
        try:
            await configuration.authorize()
            server = await Listener(configuration.context, Bridge(adapter).serve, configuration.authorize,
                                    (adapter.host, adapter.source, adapter.profile)).start(args.port,
                                                                                        address=args.address)
            # Readiness has no credential, peer or source-payload contents.
            print(json.dumps({"ready": True, "backend": "wss", "port": server.port}), flush=True)
            await stopped.wait()
        finally:
            try:
                if server is not None:
                    await server.close()
            finally:
                configuration.close()
                for selected in signals:
                    loop.remove_signal_handler(selected)
        return 0

    selection = Selection.load(args.catalog, args.registry, args.ca, args.certificate, args.key)
    reader = None
    iterator = None
    try:
        reader = await configured_reader(args.domain, selection=selection, source=args.source,
                                         socket=args.socket, scope=args.scope, hosts=args.hosts)
        if args.command == "probe":
            # This command probes WSS only; the mixed reader has separate read/watch commands.
            bindings = {binding.host for binding in selection.bindings}
            if len(reader.endpoints) != 1 or reader.endpoints[0].host not in bindings:
                raise ValueError("probe requires one explicitly selected WSS host")
            report = await probe(reader.endpoints[0].connect, mode=args.mode, timeout_ms=args.timeout_ms)
            report["backend"] = "wss"
            print(json.dumps(report, separators=(",", ":")))
            return 0 if report["ok"] else 1
        if args.command == "read":
            print(json.dumps(await reader.snapshot(), ensure_ascii=False, separators=(",", ":")))
        else:
            iterator = reader.watch()
            async for view in iterator:
                print(json.dumps(view, ensure_ascii=False, separators=(",", ":")), flush=True)
        return 0
    finally:
        try:
            if iterator is not None:
                await iterator.aclose()
            if reader is not None and getattr(args, "metrics", False):
                print(json.dumps(reader.inspect(), separators=(",", ":")), file=sys.stderr)
        finally:
            selection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="installed dependency diagnostics; no host contact")
    listener = commands.add_parser("serve", help="one explicitly configured cached publisher")
    listener.add_argument("--config", type=Path, required=True, help="private sources.toml")
    listener.add_argument("--source", required=True)
    listener.add_argument("--authorization", type=Path, required=True)
    listener.add_argument("--address", required=True, help="numeric bind address, including LAN/tailnet")
    listener.add_argument("--port", type=int, required=True)
    credential_parsers = [listener]
    for name in ("read", "watch", "probe"):
        command = commands.add_parser(name)
        credential_parsers.append(command)
        command.add_argument("--catalog", type=Path, required=True, help="private captured Host Mesh JSON")
        command.add_argument("--registry", type=Path, required=True)
        command.add_argument("--domain", choices=("tmux", "agent"), required=True)
        command.add_argument("--source", required=True)
        command.add_argument("--socket", type=Path, required=True, help="local Mesh IPC path for mixed fleets")
        command.add_argument("--scope", choices=("local", "fleet", "hosts"), default="fleet")
        command.add_argument("--hosts", nargs="*", default=[])
        if name == "probe":
            command.add_argument("--mode", choices=("snapshot", "subscribe"), default="snapshot")
            command.add_argument("--timeout-ms", type=int, choices=range(1, 60001), default=5000,
                                 metavar="1..60000")
        else:
            command.add_argument("--metrics", action="store_true")
    for selected in credential_parsers:
        for name in ("ca", "certificate", "key"):
            selected.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({"error": failure_code(error), "message": "WSS operation unavailable"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
