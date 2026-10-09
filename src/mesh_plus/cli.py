"""Explicit host bridge; configured source IDs never resolve wire-supplied argv."""

import argparse
import asyncio
import json
import os
import stat
import sys
import tomllib
from pathlib import Path

from .bridge import Bridge
from .observer import ObserverAdapter
from .protocol import MAX_MESSAGE, check
from .transport import IPCServer, LineChannel


def configured_adapter(path, source):
    path = Path(path)
    node = path.lstat()
    check(stat.S_ISREG(node.st_mode) and node.st_uid == os.getuid() and node.st_mode & 0o077 == 0,
          "source_config_policy")
    check(node.st_size <= 65536, "source_config_capacity")
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    check(set(config) == {"version", "host", "sources"} and config["version"] == 1, "source_config_shape")
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
    adapter = configured_adapter(args.config, args.source)
    bridge = Bridge(adapter)
    if args.command == "bridge":
        await bridge.serve(await stdio_channel())
    else:
        server = await IPCServer(args.socket, bridge.serve).start()
        try:
            await asyncio.Event().wait()
        finally:
            await server.close()


def main():
    parser = argparse.ArgumentParser(description="Mesh Plus experimental cached-state transport")
    commands = parser.add_subparsers(dest="command", required=True)
    default = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mesh-plus/sources.toml"
    for name in ("bridge", "serve"):
        command = commands.add_parser(name)
        command.add_argument("--source", required=True)
        command.add_argument("--config", type=Path, default=default)
        if name == "bridge":
            command.add_argument("--stdio", action="store_true", required=True)
        else:
            command.add_argument("--socket", type=Path, required=True)
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
