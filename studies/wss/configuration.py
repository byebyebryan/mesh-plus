"""Draft immutable endpoint binding and bounded owned configuration snapshots."""

import asyncio
import os
import re
import ssl
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from carrier import endpoint_url
from jsonschema import Draft202012Validator

from mesh_plus.evidence import digest
from mesh_plus.protocol import check, decode_json
from mesh_plus.reader import Reader
from mesh_plus.transport import boottime_ms, within_deadline

BINDING = "mesh-plus.wss-study.v1"


@dataclass(frozen=True)
class ServerConfiguration:
    paths: tuple
    material: tuple
    policy_path: Path
    context: object

    @classmethod
    def load(cls, ca, certificate, key, policy_path):
        paths = tuple(Path(p) for p in (ca, certificate, key))
        material = tuple(snapshot(p) for p in paths)
        context = tls_context(None, None, None, server=True, captured=material)
        check(material == tuple(snapshot(p) for p in paths), "wss_configuration_changed")
        return cls(paths, material, Path(policy_path), context)

    async def authorize(self):
        def capture():
            check(self.material == tuple(snapshot(p) for p in self.paths), "wss_configuration_changed")
            return decode_json(snapshot(self.policy_path), 1048576)
        return await within_deadline(asyncio.to_thread(capture), boottime_ms() + 5000)


def snapshot(path, maximum=1048576):
    path = Path(path)
    check(path.is_absolute() and path.parent.resolve() == path.parent, "wss_configuration_path")
    parent = path.parent.lstat()
    check(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and parent.st_mode & 0o077 == 0,
          "wss_configuration_directory")
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        anchor = os.fstat(parent_fd)
        check((anchor.st_dev, anchor.st_ino) == (parent.st_dev, parent.st_ino), "wss_configuration_changed")
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        node = os.fstat(fd)
        check(stat.S_ISREG(node.st_mode) and node.st_uid == os.getuid() and node.st_mode & 0o077 == 0 and
              node.st_size <= maximum, "wss_configuration_policy")
        raw = os.read(fd, maximum + 1)
        check(len(raw) <= maximum, "wss_configuration_capacity")
        after = os.fstat(fd)
        check((node.st_size, node.st_mtime_ns, node.st_ctime_ns) ==
              (after.st_size, after.st_mtime_ns, after.st_ctime_ns) and len(raw) == after.st_size,
              "wss_configuration_changed")
        return raw
    finally:
        os.close(fd)


