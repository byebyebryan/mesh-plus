#!/usr/bin/env python3
"""Local-only Mesh Client/Bridge close-order repro. No network or provider."""
import asyncio
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = Path("/home/bryan/code/mesh-plus-working-set/src").resolve()
VENV314 = Path("/home/bryan/.cache/agent-observer-working-set-20261018/installed-pair-b176ac06-b9e8488e/venv-314/bin/python")
VENV311 = Path("/home/bryan/.cache/agent-observer-working-set-20261018/installed-pair-b176ac06-b9e8488e/venv-311/bin/python")
MARKER = "mesh-close-order-review-child-v1"

def write_new(path, value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)

def proc_identity(pid):
    stat_path = Path(f"/proc/{pid}/stat")
    text = stat_path.read_text()
    tail = text.rsplit(")", 1)[1].strip().split()
    return {"pid": pid, "state": tail[0], "startTimeTicks": tail[19]}

def safe_cleanup(pid, start_time, waitpid_deadline):
    """Reap the owned local grandchild; only signal after PID/start/marker checks."""
    deadline = time.monotonic() + waitpid_deadline
    reaped_status = None
    while time.monotonic() < deadline:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited == pid:
                reaped_status = status
                return {"reaped": True, "waitStatus": status, "cleanupSignal": None}
        except ChildProcessError:
            pass
        try:
            identity = proc_identity(pid)
        except FileNotFoundError:
            return {"reaped": reaped_status is not None, "waitStatus": reaped_status,
                    "cleanupSignal": None, "state": "gone"}
        if identity["startTimeTicks"] != start_time:
            return {"reaped": reaped_status is not None, "waitStatus": reaped_status,
                    "cleanupSignal": None, "state": "pid_reused_guarded"}
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        except FileNotFoundError:
            continue
        if MARKER.encode() not in cmdline:
            return {"reaped": reaped_status is not None, "waitStatus": reaped_status,
                    "cleanupSignal": None, "state": "marker_guard_refused"}
        if identity["state"] in {"Z", "X"}:
            time.sleep(.01)
            continue
        time.sleep(.01)

    cleanup_signal = None
    try:
        identity = proc_identity(pid)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        if identity["startTimeTicks"] == start_time and MARKER.encode() in cmdline:
            if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
                pidfd = os.pidfd_open(pid)
                try:
                    current = proc_identity(pid)
                    current_cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
                    if current["startTimeTicks"] == start_time and MARKER.encode() in current_cmdline:
                        signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                        cleanup_signal = "SIGTERM"
                finally:
                    os.close(pidfd)
            else:
                current = proc_identity(pid)
                if current["startTimeTicks"] == start_time and MARKER.encode() in Path(f"/proc/{pid}/cmdline").read_bytes():
                    os.kill(pid, signal.SIGTERM)
                    cleanup_signal = "SIGTERM"
    except FileNotFoundError:
        pass

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited == pid:
                return {"reaped": True, "waitStatus": status, "cleanupSignal": cleanup_signal}
        except ChildProcessError:
            pass
        try:
            identity = proc_identity(pid)
        except FileNotFoundError:
            return {"reaped": False, "waitStatus": None, "cleanupSignal": cleanup_signal, "state": "gone"}
        if identity["state"] in {"Z", "X"}:
            continue
        time.sleep(.01)

    try:
        identity = proc_identity(pid)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        if identity["startTimeTicks"] == start_time and MARKER.encode() in cmdline:
            if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
                pidfd = os.pidfd_open(pid)
                try:
                    current = proc_identity(pid)
                    current_cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
                    if current["startTimeTicks"] == start_time and MARKER.encode() in current_cmdline:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        cleanup_signal = "SIGKILL"
                finally:
                    os.close(pidfd)
            else:
                current = proc_identity(pid)
                if current["startTimeTicks"] == start_time and MARKER.encode() in Path(f"/proc/{pid}/cmdline").read_bytes():
                    os.kill(pid, signal.SIGKILL)
                    cleanup_signal = "SIGKILL"
    except FileNotFoundError:
        pass

    deadline = time.monotonic() + .5
    while time.monotonic() < deadline:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited == pid:
                return {"reaped": True, "waitStatus": status, "cleanupSignal": cleanup_signal}
        except ChildProcessError:
            pass
        try:
            identity = proc_identity(pid)
        except FileNotFoundError:
            return {"reaped": False, "waitStatus": None, "cleanupSignal": cleanup_signal, "state": "gone"}
        time.sleep(.01)
    return {"reaped": False, "waitStatus": None, "cleanupSignal": cleanup_signal,
            "state": proc_identity(pid)["state"]}

