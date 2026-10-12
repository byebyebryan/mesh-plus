"""Read-only host inventory for planning an isolated WSS fleet trial.

No provider collection, socket contact, credentials, route reports or service changes.
May be streamed to an explicitly selected host over existing authenticated SSH.
"""

import argparse
import datetime
import json
import os
import pathlib
import shutil
import socket
import subprocess


def run(argv):
    try:
        process = subprocess.run(argv, capture_output=True, text=True, timeout=8)
        if process.returncode == 0:
            return process.stdout.strip()
        return {"error": "command_failed", "returncode": process.returncode}
    except (OSError, subprocess.TimeoutExpired):
        return {"error": "unavailable_or_timeout"}


def decoded(argv):
    value = run(argv)
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"error": "invalid_json"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-id", choices=("snap", "starship"), required=True)
    args = parser.parse_args()
    home = pathlib.Path.home()
    summary = {"hostId": args.host_id, "hostname": socket.gethostname(), "uid": os.getuid(),
               "checkedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "scope": "read-only inventory; no WSS reachability or native acceptance",
               "python": run(["python3", "--version"]), "openssl": run(["openssl", "version"]),
               "meshExecutable": shutil.which("mesh-plus"), "ports": {}, "tailnet": None,
               "lanCandidates": [], "selected": {}, "units": {}}
    for port in (9443, 9444):
        summary["ports"][str(port)] = run(["ss", "-H", "-ltn", f"sport = :{port}"])
    if shutil.which("tailscale"):
        status = decoded(["tailscale", "status", "--json"])
        if isinstance(status, dict) and "Self" in status:
            summary["tailnet"] = {k: status["Self"].get(k) for k in
                                  ("HostName", "DNSName", "TailscaleIPs", "Online")}
        else:
            summary["tailnet"] = status
    routes, addresses = decoded(["ip", "-json", "route", "show", "default"]), decoded(["ip", "-json", "address"])
    if isinstance(routes, list) and isinstance(addresses, list):
        interfaces = {route.get("dev") for route in routes}
        summary["lanCandidates"] = [{"interface": item["ifname"], "address": a["local"], "prefixLength": a["prefixlen"]}
                                     for item in addresses if item.get("ifname") in interfaces
                                     for a in item.get("addr_info", []) if a.get("scope") == "global" and a.get("family") == "inet"]
    for name in ("agent-observer", "tmux-observer"):
        path = home / ".local/share/chezmoi/deployments" / (name + ".json")
        if not path.exists():
            summary["selected"][name] = {"error": "manifest_missing"}
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            summary["selected"][name] = {"error": "manifest_unavailable"}
            continue
        if name == "agent-observer":
            summary["selected"][name] = {k: data.get(k) for k in ("version", "prefix", "readerPrefix")}
        else:
            summary["selected"][name] = {"observerVersion": data.get("core", {}).get("version"),
                "bridgeVersion": data.get("sharedMesh", {}).get("version"),
                "readerSdk": data.get("sharedMesh", {}).get("readerSdk", {}).get("version")}
    for unit in ("mesh-plus-agent.service", "agent-observer.service", f"tmux-observer-owner@{args.host_id}.service"):
        summary["units"][unit] = run(["systemctl", "--user", "show", unit, "--property=LoadState,ActiveState,SubState"])
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
