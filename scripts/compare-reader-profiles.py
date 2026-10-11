"""Sequential fresh-process ABBA comparison; descriptive, never a perf gate."""

import argparse
import hashlib
import importlib.metadata
import json
import statistics
import subprocess
import sys
from pathlib import Path

import mesh_plus

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, choices=range(5, 61), default=5)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    samples = []
    for domain in ("tmux", "agent"):
        for carrier in ("ipc", "ssh"):
            for scenario, readers, rows, updates, fault in (
                ("idle", 1, 0, False, False), ("multi-update", 4, 0, True, False),
                ("large-update", 1, 256, True, False), ("recovery", 1, 0, True, True),
            ):
                for order, kind in enumerate(("reference", "independent", "independent", "reference")):
                    command = [sys.executable, "-B", str(ROOT / "scripts/measure-reader.py"), "--case",
                               "--domain", domain, "--carrier", carrier, "--seconds", str(args.seconds),
                               "--readers", str(readers), "--rows", str(rows), "--profile-kind", kind, "--consumer",
                               *(["--updates"] if updates else []), *(["--fault-cycle"] if fault else [])]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=args.seconds + 45)
                    if result.returncode:
                        args.report.with_suffix(".failed.json").write_text(json.dumps({"completed": samples,
                            "failedCase": {"domain": domain, "carrier": carrier, "scenario": scenario, "order": order}}, indent=2))
                        raise RuntimeError("owned measurement failed; inspect local worker stderr")
                    sample = json.loads(result.stdout)
                    sample.update(scenario=scenario, order=order)
                    samples.append(sample)
                    args.report.with_suffix(".partial.json").write_text(json.dumps(samples, indent=2))
                    print(json.dumps({"completed": len(samples), "domain": domain, "carrier": carrier,
                                      "scenario": scenario, "kind": kind}), flush=True)
    summary = []
    for domain in ("tmux", "agent"):
        for carrier in ("ipc", "ssh"):
            for scenario in ("idle", "multi-update", "large-update", "recovery"):
                item = {"domain": domain, "carrier": carrier, "scenario": scenario}
                for kind in ("reference", "independent"):
                    matched = [s for s in samples if (s["domain"], s["carrier"], s["scenario"], s["profileKind"]) ==
                               (domain, carrier, scenario, kind)]
                    item[kind] = {"cpuMsSamples": [s["steadyWorkerCpuMs"] for s in matched],
                                  "medianCpuMs": statistics.median(s["steadyWorkerCpuMs"] for s in matched),
                                  "consumerMsSamples": [sum(s["consumerValidationMs"]) for s in matched],
                                  "framedBytesSamples": [sum(m["receivedBytes"] + m["sentBytes"] for m in s["readerMetrics"]) for s in matched]}
                summary.append(item)
    package = Path(mesh_plus.__file__).parent
    report = {"format": "mesh-plus.profile-comparison.v1", "status": "passed", "ordering": "ABBA",
              "meshVersion": mesh_plus.__version__, "python": sys.version.split()[0], "steadySeconds": args.seconds,
              "versions": {n: importlib.metadata.version(n) for n in ("tmux-observer", "agent-observer", "jsonschema")},
              "samples": samples, "summary": summary,
              "runtimeDigests": {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(package.rglob("*")) if p.suffix in {".py", ".json"}},
              "harnessDigests": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                 (Path(__file__), ROOT / "scripts/measure-reader.py", ROOT / "scripts/measurement_profiles.py",
                                  ROOT / "scripts/mesh-lab.py", ROOT / "tests/ssh_fixture.py",
                                  ROOT / "tests/test_reader.py", ROOT / "tests/test_reader_runtime.py", ROOT / "tests/test_observer.py")},
              "limits": ["Two samples per profile/scenario; descriptive and insufficient for stable tail percentiles",
                         "Same pinned native facades and fixed fixture bodies, original receipts, no provider collection",
                         "Steady worker CPU excludes publisher SSH descendants; tree samples include setup and can miss peaks",
                         "Consumer timings exclude initial readiness; frame totals include setup/oracle/cleanup",
                         "No candidate-versus-prior-release optimization claim or operational fleet acceptance"]}
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
