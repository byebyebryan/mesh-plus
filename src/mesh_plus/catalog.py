"""Host Mesh v1 authority boundary; the selected facade uses one shared writer."""

import asyncio
import contextlib
import copy
import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .evidence import digest
from .protocol import check, decode_json


@lru_cache(maxsize=3)
def host_validator(name):
    registry = Registry()
    schemas = {}
    for path in files("mesh_plus").joinpath("schemas").iterdir():
        if path.name.startswith("host-"):
            schema = json.loads(path.read_text())
            schemas[schema["$id"]] = schema
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return Draft202012Validator(schemas[name + ".schema.json"], registry=registry)


class Catalog:
    def __init__(self, payload):
        host_validator("list").validate(payload)
        hosts = payload["hosts"]
        check(sum(host["local"] for host in hosts) == 1 and hosts[0]["local"] and
              hosts[0]["id"] == payload["localHostId"], "catalog_local_host")
        identities = {}
        for host in hosts:
            check(host["id"] == host["id"].lower(), "catalog_canonical_host")
            routes = host["routes"]
            check((not routes) == host["local"], "catalog_routes")
            check(sorted(r["configuredIndex"] for r in routes) == list(range(len(routes))), "catalog_route_indices")
            for token in [host["id"], *host["aliases"], *(r["destination"] for r in routes)]:
                key = token.casefold()
                check(key not in identities or identities[key] == host["id"], "catalog_ambiguous_identity")
                identities[key] = host["id"]
        check(len({host["id"] for host in hosts}) == len(hosts), "catalog_duplicate_host")
        self.payload = copy.deepcopy(payload)
        self.revision = payload["meshRevision"]
        self.local_host = payload["localHostId"]

    @property
    def hosts(self):
        return copy.deepcopy(self.payload["hosts"])

    def select(self, mode="fleet", hosts=()):
        check(mode in {"local", "fleet", "hosts"} and (mode == "hosts") == bool(hosts), "selection_shape")
        if mode == "hosts":
            check(len(hosts) == len(set(hosts)), "duplicate_host")
            known = {host["id"]: host for host in self.hosts}
            check(all(host in known for host in hosts), "unknown_host")
            return [known[host] for host in hosts]
        return [host for host in self.hosts if mode == "fleet" or host["local"]]

    def route_token(self, host_id, route):
        host = next((host for host in self.hosts if host["id"] == host_id), None)
        check(host is not None and route in host["routes"], "catalog_route_binding")
        return digest({"catalogRevision": self.revision, "hostId": host_id, "configuredIndex": route["configuredIndex"]})


async def bounded_command(argv, *, timeout=5):
    process = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def read(stream, maximum):
        data = bytearray()
        while block := await stream.read(min(65536, maximum + 1 - len(data))):
            data.extend(block)
            check(len(data) <= maximum, "catalog_output_capacity")
        return bytes(data)

    tasks = [asyncio.create_task(read(process.stdout, 524288)), asyncio.create_task(read(process.stderr, 65536))]
    try:
        stdout, _stderr = await asyncio.wait_for(asyncio.gather(*tasks), timeout)
        await asyncio.wait_for(process.wait(), timeout)
        check(stdout.endswith(b"\n") and not stdout.endswith(b"\n\n") and not stdout[:-1].endswith((b" ", b"\r")),
              "catalog_framing")
        payload = decode_json(stdout[:-1], 524287)
        if process.returncode != 0:
            host_validator("error").validate(payload)
            raise ValueError(payload["error"]["code"])
        check(payload.get("ok") is not False, "catalog_error_exit")
        return payload
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()


class SSHPlusAuthority:
    def __init__(self, executable="rofi-ssh-plus"):
        self.executable = executable

    async def load(self):
        return Catalog(await bounded_command([self.executable, "mesh", "list", "--json"]))

    async def report_route(self, *, host, route, status, revision, observed_at):
        check(status in {"reachable", "unreachable"} and type(observed_at) is int and observed_at >= 0, "route_report")
        payload = await bounded_command([self.executable, "mesh", "report-route", "--json", "--host", host,
                                         "--route", route, "--status", status, "--source", "mesh-plus",
                                         "--mesh-revision", revision, "--observed-at", str(observed_at)])
        host_validator("report-route").validate(payload)
        return payload["accepted"]


class MeshAuthority(SSHPlusAuthority):
    """Explicit native authority selection using the same bounded process API."""

    def __init__(self, executable="mesh-plus"):
        super().__init__(executable)
