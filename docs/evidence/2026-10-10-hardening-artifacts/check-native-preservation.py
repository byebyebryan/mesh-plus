"""Passive default-server baseline across actual managed cutover operations.

Private baseline contains server identity and hook definitions; reports contain
only hashes/counts. This tool never creates, renames or kills native sessions.
"""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def native(*arguments):
    environment = dict(os.environ)
    for key in ("TMUX", "TMUX_PANE", "TMUX_TMPDIR"):
        environment.pop(key, None)
    result = subprocess.run(
        ["/usr/bin/tmux", "-f", "/dev/null", "-L", "default", *arguments],
        env=environment,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, "passive native command failed"
    assert len(result.stdout) <= 1024 * 1024, "native output exceeds fixture bound"
    return result.stdout.decode().strip()


def generation():
    return [native("display-message", "-p", field) for field in ("#{start_time}", "#{pid}", "#{socket_path}")]


def snapshot(host):
    identity = generation()
    assert all(identity), "native generation absent"
    references = {}
    for line in native("list-sessions", "-F", "#{session_id}|#{session_created}").splitlines():
        session, created = line.split("|")
        assert session.startswith("$") and session[1:].isdigit(), "invalid session reference"
        assert session not in references, "duplicate native reference"
        references[session] = int(created)
    assert references, "ordinary default server has no references"
    hooks = {"global": native("show-hooks", "-g")}
    hooks.update({session: native("show-hooks", "-t", session) for session in references})
    assert generation() == identity, "native server changed during capture"
    return {
        "hostId": host,
        "bootId": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "generation": identity,
        "references": references,
        "hooks": hooks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("capture", "verify"))
    parser.add_argument("--host", choices=("snap", "starship"), required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    assert args.baseline.resolve() != args.report.resolve(), "report must not overwrite baseline"
    current = snapshot(args.host)
    if args.operation == "capture":
        # Exclusive creation keeps historical baseline inputs immutable.
        descriptor = os.open(args.baseline, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps(current, indent=2) + "\n")
        baseline = current
    else:
        baseline = json.loads(args.baseline.read_text())
        for key in ("hostId", "bootId", "generation"):
            assert current[key] == baseline[key], "native server identity changed"
        assert all(
            current["references"].get(session) == created
            for session, created in baseline["references"].items()
        ), "native reference lost or replaced"
        assert all(current["hooks"].get(key) == value for key, value in baseline["hooks"].items()), (
            "preexisting global or session hooks changed"
        )
    report = {
        "state": "passed",
        "hostId": args.host,
        "operation": args.operation,
        "scope": "passive ordinary default server; no native mutation or GUI input",
        "baselineSha256": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "generationSha256": digest(current["generation"]),
        "baselineSessions": len(baseline["references"]),
        "currentSessions": len(current["references"]),
        "addedReferences": len(current["references"]) - len(baseline["references"]),
        "globalAndPreexistingSessionHooksPreserved": True,
        "generationPreserved": True,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
