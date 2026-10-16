#!/usr/bin/env python3
"""Explicit sibling-source capacity diagnostic; no service/network/install IO.

Uses the Observer owner's existing synthetic fixture. Results are unpaired
source diagnostics, never G1/G2 CPU or installed-artifact acceptance.
"""

import argparse
import datetime
import hashlib
import importlib
import json
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

MESH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MESH / "src"))

from mesh_plus.sync import OwnedSyncCache, source_binding  # noqa: E402
from mesh_plus.sync.canonical import canonical  # noqa: E402


def hashes(paths, root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def owner_paths(root):
    return sorted([*root.glob("agent_observer/*.py"), *root.glob("agent_observer/contracts/*.json"),
                   root / "tests/test_mesh_sync_profile.py", root / "tests/test_service_state.py"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observer-checkout", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[100, 500, 2000])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    observer = args.observer_checkout.resolve()
    if not all(1 <= count <= 2000 for count in args.counts):
        parser.error("counts must be in 1..2000")
    if args.output is not None and not args.output.resolve().is_relative_to(MESH):
        parser.error("write evidence only inside the owning Mesh repository")
    sys.path[:0] = [str(observer), str(observer / "tests")]
    before = hashes(owner_paths(observer), observer)
    fixture = importlib.import_module("test_mesh_sync_profile").MeshSyncProfileTest
    profile_class = importlib.import_module("agent_observer.mesh_sync_profile").AgentSyncProfile
    service_class = importlib.import_module("agent_observer.service_state").ServiceState
    results, unexpected = [], False
    for count in args.counts:
        test, cache = fixture(), None
        test.setUp()
        result = {"records": count, "view": "full"}
        try:
            with patch("agent_observer.service_state.uuid.uuid4", return_value=uuid.UUID("11111111-1111-4111-8111-111111111111")):
                start = time.process_time_ns()
                value = test.fixture(count)
                source = value["sources"][0]
                owner = service_class(host_scope="fixture", configs={"codex": (source["configHome"], source["configHomeKind"])},
                                      uid=1000, clock=lambda: test.now,
                                      boot_id="00000000-0000-4000-8000-000000000001", clock_domain="time:[123]")
                owner.attempt("codex", "runtime")
                owner.accept("codex", "runtime", value, sampled_ms=test.now, ttl_ms=10000)
                result["ownerFixtureBuildCpuMs"] = (time.process_time_ns() - start) / 1e6
            # Same-source full diagnostic bytes, not a full/active comparison.
            legacy = canonical(owner.frame("view", 1))
            result["legacyNativeFullBytes"] = len(legacy)
            raw = owner.sync_baseline("full")
            result.update(nativeBytes=len(raw), nativeSha256=hashlib.sha256(raw).hexdigest())
            profile = profile_class(profile_schema_digest="a" * 64)
            cache = OwnedSyncCache(profile, source_binding("fixture", "agents", profile.descriptor))
            start = time.process_time_ns()
            candidate = cache.admit_baseline(raw)
            result.update(meshBaselineCpuMs=(time.process_time_ns() - start) / 1e6,
                          budget=cache.ledger.inspect(), nativeTag=candidate.tag.native.wire(),
                          memberships=len(dict(cache.store.candidate.tables)["memberships"]))
        except Exception as error:
            result["error"] = {"type": type(error).__name__, "code": str(error)[:256]}
            result["capacityRejected"] = str(error).endswith(("_capacity", "_limit"))
            unexpected |= not result["capacityRejected"]
        finally:
            if cache is not None:
                cache.close()
                result.update(afterCloseBytes=cache.ledger.used, afterCloseReservations=cache.ledger.reserved)
            test.tearDown()
        results.append(result)
    after = hashes(owner_paths(observer), observer)
    report = {"kind": "unpaired source capacity diagnostic", "checkedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "python": sys.version.split()[0], "counterpartStableDuringRun": before == after,
              "unexpectedFailure": unexpected,
              "observerInputs": before,
              "meshInputs": hashes(sorted(MESH.glob("src/mesh_plus/**/*.py")), MESH),
              "scriptSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "results": results,
              "exclusions": ["not CPU acceptance, ABBA, RSS or plateau evidence", "not a dense nine-field fixture",
                             "not native IPC, SSH, installed-wheel, live-fleet or physical evidence",
                             "no service, collector, package, pin or sibling file mutation"]}
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if before != after:
        print("counterpart source changed during probe; discard measurements", file=sys.stderr)
        return 1
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    else:
        print(encoded, end="")
    print(json.dumps({"results": results, "counterpartStableDuringRun": True}, sort_keys=True), file=sys.stderr)
    return int(unexpected)


if __name__ == "__main__":
    raise SystemExit(main())
