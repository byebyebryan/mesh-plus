"""Disposable private certificates and broadcast cached native fixture."""

import asyncio
import hashlib
import json
import os
import ssl
import subprocess
import uuid
from pathlib import Path

from mesh_plus.api import Publication
from mesh_plus.testing.sample import Profile as IndependentProfile

if os.environ.get("MESH_WSS_NATIVE") == "1":
    from mesh_plus.api import ReferenceProfile
else:
    ReferenceProfile = IndependentProfile
from mesh_plus.testing.sample import Publisher


def command(root, *args):
    subprocess.run(["openssl", *args], cwd=root, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=10)


def certificates(root):
    root = Path(root)
    root.chmod(0o700)
    command(root, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
            "-keyout", "ca.key", "-out", "ca.pem", "-subj", "/CN=Mesh study CA", "-days", "1")
    for name in ("server", "client", "rotation", "unknown", "expired"):
        command(root, "req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                "-keyout", name + ".key", "-out", name + ".csr", "-subj", "/CN=" + name)
        (root / "extensions").write_text("subjectAltName=DNS:localhost\nextendedKeyUsage=" +
                                        ("serverAuth" if name == "server" else "clientAuth") + "\n")
        validity = ["-not_before", "20200101000000Z", "-not_after", "20200102000000Z"] if name == "expired" else ["-days", "1"]
        command(root, "x509", "-req", "-in", name + ".csr", "-CA", "ca.pem", "-CAkey", "ca.key",
                "-CAcreateserial", "-out", name + ".pem", *validity, "-extfile", "extensions")
    for path in root.iterdir():
        path.chmod(0o600)


def fingerprint(root, name="client"):
    der = ssl.PEM_cert_to_DER_cert((Path(root) / (name + ".pem")).read_text())
    return hashlib.sha256(der).hexdigest()


def contexts(root, client="client"):
    # Tests can replace paths; configuration layer supplies captured owned bytes.
    from mesh_plus.wss.configuration import tls_context
    root = Path(root)
    server = tls_context(root / "ca.pem", root / "server.pem", root / "server.key", server=True)
    peer = tls_context(root / "ca.pem", root / (client + ".pem"), root / (client + ".key"))
    return server, peer


def write_policy(path, policy):
    path.write_text(json.dumps(policy))
    path.chmod(0o600)


class BroadcastPublisher(Publisher):
    """No collectors. Every watcher has its own bounded replacement mailbox."""

    def __init__(self, domain, host="beta", rows=0):
        super().__init__(domain, host, profile=ReferenceProfile(domain))
        self.domain = domain
        self.mailboxes = set()
        if rows:
            import copy
            template = self.frame["snapshot"]["sessions"][0]
            expanded = []
            for index in range(rows):
                row = copy.deepcopy(template)
                if domain == "tmux":
                    row["sessionId"] = "$" + str(index + 100)
                else:
                    identity = str(uuid.uuid5(uuid.NAMESPACE_DNS, "mesh-study-" + str(index)))
                    row["identity"]["nativeId"] = identity
                    row["nativeIds"] = {key: identity for key in row["nativeIds"]}
                expanded.append(row)
            self.frame["snapshot"]["sessions"] = expanded
        self.codec.inspect_native(self.frame)

    def update(self, *, restart=False):
        self.frame["viewRevision"] += 1
        self.frame["sequence"] += 1
        if restart:
            self.frame["publisherId" if self.domain == "tmux" else "serviceId"] = str(uuid.uuid4())
        for row in self.frame["snapshot"]["sessions"]:
            row["name" if self.domain == "tmux" else "title"] = "revision-" + str(self.frame["viewRevision"])
        self.codec.inspect_native(self.frame)
        for mailbox in self.mailboxes:
            if not mailbox.full():
                mailbox.put_nowait(None)

    def age(self, milliseconds):
        """Rebase a cached fixture into the past, retaining every native lease.

        This is fixture initialization, never publication/traffic renewal. The
        pure native facade must accept the whole shifted frame before dispatch.
        """
        timestamp_keys = {"encodedAt", "startedAt", "finishedAt", "acceptedAt", "expiresAt",
                          "lastAttemptAt", "emittedBoottimeMs", "sampledBoottimeMs", "expiresBoottimeMs"}
        def shift(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in timestamp_keys and type(item) is int:
                        value[key] -= milliseconds
                    else:
                        shift(item)
            elif isinstance(value, list):
                for item in value:
                    shift(item)
        shift(self.frame)
        self.codec.inspect_native(self.frame)

    async def watch(self):
        mailbox = asyncio.Queue(maxsize=1)
        self.mailboxes.add(mailbox)
        self.watchers += 1
        try:
            while True:
                state = self.codec.inspect_native(self.frame)
                yield Publication(self.wrap(), state.publisher, {"revision": self.frame["viewRevision"]})
                await mailbox.get()
        finally:
            self.watchers -= 1
            self.mailboxes.remove(mailbox)
