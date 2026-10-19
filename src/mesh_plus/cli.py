"""Explicit host bridge; configured source IDs never resolve wire-supplied argv."""

import argparse
import json
import os
import signal
import stat
import sys
import tomllib
from pathlib import Path


def configured_descriptor(path, source):
    from .protocol import check

    path = Path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        node = os.fstat(stream.fileno())
        check(stat.S_ISREG(node.st_mode) and node.st_uid == os.getuid() and node.st_mode & 0o077 == 0,
              "source_config_policy")
        check(node.st_size <= 65536, "source_config_capacity")
        data = stream.read(65537)
        check(len(data) <= 65536, "source_config_capacity")
        config = tomllib.loads(data.decode("utf-8"))
    check(set(config) == {"version", "host", "sources"} and type(config["version"]) is int and
          config["version"] == 1, "source_config_shape")
    sources = config["sources"]
    check(isinstance(sources, dict) and len(sources) <= 32 and source in sources, "source_not_configured")
    selected = sources[source]
    check(isinstance(selected, dict) and set(selected) == {"domain", "socket"}, "source_descriptor_shape")
    check(selected["domain"] in {"tmux", "agent"} and isinstance(selected["socket"], str) and
          Path(selected["socket"]).is_absolute() and isinstance(config["host"], str), "source_descriptor_shape")
    return config["host"], selected["domain"], selected["socket"]


def publisher_factory_map(publisher_factories):
    """Capture trusted Python factories only; never resolve wire/config imports."""
    from .protocol import check

    factories = {} if publisher_factories is None else dict(publisher_factories)
    check(set(factories) <= {"tmux", "agent"} and all(callable(f) for f in factories.values()),
          "publisher_factory_mapping")
    return factories


def configured_adapter(path, source, *, publisher_factories=None):
    from .protocol import check

    factories = publisher_factory_map(publisher_factories)
    host, domain, socket = configured_descriptor(path, source)
    if domain in factories:
        from .state import descriptor

        adapter = factories[domain](host, source, socket)
        supported = {descriptor(domain).profile_id}
        if domain == "agent":
            supported.add(descriptor(domain, profile_id="agent-observer.mesh-candidate.v2").profile_id)
            supported.add(descriptor(domain, profile_id="agent-observer.mesh-candidate.v3").profile_id)
            supported.add(descriptor(domain, profile_id="agent-observer.mesh-active.v1").profile_id)
            supported.add(descriptor(domain, profile_id="agent-observer.mesh-working-set.v1").profile_id)
        check(getattr(adapter, "host", None) == host and getattr(adapter, "source", None) == source and
              isinstance(getattr(adapter, "profile", None), str) and adapter.profile in supported, "publisher_factory_binding")
        capabilities = getattr(adapter, "capabilities", None)
        check(isinstance(capabilities, (tuple, list)) and all(isinstance(c, str) for c in capabilities) and
              len(capabilities) == len(set(capabilities)) and
              set(capabilities) <= {"snapshot", "proof", "subscribe"} and
              all(callable(getattr(adapter, name, None)) for name in ("validate", "snapshot", "proof", "watch")),
              "publisher_factory_interface")
        return adapter
    from .observer import ObserverAdapter

    return ObserverAdapter(domain, host, source, socket)


async def stdio_channel():
    import asyncio

    from .protocol import MAX_MESSAGE
    from .transport import LineChannel

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