def tls_context(ca, certificate, key, *, server=False, captured=None):
    # Capture all bytes first. SSLContext never reopens caller-controlled paths.
    material = captured or tuple(snapshot(path) for path in (ca, certificate, key))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    if not server:
        context.check_hostname = True
    context.load_verify_locations(cadata=material[0].decode("ascii"))
    with tempfile.TemporaryDirectory(prefix="mesh-wss-credentials-") as name:
        root = Path(name)
        for filename, data in zip(("cert.pem", "key.pem"), material[1:], strict=True):
            fd = os.open(root / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
        context.load_cert_chain(root / "cert.pem", root / "key.pem")
    return context


async def policy_file(path):
    return await within_deadline(asyncio.to_thread(lambda: decode_json(snapshot(path), 1048576)),
                                 boottime_ms() + 5000)


@dataclass(frozen=True)
class Binding:
    host: str
    source: str
    profile: str
    url: str
    endpoint_index: int
    selection_revision: str

    @property
    def token(self):
        return digest({"bindingProtocol": BINDING, "selectionRevision": self.selection_revision,
                       "hostId": self.host, "endpointIndex": self.endpoint_index})


@dataclass(frozen=True)
class Selection:
    """One composition owner; private key changes revoke but never enter tokens."""

    paths: tuple
    bindings: tuple
    key_bytes: bytes
    context: object

    @classmethod
    def load(cls, catalog_path, registry_path, ca_path, certificate_path, key_path):
        paths = tuple(Path(p) for p in (catalog_path, registry_path, ca_path, certificate_path, key_path))
        raw = tuple(snapshot(p) for p in paths)
        from mesh_plus.catalog import Catalog
        catalog = Catalog(decode_json(raw[0], 1048576))
        registry = decode_json(raw[1], 1048576)
        # Public inputs only, explicitly not the private key or route health.
        trust_revision = digest({"ca": raw[2].decode("ascii"), "certificate": raw[3].decode("ascii")})
        bindings = resolve(catalog, registry, trust_revision)
        context = tls_context(None, None, None, captured=raw[2:])
        check(raw == tuple(snapshot(p) for p in paths), "wss_configuration_changed")
        return cls(paths, bindings, raw[4], context)

    async def check(self):
        def current():
            candidate = Selection.load(*self.paths)
            check(candidate.key_bytes == self.key_bytes, "scope_changed")
            return candidate.bindings[0].selection_revision
        return await within_deadline(asyncio.to_thread(current), boottime_ms() + 5000)


def resolve(catalog, registry, trust_revision):
    schema = decode_json((Path(__file__).parent / "registry.schema.json").read_bytes())
    Draft202012Validator(schema).validate(registry)
    check(set(registry) == {"protocol", "endpoints"} and registry["protocol"] == BINDING,
          "wss_registry")
    endpoints = registry["endpoints"]
    check(type(endpoints) is list and 1 <= len(endpoints) <= 16, "wss_registry_capacity")
    known = {h["id"] for h in catalog.hosts if not h["local"]}
    revision = digest({"bindingProtocol": BINDING, "hostMeshRevision": catalog.revision,
                       "registry": registry, "trustRevision": trust_revision})
    result = []
    for index, entry in enumerate(endpoints):
        check(set(entry) == {"hostId", "sourceId", "profile", "url", "product", "capabilities"},
              "wss_registry_entry")
        check(entry["hostId"] in known and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", entry["sourceId"]),
              "wss_registry_scope")
        check(entry["product"] == "state" and entry["capabilities"] == ["snapshot", "proof", "subscribe"] and
              entry["profile"] in {"tmux-observer.mesh-candidate.v1", "agent-observer.mesh-candidate.v1"},
              "wss_registry_product")
        endpoint_url(entry["url"])
        result.append(Binding(entry["hostId"], entry["sourceId"], entry["profile"], entry["url"], index, revision))
    check(len({b.host for b in result}) == len(result), "wss_registry_duplicate_host")
    return tuple(result)


class StudyReader(Reader):
    """Explicit immutable backend specialization, never inferred from Client."""

    def __init__(self, *args, bindings, **kwargs):
        self.backends = MappingProxyType({b.host: b for b in bindings})
        super().__init__(*args, **kwargs)
        for endpoint in self.endpoints:
            if endpoint.host in self.backends:
                binding = self.backends[endpoint.host]
                check(not endpoint.local and endpoint.route_token == binding.token and
                      self.catalog_revision == binding.selection_revision and
                      self.profile.descriptor.profile_id == binding.profile and
                      (endpoint.codec is None or endpoint.codec.source == binding.source), "wss_reader_binding")

    async def _connect(self, endpoint):
        if self.catalog_check:
            revision = await within_deadline(self.catalog_check(), boottime_ms() + 5000)
            check(revision == self.catalog_revision, "scope_changed")
        return await super()._connect(endpoint)

    def _label(self, host):
        if host["hostId"] in self.backends:
            host["delivery"]["path"] = "wss"
            host["delivery"]["routeToken"] = self.backends[host["hostId"]].token
        return host

    def unavailable(self, *args, **kwargs):
        return self._label(super().unavailable(*args, **kwargs))

    async def read_host(self, *args, **kwargs):
        host, rows = await super().read_host(*args, **kwargs)
        return self._label(host), rows

    async def snapshot(self, *args, **kwargs):
        # SDK v1 does not check catalog authority before poll dispatch. This
        # isolated proposal checks composition revision before opening any source.
        if self.catalog_check:
            revision = await within_deadline(self.catalog_check(), boottime_ms() + 5000)
            check(revision == self.catalog_revision, "scope_changed")
        return await super().snapshot(*args, **kwargs)

    def inspect(self):
        result = super().inspect()
        result["byteScope"] = "completed-json-messages" if len(self.backends) == len(self.endpoints) else "mixed"
        return result
