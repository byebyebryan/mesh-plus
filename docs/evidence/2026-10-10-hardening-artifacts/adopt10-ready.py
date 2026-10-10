"""Scoped paired adoption with a captured headless/desktop topology and rollback.

Controls contain private bytes and stay outside the evidence repository.
"""

import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import signal
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=["capture", "select", "restore", "recover"])
parser.add_argument("--host", choices=["snap", "starship"], required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--baseline-source", type=Path, required=True)
parser.add_argument("--work", type=Path, required=True)
args = parser.parse_args()
home = Path.home()
work = args.work
work.mkdir(mode=0o700, parents=True, exist_ok=True)


def load(source):
    loader = importlib.machinery.SourceFileLoader(
        "owned_ops_" + source.name, str(source / "scripts/tmux-observer-operations")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


current = load(args.source)
old = load(args.baseline_source)


def selection(source):
    return json.loads((source / "docs/tmux-observer-operations-tuple.json").read_text())


def run(argv, label, timeout=180):
    result = subprocess.run(argv, capture_output=True, timeout=timeout)
    (work / (label + ".log")).write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, label + " failed; private log retained"
    return result.stdout


def active(unit):
    return (
        subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True).stdout.strip()
        == b"active"
    )


def incarnation(unit):
    pid = int(subprocess.check_output(["systemctl", "--user", "show", unit, "-p", "MainPID", "--value"]))
    return {
        "pid": pid,
        "birth": Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19] if pid else None,
    }


def tree_digest(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file() and p.suffix in {".py", ".json"} and "__pycache__" not in p.parts
    }


def protected():
    operations = json.loads((args.baseline_source / "docs/agent-observer-operations-tuple.json").read_text())
    files = [
        ".config/systemd/user/agent-observer.service",
        ".config/mesh-plus/sources.toml",
        ".config/kitty/kitty.conf",
        ".config/niri/config.kdl",
        ".config/niri/dms/binds.kdl",
        ".local/bin/agent-observer-write",
        ".config/agent-observer/workspace.json",
    ]
    return {
        "controls": {name: old.node(home / name) for name in files},
        "collector": incarnation("agent-observer.service"),
        "collectorBytes": tree_digest(home / operations["prefix"]),
        "writerBytes": tree_digest(home / operations["writerPrefix"]),
    }


def foreign_source():
    if args.host != "starship":
        return None
    root = home / ".local/share/chezmoi"
    names = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
        )
        .decode()
        .split("\0")
    )
    rows = {name: old.node(root / name) for name in names if name and (root / name).is_file()}
    # Hash private source bytes rather than exporting their contents.
    return {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip(),
        "statusSha256": hashlib.sha256(
            subprocess.check_output(["git", "status", "--porcelain=v1", "-z"], cwd=root)
        ).hexdigest(),
        "payloadSha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
    }


def verify_payloads(selected):
    for item in [selected["core"], selected["frontend"], *selected["sharedMesh"]["packages"]]:
        for name, value in item["files"].items():
            path = home / item["prefix"] / name
            assert path.is_file() and not path.is_symlink(), name
            raw = path.read_bytes()
            assert len(raw) == value["bytes"] and hashlib.sha256(raw).hexdigest() == value["sha256"], name
            if "executable" in value:
                assert bool(path.stat().st_mode & 0o111) == value["executable"], name