async def run(args, *, publisher_factories=None):
    publisher_factories = publisher_factory_map(publisher_factories)
    if args.command == "doctor":
        from .diagnostics import doctor, doctor_sdk, failure_code

        report = doctor_sdk() if args.sdk else doctor()
        if args.config:
            try:
                configured_descriptor(args.config, args.source)
                report["checks"]["sourceConfiguration"] = "accepted"
            except Exception as error:
                report["ok"] = False
                report["checks"]["sourceConfiguration"] = failure_code(error)
        print(json.dumps(report, separators=(",", ":")))
        return 0 if report["ok"] else 1
    if args.command == "probe":
        from .catalog import MeshAuthority
        from .client import Client
        from .diagnostics import probe
        from .observer import ObserverCodec
        from .protocol import check
        from .remote import connect_catalog_host
        from .transport import connect_ipc

        async def connect():
            codec = ObserverCodec(args.domain, args.host, args.source)
            if args.socket:
                return await Client.connect(await connect_ipc(args.socket), host=args.host, source=args.source,
                                            profile=args.domain + "-observer.mesh-candidate.v1", codec=codec.validate)
            catalog = await MeshAuthority().load()
            selected = catalog.select("hosts", [args.host])[0]
            check(not selected["local"], "probe_local_requires_socket")
            return await connect_catalog_host(catalog, selected, args.domain, args.source, authority=None)
        report = await probe(connect, mode=args.mode, timeout_ms=args.timeout_ms)
        print(json.dumps(report, separators=(",", ":")))
        return 0 if report["ok"] else 1
    if args.command == "assess":
        from .catalog import MeshAuthority, SSHPlusAuthority
        from .diagnostics import assess_configured
        authority = MeshAuthority() if args.authority == "mesh" else SSHPlusAuthority()
        report = await assess_configured(args.domain, mode=args.mode, timeout_ms=args.timeout_ms,
                                         source=args.source, socket=args.socket, scope=args.scope, hosts=args.hosts,
                                         local_host=args.local_host, authority=authority)
        print(json.dumps(report, separators=(",", ":")))
        return 0 if report["ok"] else 1
    if args.command in {"hosts", "read", "watch"}:
        from .catalog import MeshAuthority, SSHPlusAuthority

        authority = MeshAuthority() if args.authority == "mesh" else SSHPlusAuthority()
        if args.command == "hosts":
            catalog = await authority.load()
            print(json.dumps(catalog.payload, separators=(",", ":")))
            return
        from .configured_read import configured_reader

        reader = await configured_reader(args.domain, source=args.source, socket=args.socket,
                                         scope=args.scope, hosts=args.hosts, local_host=args.local_host,
                                         authority=authority, report_routes=True)
        iterator = None
        try:
            if args.command == "read":
                print(json.dumps(await reader.snapshot(), ensure_ascii=False, separators=(",", ":")))
            else:
                iterator = reader.watch()
                async for view in iterator:
                    print(json.dumps(view, ensure_ascii=False, separators=(",", ":")), flush=True)
        finally:
            if iterator is not None:
                await iterator.aclose()
            if args.metrics:
                print(json.dumps(reader.inspect(), separators=(",", ":")), file=sys.stderr, flush=True)
        return
    import asyncio

    from .bridge import Bridge
    from .transport import IPCServer

    adapter = configured_adapter(args.config, args.source, publisher_factories=publisher_factories)
    bridge = Bridge(adapter)
    if args.command == "bridge":
        await bridge.serve(await stdio_channel())
    else:
        server = None
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        for selected in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(selected, stopped.set)
        try:
            # Socket publication may yield. Install shutdown ownership before
            # a supervisor can observe and stop the new endpoint.
            server = await IPCServer(args.socket, bridge.serve).start()
            await stopped.wait()
        finally:
            if server is not None:
                await server.close()
            for selected in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(selected)


def main(*, publisher_factories=None):
    # Catalog polling is a stdlib authority operation. Loading the state SDK
    # here would add its dependency import cost to every catalog recheck.
    if len(sys.argv) > 1 and sys.argv[1] == "mesh":
        from .authority_cli import main as authority_main
        return authority_main(sys.argv[2:])
    publisher_factories = publisher_factory_map(publisher_factories)
    import asyncio

    parser = argparse.ArgumentParser(description="Mesh Plus experimental cached-state transport")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("mesh", help="Host Mesh authority: list/report-route --json")
    diagnostic = commands.add_parser("doctor", help="inspect packages and optional source config without contacting hosts")
    diagnostic.add_argument("--config", type=Path)
    diagnostic.add_argument("--source")
    diagnostic.add_argument("--sdk", action="store_true", help="explicit SDK/interface diagnostics v2")
    diagnostic = commands.add_parser("probe", help="explicit cached-state IPC or catalog SSH probe; no health writes")
    diagnostic.add_argument("--domain", choices=("tmux", "agent"), required=True)
    diagnostic.add_argument("--host", required=True)
    diagnostic.add_argument("--source", required=True)
    diagnostic.add_argument("--socket", type=Path, help="local IPC; omit for an explicit remote catalog host")
    diagnostic.add_argument("--mode", choices=("snapshot", "subscribe"), default="snapshot")
    diagnostic.add_argument("--timeout-ms", type=int, choices=range(1, 60001), default=5000, metavar="1..60000")
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
    for name in ("read", "watch", "assess"):
        command = commands.add_parser(name)
        command.add_argument("--domain", choices=("tmux", "agent"), required=True)
        command.add_argument("--authority", choices=("ssh-plus", "mesh"), default="ssh-plus")
        command.add_argument("--source", required=True)
        command.add_argument("--socket", type=Path, required=True, help="local Mesh bridge IPC endpoint")
        command.add_argument("--scope", choices=("local", "fleet", "hosts"), default="fleet")
        command.add_argument("--hosts", nargs="*", default=[])
        command.add_argument("--local-host", help="explicit standalone local identity; bypass Host Mesh authority")
        if name == "assess":
            command.add_argument("--mode", choices=("snapshot", "subscribe"), default="snapshot")
            command.add_argument("--timeout-ms", type=int, choices=range(1, 60001), default=5000, metavar="1..60000")
        else:
            command.add_argument("--metrics", action="store_true", help="emit final local transport counters on stderr")
    args = parser.parse_args()
    if args.command == "doctor" and bool(args.config) != bool(args.source):
        parser.error("doctor --config and --source must be supplied together")
    try:
        return asyncio.run(run(args, publisher_factories=publisher_factories)) or 0
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
