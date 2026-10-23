"""Read-only host metadata census; no native provider query or service mutation."""

import datetime
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path


def command(argv, timeout=8):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"exit": result.returncode, "stdout": result.stdout}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": type(error).__name__}


def file_metadata(path):
    if not path.is_file():
        return {"exists": False}
    return {
        "exists": True,
        "resolved": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def process_identity(pid):
    try:
        root = Path("/proc") / str(pid)
        stat = (root / "stat").read_text().rsplit(")", 1)[1].split()
        prefixes = tuple(
            str(Path.home() / ".local/share" / name) + "/"
            for name in (
                "agent-observer",
                "mesh-plus",
                "tmux-observer",
                "rlcd-agent-dashboard",
                "rofi",
                "rofi-agent-plus",
            )
        )
        paths = [
            item.decode(errors="replace")
            for item in (root / "cmdline").read_bytes().split(b"\0")
            if item
            and item.decode(errors="replace").startswith(prefixes)
            and not any(chr(value).isspace() or value < 32 for value in item)
        ]
        return {
            "pid": int(pid),
            "parent": int(stat[1]),
            "startTicks": int(stat[19]),
            "uid": root.stat().st_uid,
            "executable": os.readlink(root / "exe"),
            "comm": (root / "comm").read_text().strip(),
            "artifactPaths": paths[:20],
        }
    except (OSError, ValueError):
        return None


def main():
    home = Path.home()
    result = {
        "observedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "uid": os.getuid(),
        "bootId": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "scope": "Selectors, unit metadata and process identity only; no provider state or device acceptance.",
    }
    names = [
        "mesh-plus",
        "mesh-plus-active",
        "mesh-plus-working-set",
        "mesh-plus-tmux",
        "rofi-ssh-plus",
        "rofi-agent-plus",
        "rofi-agent-plus-host",
        "rofi-tmux-plus",
        "agent-observer",
        "agent-observer-service",
        "agent-observer-write",
        "tmux-observer",
        "tmux-observer-client",
        "rlcd-agent-dashboard",
    ]
    result["selectors"] = {name: file_metadata(home / ".local/bin" / name) for name in names}
    units = command(
        [
            "systemctl",
            "--user",
            "list-units",
            "--all",
            "--no-pager",
            "--output=json",
            "agent-observer*",
            "tmux-observer*",
            "mesh-plus*",
            "rlcd-agent-dashboard*",
        ]
    )
    result["units"] = []
    if units.get("exit") == 0:
        for unit in json.loads(units["stdout"]):
            name = unit["unit"]
            details = command(
                [
                    "systemctl",
                    "--user",
                    "show",
                    name,
                    "--property=MainPID,ActiveState,SubState,FragmentPath,ExecMainStartTimestampMonotonic",
                ]
            )
            properties = dict(
                line.split("=", 1) for line in details.get("stdout", "").splitlines() if "=" in line
            )
            pid = properties.get("MainPID", "0")
            result["units"].append(
                {
                    "unit": name,
                    "properties": properties,
                    "process": process_identity(pid) if pid != "0" else None,
                }
            )
    else:
        result["unitError"] = {k: v for k, v in units.items() if k != "stdout"}
    result["nativeProcesses"] = []
    for root in Path("/proc").iterdir():
        if not root.name.isdigit():
            continue
        try:
            if root.stat().st_uid != os.getuid():
                continue
            executable = os.readlink(root / "exe")
            if Path(executable).name not in {"codex", "claude", "tmux"}:
                continue
            identity = process_identity(root.name)
            if identity:
                result["nativeProcesses"].append(identity)
        except OSError:
            continue
    result["nativeProcesses"].sort(key=lambda item: item["pid"])
    result["configuration"] = {}
    for rel in [
        ".config/rofi-agent-plus/direct.toml",
        ".config/agent-observer/profiles.toml",
        ".config/rlcd-agent-dashboard/selection.json",
        ".config/rlcd-agent-dashboard/profiles.json",
        ".config/mesh-plus/sources.toml",
    ]:
        path = home / rel
        metadata = file_metadata(path)
        if path.exists() and path.suffix == ".json" and "rlcd" in rel:
            data = json.loads(path.read_text())
            metadata["selection"] = {
                key: value
                for key, value in data.items()
                if key in {"bundle", "python", "dependencies", "manifestSha256", "sourceRevision"}
            }
        result["configuration"][rel] = metadata
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
