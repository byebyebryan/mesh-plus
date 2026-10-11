"""Validate redacted run completeness and summarize descriptive study results."""

import hashlib
import json
import statistics
from pathlib import Path

STUDY = Path(__file__).resolve().parent


def summarize(runs):
    rows = []
    for domain in ("tmux", "agent"):
        for scenario in ("idle", "four", "large", "recovery"):
            for carrier in ("ssh", "wss", "ipc"):
                selected = [v for v in runs if (v["domain"], v["scenario"], v["carrier"]) ==
                            (domain, scenario, carrier)]
                if not selected:
                    continue
                rows.append({"domain": domain, "scenario": scenario, "carrier": carrier, "samples": len(selected),
                             "treeCpuMsMean": statistics.mean(v["sampledTreeCpuMs"] for v in selected),
                             "publisherCpuMsMean": statistics.mean(v["sampledPublisherCpuMs"] for v in selected),
                             "peakTreeRssKiBMean": statistics.mean(v["sampledPeakTreeRssKiB"] for v in selected),
                             "peakProcesses": [v["sampledPeakProcesses"] for v in selected],
                             "workerLessSamplerMsMean": (statistics.mean(v["workerCpuLessSamplerMs"] for v in selected)
                                                         if all("workerCpuLessSamplerMs" in v for v in selected) else None),
                             "loadAverage": [v["loadAverage"] for v in selected]})
    return rows


def main():
    results = STUDY / "results"
    initial = json.loads((results / "runs.json").read_text())
    extra = json.loads((results / "extras.json").read_text())
    refinement = json.loads((results / "refinement-runs.json").read_text())
    assert len(initial) == 32 and len(refinement) == 10
    for group in (initial, refinement[:8]):
        for offset in range(0, len(group), 4):
            assert [v["carrier"] for v in group[offset:offset + 4]] == ["ssh", "wss", "wss", "ssh"]
    for run in initial + refinement:
        assert run["elapsedSeconds"] >= 30 and run["checks"]["baseline"] == run["readers"]
        assert run["cleanup"]["activeReaderConnections"] == 0
        assert run["cleanup"]["publisherProcessesReaped"] == run["readers"]
        assert all(v["cleanupFailures"] == 0 for v in run["metrics"])
        if run["scenario"] != "idle":
            assert run["checks"]["updates"] >= run["readers"]
        if run["scenario"] == "recovery":
            assert run["checks"]["unavailable"] >= 1 and run["checks"]["recoveries"] >= 1
    cold = [v for v in extra if v["scenario"] == "cold"]
    assert len(cold) == 4 and all(len(v["samplesMs"]) == 10 and v["proofs"] == 10 for v in cold)
    assert all(v["reader"]["activeConnections"] == 0 and v["cleanup"]["channelsClosed"] == 10 for v in cold)
    assert all(v["metrics"][0]["byteScope"] == "completed-json-lines" and
               v["metrics"][0]["operations"]["snapshotRequests"] > 0 and
               v["metrics"][0]["operations"]["proofRequests"] == 0 for v in refinement[8:])
    gates = []
    for version in ("311", "313", "314"):
        whole = json.loads((results / ("final-" + version + ".json")).read_text())
        carrier = json.loads((results / ("final-carrier-" + version + ".json")).read_text())
        for gate in (whole, carrier):
            assert gate["status"] == "passed" and not gate["skipped"] and not gate["runtimeDrift"]
        assert whole["testsRun"] == 31 and carrier["testsRun"] == 23
        for name in ("carrier.py", "configuration.py", "fixtures.py", "test_state.py"):
            assert whole["studyInputs"][name] == hashlib.sha256((STUDY / name).read_bytes()).hexdigest()
        assert carrier["studyInputs"]["test_carrier.py"] == hashlib.sha256((STUDY / "test_carrier.py").read_bytes()).hexdigest()
        gates.append({"python": whole["python"], "allStudyCases": 31, "carrierRefreshCases": 23,
                      "stateSourceUnchanged": True, "status": "passed", "skips": 0})
    stress = json.loads((results / "resources.json").read_text())
    assert stress["status"] == "passed" and stress["slowReader"]["peakQueuedFrames"] == 2
    assert stress["oversizedPeer"]["assembledBytes"] == 0 and stress["pendingTLS"]["admitted"] == 4
    assert not any(stress["cleanup"].values())
    report = {"format": "mesh-plus.wss-study.decision.v1", "status": "passed",
              "disposition": "feasible_opt_in_candidate_defer_runtime_promotion",
              "initialABBARuns": 32, "refinedABBARuns": 8, "coldAcquisitions": 40,
              "trueLocalReferences": 2, "initial": summarize(initial), "refinement": summarize(refinement),
              "validation": gates,
              "resources": stress,
              "cold": [{"domain": v["domain"], "carrier": v["carrier"], "samples": 10,
                        "meanMs": statistics.mean(v["samplesMs"]), "medianMs": statistics.median(v["samplesMs"]),
                        "minMs": min(v["samplesMs"]), "maxMs": max(v["samplesMs"])} for v in cold],
              "findings": ["Fewer processes and lower tree RSS in this one-publisher-per-reader WSS fixture",
                           "No demonstrated reduction of consumer full-proof/native validation work",
                           "Initial CPU includes 20ms process-count-dependent sampler overhead",
                           "Refinement subtracts measured sampler CPU, but is descriptive and includes unpinned host load",
                           "Tmux refined runs overlapped cross-Python validation; CPU conclusions remain qualified",
                           "Initial IPC extras are remote-proof emulation, not ordinary local Read acceptance",
                           "True local IPC controls replace that interpretation in the refinement",
                           "The frozen generic JSON parser bounds bytes/depth, not a separate global node count",
                           "No pooling, compact proofs, TLS/NIC-byte or WAN benefit is established"],
              "promotionBlocks": ["Reviewed WSS authority/revision/token contract and lock addendum",
                                  "Opt-in SDK factory and mixed-backend metrics/counter correction",
                                  "Carrier-wide setup and send validation budget review",
                                  "Bounded configuration IO boundary under blocked filesystems",
                                  "Immutable package and owner-selected operational acceptance"],
              "evidenceHashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(results.glob("*.json")) if p.name != "decision.json"}}
    (results / "decision.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "disposition": report["disposition"],
                      "cold": report["cold"]}, indent=2))


if __name__ == "__main__":
    main()