BRIDGE_CODE = r"""
import asyncio
import json
import os
from pathlib import Path
import sys
import gc
gc.disable()
sys.path.insert(0, "/home/bryan/code/mesh-plus-working-set/src")
from mesh_plus.bridge import Bridge
from mesh_plus.protocol import MAX_MESSAGE, check
from mesh_plus.transport import LineChannel

MARKER = "mesh-close-order-review-child-v1"
receipt_root = Path(sys.argv[1]).parent

def start_ticks(pid):
    tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].strip().split()
    return tail[19]

def write_receipt(value):
    name = "bridge-started.json" if value["event"] == "bridge_started" else "bridge-terminal.json"
    target = receipt_root / name
    temporary = target.with_name(target.name + ".tmp." + str(os.getpid()))
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.link(temporary, target)
    os.unlink(temporary)

class Source:
    host = "fixture-host"
    source = "synthetic"
    profile = "mesh-plus.synthetic.state.v1"
    capabilities = ("snapshot",)
    def validate(self, value):
        check(type(value) is dict and type(value.get("value")) is int, "fixture_payload")
    async def snapshot(self, parameters):
        return {"value": 7}

async def pipe_channel():
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_MESSAGE + 1)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer)
    protocol = asyncio.streams.FlowControlMixin(loop=loop)
    transport, protocol = await loop.connect_write_pipe(lambda: protocol, sys.stdout.buffer)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return LineChannel(reader, writer, "client")

async def main():
    channel = await pipe_channel()
    await Bridge(Source()).serve(channel)

terminal = "normal_return"
error_type = None
exit_code = 0
try:
    write_receipt({"event": "bridge_started", "pid": os.getpid(),
                   "startTimeTicks": start_ticks(os.getpid()), "marker": MARKER})
    asyncio.run(main())
except BaseException as error:
    terminal = type(error).__name__
    error_type = type(error).__name__
    exit_code = 1
finally:
    write_receipt({"event": "bridge_terminal", "pid": os.getpid(),
                   "startTimeTicks": start_ticks(os.getpid()), "terminal": terminal,
                   "errorType": error_type, "exitCode": exit_code, "marker": MARKER})
raise SystemExit(exit_code)
"""

RELAY_CODE = r"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

relay_path = Path(sys.argv[1])
bridge_path = Path(sys.argv[2])
delay = float(sys.argv[3])
bridge_code = sys.argv[4]

def write_new(path, value):
    temporary = path.with_name(path.name + ".tmp." + str(os.getpid()))
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.link(temporary, path)
    os.unlink(temporary)

child = subprocess.Popen([sys.executable, "-I", "-B", "-c", bridge_code, str(bridge_path)],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        bufsize=0, close_fds=True)
tail = Path(f"/proc/{child.pid}/stat").read_text().rsplit(")", 1)[1].strip().split()
write_new(bridge_path.parent / "bridge-identity.json",
          {"pid": child.pid, "startTimeTicks": tail[19], "marker": "mesh-close-order-review-child-v1"})

def forward_client():
    try:
        for line in sys.stdin.buffer:
            frame = json.loads(line)
            if frame.get("kind") == "close":
                write_new(relay_path, {"event": "relay_observed_protocol_close",
                                       "frameKind": "close", "lineBytes": len(line),
                                       "lineSha256": hashlib.sha256(line).hexdigest(),
                                       "relayPid": os.getpid(), "forwardDelayMs": int(delay * 1000)})
                if delay:
                    time.sleep(delay)
            child.stdin.write(line)
            child.stdin.flush()
    finally:
        try:
            child.stdin.close()
        except Exception:
            pass

