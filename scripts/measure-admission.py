"""Exact-work synthetic admission/current comparison; no services or native reads."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def measure(args):
    sys.path.insert(0, str(ROOT / "tests"))
    from prepared_fixture import StaticPreparation
    from test_simplification import fleet

    from mesh_plus import view
    from mesh_plus.api import PreparedReadGuard
    from mesh_plus.evidence import digest
    from mesh_plus.reader import PublicationState

    profile, reader, initial = await fleet("agent", hosts=2, rows=args.rows // 2, system=True)
    outcomes = {h["hostId"]: (h, [r for r in initial["sessions"] if profile.record_host(r) == h["hostId"]])
                for h in initial["mesh"]["hosts"]}
    for host, rows in outcomes.values():
        for row in rows:
            row["nativeIds"]["threadId"] = row["identity"]["nativeId"]
        if host["delivery"]["proof"] is not None:
            host["delivery"]["proof"]["payloadDigest"] = digest(profile.restore_native(host["owner"], rows))
    preparation = StaticPreparation(profile)
    if args.native_profile:
        from agent_observer.mesh_preparation import AgentPreparation
        from agent_observer.mesh_profile import AgentProfile
        profile = AgentProfile()
        reader.profile = profile
        reader.endpoints = tuple(replace(e, codec=profile.bind(e.host, "default")) for e in reader.endpoints)
        preparation = AgentPreparation(profile)
        view.validate_response(initial, profile=profile)
    guard = PreparedReadGuard("agent", "a" * 32, profile=profile, preparation=preparation)

    def classify(row):
        selected = int(row["identity"]["nativeId"].replace("-", ""), 16) < 105
        summary = None if selected else {"host": row["identity"]["hostScope"],
                                         "id": row["identity"]["nativeId"], "reason": "excluded"}
        return selected, summary

    if args.mode == "selection":
        from mesh_plus.api import SelectionRule
        selection = guard.select(lambda row: SelectionRule(*classify(row)))
    counts = {"aggregateAdmissions": 0, "currentRows": 0, "contextRows": 0, "selectedRows": 0, "summaries": 0}
    original = view._validated_response

    def admit(*a, **kw):
        counts["aggregateAdmissions"] += 1
        return original(*a, **kw)

    # Reader imports admission locally by name; patch both aliases for counting.
    import mesh_plus.reader as reader_module
    view._validated_response = reader_module._validated_response = admit
    compose = reader.compose_admitted if args.mode in {"owned", "selection"} else reader.compose
    state = PublicationState()
    signatures = []
    cpu = time.process_time_ns()
    wall = time.monotonic_ns()
    for index in range(args.generations):
        for host, rows in outcomes.values():
            rows[0]["title"] = "synthetic generation " + str(index)
            host["owner"]["service"]["viewRevision"] += 1
            if host["delivery"]["proof"] is not None:
                host["delivery"]["proof"]["payloadDigest"] = digest(profile.restore_native(host["owner"], rows))
        frame = compose(reader.endpoints, outcomes, "a" * 32, "watch", state=state)
        guard.accept(frame)
        context = guard.context() if args.mode in {"owned", "selection"} else guard.snapshot()
        counts["contextRows"] += len(context["sessions"])
        clock = context["mesh"]["reader"]["clock"]
        now = context["mesh"]["reader"]["encodedAtMs"]
        for _ in range(args.reads):
            if args.mode == "selection":
                rows, summaries = selection.current(now, clock)
                counts["currentRows"] += len(rows) + len(summaries)
            else:
                all_rows = guard.current(now, clock)
                counts["currentRows"] += len(all_rows)
                rows, summaries = [], []
                for row in all_rows:
                    selected, summary = classify(row)
                    if selected:
                        rows.append(row)
                    if summary is not None:
                        summaries.append(summary)
            counts["selectedRows"] += len(rows)
            counts["summaries"] += len(summaries)
            signatures.append(hashlib.sha256(json.dumps({"rows": [
                (r["identity"]["hostScope"], r["identity"]["nativeId"], r["title"]) for r in rows
            ], "summaries": summaries}, sort_keys=True).encode()).hexdigest())
    elapsed = {"cpuMs": (time.process_time_ns() - cpu) / 1e6,
               "wallMs": (time.monotonic_ns() - wall) / 1e6}
    guard.disconnect()
    return {"scope": __doc__, "version": importlib.metadata.version("mesh-plus"), "python": sys.version,
            "runtime": str(Path(view.__file__).resolve()), "mode": args.mode, "rows": args.rows,
            "nativeProfile": args.native_profile,
            "generations": args.generations, "readsPerGeneration": args.reads, **elapsed, "counts": counts,
            "semanticSignature": hashlib.sha256(json.dumps(signatures).encode()).hexdigest(),
            "cleanup": guard.snapshot() is None,
            "limits": ["Frozen Agent v3 fixture; explicit native-profile flag selects installed pure Observer validation",
                       "Transport, ordinary publishers, collection and device excluded",
                       "CPU includes compose/admission/preparation/reads/exports and semantic signature calculation",
                       "CPU milliseconds of exact work, not live service percent or real fleet savings"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("raw", "owned", "selection"), required=True)
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--generations", type=int, default=15)
    parser.add_argument("--reads", type=int, default=4)
    parser.add_argument("--native-profile", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rows < 10 or args.rows % 2 or min(args.generations, args.reads) < 1:
        parser.error("rows must be even and >=10; generations and reads must be positive")
    result = asyncio.run(measure(args))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("mode", "rows", "cpuMs", "counts", "semanticSignature", "cleanup")}))


if __name__ == "__main__":
    main()
