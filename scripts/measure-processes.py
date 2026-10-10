"""Measure independent Reader processes against one immutable private replay.

Each worker owns its connections and carrier fixture. Reports contain aggregate
metrics only. Simultaneous RSS is sampled from the coordinator's owned tree;
remote SSH publishers and daemon fixtures are included only when descendants.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import signal
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("profile_fleet", ROOT / "profile-fleet.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


async def run(args):
    workers, communication, reports = [], [], []
    peak_rss = peak_processes = 0
    with tempfile.TemporaryDirectory(prefix="mesh-process-measure-") as name:
        try:
            for index in range(args.processes):
                command = [
                    sys.executable,
                    str(ROOT / "measure-reader.py"),
                    "--case",
                    "--readers",
                    "1",
                    "--domain",
                    args.domain,
                    "--carrier",
                    args.carrier,
                    "--frame",
                    str(args.frame),
                    "--seconds",
                    str(args.seconds),
                    "--proof-interval",
                    str(args.proof_interval),
                ]
                command += ["--operation", args.operation]
                if args.updates:
                    command.append("--updates")
                output = Path(name) / f"worker-{index}.json"
                with output.open("wb") as stdout:
                    worker = await asyncio.create_subprocess_exec(
                        *command, stdout=stdout, stderr=asyncio.subprocess.PIPE, start_new_session=True
                    )
                workers.append(worker)
                reports.append(output)
                communication.append(asyncio.create_task(worker.communicate()))

            async def sample():
                nonlocal peak_rss, peak_processes
                while not all(task.done() for task in communication):
                    tree = profile.process_tree()
                    peak_rss = max(peak_rss, sum(row["rssBytes"] for row in tree.values()))
                    peak_processes = max(peak_processes, len(tree))
                    await asyncio.sleep(0.02)

            await asyncio.wait_for(asyncio.gather(*communication, sample()), args.seconds + 60)
            if any(worker.returncode for worker in workers):
                raise RuntimeError("independent_worker_failed")
            result = {
                "format": "mesh-plus.independent-readers.v1",
                "state": "passed",
                "processes": args.processes,
                "sampledPeakOwnedRssBytes": peak_rss,
                "sampledPeakOwnedProcesses": peak_processes,
                "workers": [json.loads(path.read_bytes()) for path in reports],
                "inputSha256": hashlib.sha256(args.frame.read_bytes()).hexdigest(),
                "harnessDigests": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (Path(__file__), ROOT / "measure-reader.py", ROOT / "profile-fleet.py")
                },
                "runtimeDigests": {
                    str(path.relative_to(Path(profile.mesh_plus.__file__).parent)): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in sorted(Path(profile.mesh_plus.__file__).parent.rglob("*"))
                    if path.suffix in {".py", ".json"}
                },
                "limits": [
                    "Independent processes; each owns its carrier fixture",
                    "Same private input and cadence; no shared bridge savings comparison",
                    "20ms owned tree RSS includes coordinator/setup; can miss peaks",
                    "Private input data never included; this is replay, not live native truth",
                ],
            }
            args.report.write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps(
                    {"state": "passed", "processes": args.processes, "sampledPeakOwnedRssBytes": peak_rss}
                )
            )
        finally:
            # Give each owned interpreter a chance to close its disposable SSH
            # daemon and bridge before forcing termination of its process group.
            for worker in workers:
                if worker.returncode is None:
                    try:
                        worker.send_signal(signal.SIGINT)
                    except ProcessLookupError:
                        pass
            try:
                await asyncio.wait_for(asyncio.gather(*(worker.wait() for worker in workers)), 10)
            except TimeoutError:
                for worker in workers:
                    if worker.returncode is None:
                        try:
                            os.killpg(worker.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
            await asyncio.gather(*(worker.wait() for worker in workers))
            await asyncio.gather(*communication, return_exceptions=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=("tmux", "agent"), required=True)
    parser.add_argument("--carrier", choices=("ipc", "ssh"), required=True)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--processes", type=int, choices=(1, 4), required=True)
    parser.add_argument("--seconds", type=int, choices=range(5, 601), default=30)
    parser.add_argument("--proof-interval", type=float, default=3)
    parser.add_argument("--updates", action="store_true")
    parser.add_argument("--operation", choices=("watch", "snapshot"), default="watch")
    parser.add_argument("--report", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
