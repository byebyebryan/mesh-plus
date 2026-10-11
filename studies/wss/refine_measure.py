"""Decision-driving repeat after carrier review, with explicit sampler cost."""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from mesh_plus.testing.ssh_carrier import _stop

STUDY = Path(__file__).resolve().parent
OUTPUT = Path("/tmp/mesh-wss-study/refinement")


def inputs():
    return {name: hashlib.sha256((STUDY / name).read_bytes()).hexdigest() for name in
            ("carrier.py", "configuration.py", "fixtures.py", "node.py", "measure.py", "refine_measure.py")}


async def main():
    OUTPUT.mkdir(exist_ok=True)
    captured = inputs()
    results = []
    selection = [(domain, carrier, "four") for domain in ("tmux", "agent")
                 for carrier in ("ssh", "wss", "wss", "ssh")]
    selection += [(domain, "ipc", "idle") for domain in ("tmux", "agent")]
    for domain, carrier, scenario in selection:
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(STUDY / "measure.py"), "--worker", "--domain", domain,
            "--carrier", carrier, "--scenario", scenario, "--seconds", "30", "--sampling-seconds", ".5",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 70)
            if process.returncode:
                raise RuntimeError(stderr.decode()[-4096:])
            if inputs() != captured:
                raise RuntimeError("study_inputs_changed_during_measurement")
            result = json.loads(stdout)
            result["order"] = len(results) + 1
            results.append(result)
            (OUTPUT / "runs.json").write_text(json.dumps(results, indent=2) + "\n")
            print(f"{len(results)}/10 {domain} {scenario} {carrier} passed", flush=True)
        finally:
            await _stop(process)
    report = {"format": "mesh-plus.wss-study.refinement-measurement.v1", "status": "passed",
              "studyInputs": captured, "runs": 10, "remoteABBARuns": 8, "trueLocalIPCReferences": 2,
              "steadySeconds": 30, "samplingSeconds": .5,
              "scope": "four independent persistent publishers, full native validators/proofs; true local IPC separately",
              "cpuCaveat": "Sampler CPU is separately measured/subtracted from worker CPU; loop scheduling overhead remains",
              "byteCaveat": "Raw WebSocket counters are framing queued before TLS, not encrypted or NIC bytes",
              "excluded": ["WAN", "physical suspend", "TLS/NIC bytes", "global RSS bound", "tail latency"]}
    (OUTPUT / "measurement.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