def forward_bridge():
    for line in child.stdout:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()

left = threading.Thread(target=forward_client, daemon=True)
right = threading.Thread(target=forward_bridge, daemon=True)
left.start()
right.start()
left.join()
right.join()
child.wait()
"""

async def run_case(case_dir, delay, barrier):
    import gc
    gc.disable()
    sys.path.insert(0, str(SOURCE_ROOT))
    import importlib.metadata
    from mesh_plus.client import Client
    from mesh_plus.protocol import check
    from mesh_plus.transport import subprocess_channel

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # Linux PR_SET_CHILD_SUBREAPER, this process only.
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    os.chmod(case_dir, 0o700)
    relay_receipt = case_dir / "relay.json"
    bridge_receipt = case_dir / "bridge-terminal.json"
    argv = [sys.executable, "-I", "-B", "-c", RELAY_CODE,
            str(relay_receipt), str(bridge_receipt), str(delay), BRIDGE_CODE]
    channel = await subprocess_channel(argv)
    wrapper_pid = channel.process.pid
    client = None
    request_value = None
    client_error = None
    try:
        client = await Client.connect(channel, host="fixture-host", source="synthetic",
                                      profile="mesh-plus.synthetic.state.v1",
                                      codec=lambda value: check(type(value) is dict and
                                                                type(value.get("value")) is int,
                                                                "fixture_payload"),
                                      required=("snapshot",), timeout=3)
        raw_send = channel.send
        async def send_with_close_barrier(frame):
            sent = await raw_send(frame)
            if frame.get("kind") == "close":
                target = bridge_receipt if barrier == "bridge_terminal" else relay_receipt
                expected_event = "bridge_terminal" if barrier == "bridge_terminal" else "relay_observed_protocol_close"
                limit = time.monotonic() + 2
                while time.monotonic() < limit:
                    if target.exists():
                        observed = json.loads(target.read_text())
                        if observed.get("event") == expected_event:
                            if barrier == "relay_close" and observed.get("frameKind") != "close":
                                raise AssertionError("relay barrier saw non-close frame")
                            return sent
                    await asyncio.sleep(.002)
                raise TimeoutError("close_barrier_timeout")
            return sent
        channel.send = send_with_close_barrier
        request_value = await asyncio.wait_for(client.request(timeout_ms=2000), 3)
        if request_value != {"value": 7}:
            raise AssertionError(f"unexpected snapshot: {request_value!r}")
        await asyncio.wait_for(client.close(), 3)
    except BaseException as error:
        client_error = type(error).__name__
        if client is not None and not channel.closed:
            await asyncio.wait_for(client.close(), 3)
        elif not channel.closed:
            await asyncio.wait_for(channel.close(), 3)

    close_count = 0
    close_bytes = 0
    if client is not None:
        counts = client.inspect()["channel"]["byKind"]["sent"].get("close", {})
        close_count, close_bytes = counts.get("frames", 0), counts.get("bytes", 0)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not bridge_receipt.exists():
        await asyncio.sleep(.01)
    bridge_outcome = None
    if bridge_receipt.exists():
        bridge_outcome = json.loads(bridge_receipt.read_text())

    identity_path = case_dir / "bridge-identity.json"
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not identity_path.exists():
        await asyncio.sleep(.01)
    bridge_identity = json.loads(identity_path.read_text()) if identity_path.exists() else None

    bridge_cleanup = None
    if bridge_identity:
        bridge_cleanup = safe_cleanup(bridge_identity["pid"], bridge_identity["startTimeTicks"], .5)

    relay_event = json.loads(relay_receipt.read_text()) if relay_receipt.exists() else None
    removed_temporary_receipts = []
    for temporary in case_dir.glob("*.tmp.*"):
        if temporary.is_symlink() or not temporary.is_file() or temporary.parent != case_dir:
            raise RuntimeError("unexpected temporary receipt path")
        temporary.unlink()
        removed_temporary_receipts.append(temporary.name)
    result = {
        "case": case_dir.name,
        "barrier": barrier,
        "expectedBridgeTerminal": "normal_return",
        "delayMs": int(delay * 1000),
        "python": sys.version,
        "meshMetadataDistributionVersion": importlib.metadata.version("mesh-plus"),
        "meshImport": __import__("mesh_plus").__file__,
        "selectedInputRoot": str(SOURCE_ROOT),
        "transportSourceSha256": hashlib.sha256((SOURCE_ROOT / "mesh_plus/transport.py").read_bytes()).hexdigest(),
        "request": request_value,
        "clientErrorType": client_error,
        "clientSentCloseFrames": close_count,
        "clientSentCloseBytes": close_bytes,
        "relayCloseEvent": relay_event,
        "bridgeTerminal": bridge_outcome,
        "wrapperPid": wrapper_pid,
        "wrapperReturnCode": channel.process.returncode,
        "bridgeIdentity": bridge_identity,
        "bridgeCleanup": bridge_cleanup,
        "temporaryReceiptFilesRemoved": removed_temporary_receipts,
        "bounded": {"clientCloseSeconds": 3, "receiptWaitSeconds": 2,
                    "bridgeCleanupWaitSeconds": 2, "relayForwardDelayMs": int(delay * 1000)},
    }
    write_new(case_dir / "case-report.json", result)
    bridge_gone = bridge_cleanup and bridge_cleanup.get("cleanupSignal") is None and (
        bridge_cleanup.get("reaped") or bridge_cleanup.get("state") == "gone")
    if (close_count != 1 or not relay_event or relay_event.get("frameKind") != "close" or
            not bridge_outcome or bridge_outcome.get("terminal") != "normal_return" or
            not bridge_gone or channel.process.returncode != 0):
        raise AssertionError(json.dumps(result, sort_keys=True))
    return result

def controller():
    results_dir = ROOT / "results"
    if not results_dir.exists():
        results_dir.mkdir(mode=0o700)
    if results_dir.is_symlink() or results_dir.stat().st_mode & 0o077:
        raise RuntimeError("results directory permissions or type are unsafe")
    runs = []
    scenarios = [
        ("314", VENV314, "source-defer50ms", 0.05, "relay_close"),
        ("311", VENV311, "source-defer50ms", 0.05, "relay_close"),
    ]
    for version, interpreter, label, delay, barrier in scenarios:
        case_name = f"py{version}-{label}"
        case_dir = results_dir / case_name
        case_dir.mkdir(mode=0o700)
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run(
            [str(interpreter), "-I", "-B", str(Path(__file__).resolve()),
             "--case", str(case_dir), str(delay), barrier],
            env=env, capture_output=True, text=True, timeout=8, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"{case_name} failed ({completed.returncode}): {completed.stderr[-4000:]}")
        runs.append(json.loads(completed.stdout.strip().splitlines()[-1]))

    output = {"format": "mesh-local-close-order-source-repro-v1",
              "recordedAtNs": time.time_ns(),
              "scope": "local subprocess_channel + Client + real Bridge; no SSH/provider/service",
              "source": {"kind": "selected worktree source import",
                         "selectedInputRoot": str(SOURCE_ROOT),
                         "transportSha256": hashlib.sha256((SOURCE_ROOT / "mesh_plus/transport.py").read_bytes()).hexdigest()},
              "installedNegativeBaseline": {"report": "/home/bryan/.cache/agent-observer-working-set-20261018/fixed-ssh-close-order-review-v1/controller-report.json",
                                            "wheelSha256": "1476da94402168b41e8c296044e1579aa3f9584c011d4eca4cddd0106c6cf802"},
              "runs": runs}
    write_new(ROOT / "controller-report.json", output)
    print(json.dumps(output, sort_keys=True))

if __name__ == "__main__":
    if sys.argv[1:] == ["--controller"]:
        controller()
    elif len(sys.argv) == 5 and sys.argv[1] == "--case":
        case_dir = Path(sys.argv[2]).resolve()
        result = asyncio.run(run_case(case_dir, float(sys.argv[3]), sys.argv[4]))
        print(json.dumps(result, sort_keys=True))
    else:
        raise SystemExit("usage: close_order_repro.py --controller | --case DIR DELAY")
