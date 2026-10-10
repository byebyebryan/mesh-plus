"""Explicit host bridge; configured source IDs never resolve wire-supplied argv."""

import argparse
import asyncio
import json
import os
import signal
import stat
import sys
import tomllib
from pathlib import Path

from .bridge import Bridge
from .catalog import MeshAuthority, SSHPlusAuthority
from .client import Client
from .observer import ObserverAdapter, ObserverCodec
from .protocol import MAX_MESSAGE, check
from .reader import Endpoint, Reader
from .remote import connect_catalog_host
from .transport import IPCServer, LineChannel, connect_ipc


def configured_adapter(path, source):
    path = Path(path)
    node = path.lstat()
    check(stat.S_ISREG(node.st_mode) and node.st_uid == os.getuid() and node.st_mode & 0o077 == 0,
          "source_config_policy")
    check(node.st_size <= 65536, "source_config_capacity")
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    check(set(config) == {"version", "host", "sources"} and type(config["version"]) is int and
          config["version"] == 1, "source_config_shape")
    sources = config["sources"]
    check(isinstance(sources, dict) and len(sources) <= 32 and source in sources, "source_not_configured")
    selected = sources[source]
    check(set(selected) == {"domain", "socket"}, "source_descriptor_shape")
    return ObserverAdapter(selected["domain"], config["host"], source, selected["socket"])


async def stdio_channel():
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_MESSAGE + 1)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer)

    class WriteProtocol(asyncio.streams.FlowControlMixin):
        def __init__(self):
            super().__init__(loop=loop)
            self.done = loop.create_future()

        def connection_lost(self, error):
            super().connection_lost(error)
            if not self.done.done():
                if error:
                    self.done.set_exception(error)
                else:
                    self.done.set_result(None)

        def _get_close_waiter(self, stream):
            return self.done

    transport, protocol = await loop.connect_write_pipe(WriteProtocol, sys.stdout.buffer)
    return LineChannel(reader, asyncio.StreamWriter(transport, protocol, reader, loop), "client")


async def run(args):
    authority = MeshAuthority() if getattr(args, "authority", "ssh-plus") == "mesh" else SSHPlusAuthority()
    if args.command == "hosts":
        catalog = await authority.load()
        print(json.dumps(catalog.payload, separators=(",", ":")))
        return
    if args.command in {"read", "watch"}:
        check(not args.local_host or (args.scope in {"local", "fleet"} and not args.hosts), "standalone_scope")
        catalog = None if args.local_host else await authority.load()
        local_host = args.local_host or catalog.local_host
        selected = [{"id": local_host, "local": True}] if catalog is None else catalog.select(args.scope, args.hosts)
        endpoints = []
        for host in selected:
            if host["local"]:
                async def connect_local(host_id=host["id"]):
                    codec = ObserverCodec(args.domain, host_id, args.source)
                    return await Client.connect(await connect_ipc(args.socket), host=host_id, source=args.source,
                                                profile=args.domain + "-observer.mesh-candidate.v1", codec=codec.validate)
                endpoints.append(Endpoint(host["id"], True, None, connect_local))
            else:
                async def connect_remote(selected_host=host):
                    return await connect_catalog_host(catalog, selected_host, args.domain, args.source, authority=authority)
                endpoints.append(Endpoint(host["id"], False, catalog.route_token(host["id"], host["routes"][0]), connect_remote))
        async def catalog_check():
            return (await authority.load()).revision
        reader = Reader(args.domain, endpoints, local_host=local_host, catalog_revision=catalog.revision if catalog else None,
                        catalog_check=catalog_check if catalog else None)
        if args.command == "read":
            print(json.dumps(await reader.snapshot(), ensure_ascii=False, separators=(",", ":")))
        else:
            async for view in reader.watch():
                print(json.dumps(view, ensure_ascii=False, separators=(",", ":")), flush=True)
        return
    adapter = configured_adapter(args.config, args.source)
    bridge = Bridge(adapter)
    if args.command == "bridge":
        await bridge.serve(await stdio_channel())
    else:
        server = await IPCServer(args.socket, bridge.serve).start()
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        for selected in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(selected, stopped.set)
        try:
            await stopped.wait()
        finally:
            await server.close()
            for selected in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(selected)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "mesh":
        from .authority_cli import main as authority_main
        return authority_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description="Mesh Plus experimental cached-state transport")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("mesh", help="Host Mesh authority: list/report-route --json")
    default = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mesh-plus/sources.toml"
    for name in ("bridge", "serve"):
        command = commands.add_parser(name)
        command.add_argument("--source", required=True)
        command.add_argument("--config", type=Path, default=default)
        if name == "bridge":
            command.add_argument("--stdio", action="store_true", required=True)
        else:
            command.add_argument("--socket", type=Path, required=True)
    hosts = commands.add_parser("hosts")
    hosts.add_argument("--authority", choices=("ssh-plus", "mesh"), default="ssh-plus")
    for name in ("read", "watch"):
        command = commands.add_parser(name)
        command.add_argument("--domain", choices=("tmux", "agent"), required=True)
        command.add_argument("--authority", choices=("ssh-plus", "mesh"), default="ssh-plus")
        command.add_argument("--source", required=True)
        command.add_argument("--socket", type=Path, required=True, help="local Mesh bridge IPC endpoint")
        command.add_argument("--scope", choices=("local", "fleet", "hosts"), default="fleet")
        command.add_argument("--hosts", nargs="*", default=[])
        command.add_argument("--local-host", help="explicit standalone local identity; bypass Host Mesh authority")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        # Diagnostics never share stdout with protocol data or expose configuration contents.
        print(json.dumps({"error": getattr(error, "code", "bridge_failed"), "message": "Mesh bridge unavailable"}),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
