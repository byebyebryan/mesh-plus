"""Dedicated private trial credentials; signing key stays on its issuing host."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

IPS = {"snap": "100.70.82.105", "starship": "100.84.31.64"}
DNS = {"snap": "snap.tail223cf3.ts.net", "starship": "starship.tail223cf3.ts.net"}


def run(args):
    subprocess.run(["openssl", *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def request(root, host):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for label in ("server", "tmux-client", "agent-client"):
        if (root / (label + ".key")).exists():
            raise ValueError("credential_exists")
        run(["req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
             "-keyout", str(root / (label + ".key")), "-out", str(root / (label + ".csr")),
             "-subj", f"/CN=mesh-perf-{host}-{label}"])


def issue(root, host):
    issuer = root / "issuer"
    issuer.mkdir(mode=0o700, exist_ok=True)
    if not (issuer / "ca.pem").exists():
        run(["req", "-new", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
             "-keyout", str(issuer / "ca.key"), "-out", str(issuer / "ca.pem"), "-days", "30",
             "-subj", "/CN=mesh-perf-private-trial-ca", "-addext", "basicConstraints=critical,CA:TRUE",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign"])
    directory = root / host
    for label in ("server", "tmux-client", "agent-client"):
        certificate = directory / (label + ".pem")
        if certificate.exists():
            raise ValueError("certificate_exists")
        extension = directory / (label + ".ext")
        extension.write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n" +
                             (f"extendedKeyUsage=serverAuth\nsubjectAltName=IP:{IPS[host]},DNS:{DNS[host]}\n"
                              if label == "server" else "extendedKeyUsage=clientAuth\n"))
        run(["x509", "-req", "-in", str(directory / (label + ".csr")), "-CA", str(issuer / "ca.pem"),
             "-CAkey", str(issuer / "ca.key"), "-CAcreateserial", "-out", str(certificate), "-days", "7",
             "-extfile", str(extension)])
        run(["verify", "-CAfile", str(issuer / "ca.pem"), str(certificate)])
    (directory / "ca.pem").write_bytes((issuer / "ca.pem").read_bytes())


def configure(root, host):
    peer = "starship" if host == "snap" else "snap"
    # Captured authority catalog is private and unchanged; endpoint selectors remain canonical.
    catalog = subprocess.check_output([str(Path.home() / ".local/bin/mesh-plus"), "mesh", "list", "--json"])
    (root / "catalog.json").write_bytes(catalog)
    for domain, port in (("tmux", 9443), ("agent", 9444)):
        source = "tmux_default" if domain == "tmux" else "agent"
        profile = domain + "-observer.mesh-candidate.v1"
        der = subprocess.check_output(["openssl", "x509", "-in", str(root / ("peer-" + domain + "-client.pem")), "-outform", "DER"])
        (root / (domain + "-authorization.json")).write_text(json.dumps({hashlib.sha256(der).hexdigest(): [host, source, profile]}))
        registry = {"protocol": "mesh-plus.wss.v1", "endpoints": [
            {"hostId": peer, "sourceId": source, "profile": profile,
             "url": f"wss://{IPS[peer]}:{port}/mesh/state", "product": "state",
             "capabilities": ["snapshot", "proof", "subscribe"]}]}
        (root / (domain + "-registry.json")).write_text(json.dumps(registry))
    for path in root.iterdir():
        if path.is_file():
            path.chmod(0o600)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("request", "issue", "configure"))
    parser.add_argument("--host", choices=("snap", "starship"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if not args.root.is_absolute() or args.root.parent.resolve() != args.root.parent:
        parser.error("absolute canonical private root required")
    {"request": request, "issue": issue, "configure": configure}[args.command](args.root, args.host)
    print(json.dumps({"host": args.host, "step": args.command, "status": "prepared"}))


if __name__ == "__main__":
    main()