def cached_probe(label):
    with tempfile.TemporaryDirectory(prefix="mesh-adoption-read-", dir=work) as private:
        endpoint = Path(private) / "read.sock"
        log = open(work / (label + "-probe-server.log"), "wb")
        process = subprocess.Popen(
            [
                str(home / ".local/bin/mesh-plus"),
                "serve",
                "--source",
                "tmux_default",
                "--socket",
                str(endpoint),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 10
            while not endpoint.exists():
                assert process.poll() is None, "owned probe exited before publication"
                assert time.monotonic() < deadline, "owned probe socket deadline"
                time.sleep(0.05)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.settimeout(3)
                peer.connect(str(endpoint))
                pid, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                assert pid == process.pid and uid == os.getuid(), "owned IPC peer mismatch"
            frames = []
            for scope in ["local", "fleet"]:
                frame = json.loads(
                    run(
                        [
                            str(home / ".local/bin/mesh-plus"),
                            "read",
                            "--domain",
                            "tmux",
                            "--source",
                            "tmux_default",
                            "--socket",
                            str(endpoint),
                            "--scope",
                            scope,
                        ],
                        label + "-cached-" + scope,
                        timeout=40,
                    )
                )
                assert frame["mesh"]["status"] == "complete", "cached delivery incomplete"
                frames.append(
                    {"scope": scope, "hosts": len(frame["mesh"]["hosts"]), "rows": len(frame["sessions"])}
                )
            return {"state": "passed", "kernelPeerMatches": True, "cachedReads": frames}
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
            log.close()
            assert process.returncode == 0, "owned probe cleanup failed"


def verify(source, label, captured):
    verify_payloads(selection(source))
    owner_unit = "tmux-observer-owner@" + args.host + ".service"
    owner_pid = incarnation(owner_unit)["pid"]
    assert owner_pid > 0, "owner process absent"
    # systemd's start reply proves a process exists, not IPC publication.
    # Reuse the reviewed bounded native-ready gate before inspecting its peer.
    owner_frame = current.owner_ready(args.host)
    assert owner_frame["source"]["hostId"] == args.host
    native_endpoint = Path("/run/user") / str(os.getuid()) / "tmux-observer/owner.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(3)
        peer.connect(str(native_endpoint))
        pid, uid, _ = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        assert pid == owner_pid and uid == os.getuid(), "native owner endpoint mismatch"
    argv = Path(f"/proc/{owner_pid}/cmdline").read_bytes().rstrip(b"\0").split(b"\0")
    assert argv[1:] == [
        os.fsencode(home / ".local/share/tmux-observer/bin/tmux-observer"),
        b"owner",
        b"--host-id",
        args.host.encode(),
        b"--local-attachments",
    ], "native owner command differs"
    result = json.loads(
        run([str(source / "scripts/agent-observer-mesh-operations"), "--host", args.host], label + "-agent")
    )
    assert result["status"] == "accepted"
    assert protected() == captured["protected"], "collector/writer/protected controls changed"
    assert foreign_source() == captured["foreignSource"], "foreign managed source changed"
    assert set(captured["nativeReferences"]) <= set(old.native_references()), (
        "preexisting session disappeared"
    )
    if captured["desktopActive"]:
        run(
            [
                str(source / "scripts/tmux-observer-operations"),
                "verify",
                "--host",
                args.host,
                "--output",
                str(work / (label + "-tmux.json")),
            ],
            label + "-tmux",
        )
    else:
        assert not active("tmux-observer-desktop.service"), "headless baseline was changed"
        raw = subprocess.check_output(
            [
                "systemctl",
                "--user",
                "list-units",
                "--type=service",
                "--state=active",
                "--no-legend",
                "--plain",
                "tmux-observer-fleet@*.service",
            ]
        )
        assert not raw.strip(), "a managed desktop context was started in the headless baseline"
        assert active("tmux-observer-owner@" + args.host + ".service")
    probe = cached_probe(label)
    (work / (label + "-summary.json")).write_text(
        json.dumps(
            {
                "state": "passed",
                "host": args.host,
                "desktopServiceGate": captured["desktopActive"],
                "physicalDesktopAcceptance": False,
                "cachedProbe": probe,
                "installedPayloadsVerified": True,
                "collectorWriterAndForeignSourcePreserved": True,
                "nativeReferencesPreserved": True,
                "nativeOwnerKernelPeerMatches": True,
            },
            indent=2,
        )
        + "\n"
    )


def stop_topology(captured, label, *, allow_stopped=False):
    desktop_active = active("tmux-observer-desktop.service")
    assert desktop_active == captured["desktopActive"] or (
        allow_stopped and captured["desktopActive"] and not desktop_active
    ), "desktop activation changed after capture"
    assert subprocess.run(["pgrep", "-x", "rofi"], capture_output=True).returncode == 1, "Rofi is open"
    units = []
    if captured["desktopActive"]:
        units.append("tmux-observer-desktop.service")
    raw = subprocess.check_output(
        [
            "systemctl",
            "--user",
            "list-units",
            "--type=service",
            "--state=active",
            "--no-legend",
            "--plain",
            "tmux-observer-fleet@*.service",
        ],
        text=True,
    )
    units += [line.split()[0] for line in raw.splitlines()]
    assert len(units) <= 2, "unexpected managed desktop topology"
    if not captured["desktopActive"]:
        assert not units, "an uncaptured fleet context appeared"
    units += ["tmux-observer-owner@" + args.host + ".service", "mesh-plus-agent.service"]
    run(["systemctl", "--user", "stop", *units], label + "-stop")


def start_topology(captured, label):
    run(["systemctl", "--user", "daemon-reload"], label + "-reload")
    run(
        [
            "systemctl",
            "--user",
            "start",
            "tmux-observer-owner@" + args.host + ".service",
            "mesh-plus-agent.service",
        ],
        label + "-start",
    )
    if captured["desktopActive"]:
        run(["systemctl", "--user", "start", "tmux-observer-desktop.service"], label + "-desktop")


baseline_file = work / "baseline.json"
controls = old.control_paths(args.host) + [
    ".local/bin/agent-observer",
    ".config/systemd/user/mesh-plus-agent.service",
    ".config/systemd/user/default.target.wants/mesh-plus-agent.service",
]
controls = list(dict.fromkeys(controls))
if args.operation == "capture":
    assert not baseline_file.exists()
    verify_payloads(selection(args.baseline_source))
    captured = {
        "host": args.host,
        "controls": {name: old.node(home / name) for name in controls},
        "payloads": old.capture_payloads(selection(args.baseline_source), baseline_file),
        "protected": protected(),
        "foreignSource": foreign_source(),
        "nativeReferences": old.native_references(),
        "desktopActive": active("tmux-observer-desktop.service"),
    }
    baseline_file.write_text(json.dumps(captured, indent=2) + "\n")
    baseline_file.chmod(0o600)
    verify(args.baseline_source, "baseline", captured)
else:
    captured = json.loads(baseline_file.read_text())
    assert captured["host"] == args.host
    assert protected() == captured["protected"] and foreign_source() == captured["foreignSource"]
    if args.operation == "select":
        actual = {name: old.node(home / name) for name in controls}
        assert actual == captured["controls"], "captured controls have drifted"
        targets = [
            ".local/share/rofi/extensions/tmux-plus",
            ".local/share/mesh-plus/0.1.0a10/python",
            ".local/share/tmux-observer/python",
            ".local/share/tmux-observer/bin/tmux-observer-client",
            ".local/bin/mesh-plus",
            ".local/bin/agent-observer",
            ".config/systemd/user/mesh-plus-agent.service",
            ".config/systemd/user/tmux-observer-owner@.service",
            ".config/systemd/user/tmux-observer-fleet@.service",
        ]
        (home / ".local/share/mesh-plus/0.1.0a10").mkdir(parents=True, exist_ok=True)
        command = ["chezmoi", "--source", str(args.source), "apply", "--force", "--verbose"]
        run([*command, "--dry-run", *[str(home / p) for p in targets]], "select-dry-run")
        assert {name: old.node(home / name) for name in controls} == captured["controls"]
        stop_topology(captured, "select")
        try:
            run([*command, *[str(home / p) for p in targets]], "select-apply")
            start_topology(captured, "select")
            verify(args.source, "selected", captured)
        except BaseException:
            stop_topology(captured, "failed-select", allow_stopped=True)
            actual = {name: old.node(home / name) for name in controls}
            with old.staged_payloads(captured, selection(args.source)) as staged:
                changed = {
                    name: value for name, value in captured["controls"].items() if value != actual[name]
                }
                old.replace_payloads(
                    staged, lambda: old.restore_controls(changed, {name: actual[name] for name in changed})
                )
            verify_payloads(selection(args.baseline_source))
            start_topology(captured, "failed-select-restored")
            verify(args.baseline_source, "failed-select-restored", captured)
            raise
    elif args.operation == "recover":
        verify(args.source, "before-recovery", captured)
        before = (
            incarnation("mesh-plus-agent.service"),
            incarnation("tmux-observer-owner@" + args.host + ".service"),
        )
        stop_topology(captured, "recovery")
        start_topology(captured, "recovery")
        after = (
            incarnation("mesh-plus-agent.service"),
            incarnation("tmux-observer-owner@" + args.host + ".service"),
        )
        assert all(a != b for a, b in zip(before, after)), "service incarnation did not change"
        verify(args.source, "recovered", captured)
        (work / "recovery-incarnations.json").write_text(
            json.dumps({"before": before, "after": after, "physicalSuspendAccepted": False}, indent=2) + "\n"
        )
    else:
        verify(args.source, "before-rollback", captured)
        actual = {name: old.node(home / name) for name in controls}
        stop_topology(captured, "rollback")
        with old.staged_payloads(captured, selection(args.source)) as staged:
            changed = {name: value for name, value in captured["controls"].items() if value != actual[name]}
            selected_controls = {name: actual[name] for name in changed}

            def finalize_restore():
                old.restore_controls(changed, selected_controls)
                try:
                    start_topology(captured, "rollback")
                    verify(args.baseline_source, "restored", captured)
                except BaseException:
                    stop_topology(captured, "failed-rollback", allow_stopped=True)
                    old.restore_controls(selected_controls, changed)
                    raise

            try:
                old.replace_payloads(staged, finalize_restore)
            except BaseException:
                # The helper has reinstated selected trees; controls above
                # have likewise returned to the verified pre-rollback tuple.
                verify_payloads(selection(args.source))
                start_topology(captured, "rollback-selected-recovered")
                verify(args.source, "rollback-selected-recovered", captured)
                raise
print(json.dumps({"state": "passed", "operation": args.operation, "host": args.host}))
