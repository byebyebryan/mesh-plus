"""Owned runtime-only peer-specific trial rules, with explicit reversible receipts."""

import argparse
import json
import subprocess
from pathlib import Path

IPS = {"snap": "100.70.82.105", "starship": "100.84.31.64"}


def command(*args):
    return subprocess.run(["sudo", "-n", "firewall-cmd", *args], capture_output=True, text=True, timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "remove", "check"))
    parser.add_argument("--host", choices=("snap", "starship"), required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    peer = "starship" if args.host == "snap" else "snap"
    rule = f'rule family="ipv4" source address="{IPS[peer]}/32" destination address="{IPS[args.host]}/32" port port="9443-9444" protocol="tcp" accept'
    if args.action == "install":
        if args.receipt.exists():
            raise ValueError("receipt_already_exists")
        selected = command("--get-zone-of-interface=tailscale0")
        zone = selected.stdout.strip()
        if selected.returncode != 0 or zone in ("", "no zone"):
            selected = command("--get-default-zone")
            if selected.returncode:
                raise RuntimeError("firewall_zone_unavailable")
            zone = selected.stdout.strip()
        before = command("--zone=" + zone, "--query-rich-rule=" + rule)
        if before.returncode not in (0, 1):
            raise RuntimeError("firewall_query_failed")
        owned = before.returncode == 1
        if owned:
            added = command("--zone=" + zone, "--add-rich-rule=" + rule, "--timeout=21600")
            if added.returncode:
                raise RuntimeError("firewall_install_failed")
        if command("--zone=" + zone, "--query-rich-rule=" + rule).returncode:
            raise RuntimeError("firewall_rule_not_active")
        data = {"host": args.host, "peer": peer, "zone": zone, "rule": rule, "owned": owned,
                "runtimeOnly": True, "timeoutSeconds": 21600, "permanentChanged": False}
        args.receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(data, indent=2) + "\n")
        args.receipt.chmod(0o600)
    else:
        data = json.loads(args.receipt.read_text())
        if data["host"] != args.host or data["rule"] != rule:
            raise ValueError("firewall_receipt_binding")
        if args.action == "remove" and data["owned"]:
            active = command("--zone=" + data["zone"], "--query-rich-rule=" + rule)
            if active.returncode == 0:
                removed = command("--zone=" + data["zone"], "--remove-rich-rule=" + rule)
                if removed.returncode:
                    raise RuntimeError("firewall_removal_failed")
            if command("--zone=" + data["zone"], "--query-rich-rule=" + rule).returncode != 1:
                raise RuntimeError("firewall_rule_remains")
    print(json.dumps({"host": args.host, "step": args.action, "owned": data["owned"], "zone": data["zone"], "runtimeOnly": True}))


if __name__ == "__main__":
    main()
