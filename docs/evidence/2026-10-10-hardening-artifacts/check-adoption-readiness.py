"""Reject the original peer-before-ready order with an owned unpublished peer."""

import ast
import hashlib
import json
import os
import socket
import struct
import types
from pathlib import Path

root = Path("/tmp/mesh-hardening/adoption")
cases = []
for filename, expected in (("adopt10-pre-readiness-executed.py", "FileNotFoundError"), ("adopt10.py", None)):
    helper = root / filename
    tree = ast.parse(helper.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "verify")
    stop = next(
        index for index, node in enumerate(function.body)
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "result" for target in node.targets)
    )
    function.body = function.body[:stop]
    code = compile(ast.Module(body=[function], type_ignores=[]), str(helper), "exec")
    state = {"ready": False}
    home = root / "owned-readiness-home"
    argv = [b"python", os.fsencode(home / ".local/share/tmux-observer/bin/tmux-observer"), b"owner", b"--host-id", b"snap", b"--local-attachments"]

    def path(value):
        if str(value) == "/proc/1234/cmdline":
            return types.SimpleNamespace(read_bytes=lambda: b"\0".join(argv) + b"\0")
        return Path(value)

    def ready(host):
        state["ready"] = True
        return {"source": {"hostId": host}}

    class Peer:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, seconds):
            pass

        def connect(self, endpoint):
            if not state["ready"]:
                raise FileNotFoundError("owned fixture peer not published")

        def getsockopt(self, *args):
            return struct.pack("3i", 1234, os.getuid(), 0)

    fake_socket = types.SimpleNamespace(
        socket=lambda *args: Peer(), AF_UNIX=socket.AF_UNIX,
        SOCK_STREAM=socket.SOCK_STREAM, SOL_SOCKET=socket.SOL_SOCKET, SO_PEERCRED=socket.SO_PEERCRED,
    )
    namespace = {
        "args": types.SimpleNamespace(host="snap"), "home": home, "Path": path,
        "os": os, "struct": struct, "socket": fake_socket,
        "selection": lambda source: {}, "verify_payloads": lambda selected: None,
        "incarnation": lambda unit: {"pid": 1234}, "current": types.SimpleNamespace(owner_ready=ready),
    }
    exec(code, namespace)
    failure = None
    try:
        namespace["verify"]("owned-source", "owned-check", {})
    except FileNotFoundError:
        failure = "FileNotFoundError"
    assert failure == expected, filename
    cases.append({"input": filename, "helperSha256": hashlib.sha256(helper.read_bytes()).hexdigest(), "expectedFailure": expected, "observedFailure": failure, "readyBeforePeer": state["ready"]})
report = {"state": "passed", "scope": "extracted actual verification prefix; owned unpublished peer, native-ready and PID reads mocked; no native IO or live acceptance", "cases": cases}
(root / "adoption-readiness-owned.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
