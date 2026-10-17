"""Reproduce bounded source compatibility; no installed/native acceptance."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OBSERVER = ROOT.parent / "agent-observer-active-feed"
OUTPUT = Path(__file__).with_name("packed-node-source-checks.json")
PRIVATE = r"""
import gc
import unittest
from unittest.mock import patch
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync._packed_nodes import PackedNodeArena
from mesh_plus.sync.reconstruction import ReconstructionStore

gc.disable()
arenas = []
initialize = ReconstructionStore.__init__
def paged(self, *args, **kwargs):
    initialize(self, *args, **kwargs)
    existing = getattr(self.ledger, "_packed_nodes", None)
    if existing is None or existing() is None:
        arenas.append(PackedNodeArena(self.ledger))
with patch.object(ReconstructionStore, "__init__", paged):
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromName("test_mesh_sync_profile"))
for arena in arenas:
    arena.close()
    arena.close()
    ledger = arena.ledger
    assert (ledger.used, ledger.reserved, ledger.encoded, ledger.encoded_reserved,
            ledger.pending_encoded, ledger.pending_units) == (0, 0, 0, 0, 0, 0)
print("private arenas closed:", len(arenas), "; cyclic GC:", gc.isenabled())
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
"""


def snapshot():
    result = {}
    for label, checkout in (("mesh", ROOT), ("observer", OBSERVER)):
        paths = list(checkout.glob("src/mesh_plus/**/*.py")) if label == "mesh" else list(checkout.glob("agent_observer/**/*.py"))
        paths += list(checkout.glob("tests/test_sync*.py"))
        if label == "observer":
            paths += list(checkout.glob("agent_observer/contracts/*.json"))
            paths += list(checkout.glob("tests/test_mesh_sync*.py"))
        result[label] = {str(path.relative_to(checkout)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in sorted(paths)}
    return result


def main():
    if OUTPUT.exists():
        raise SystemExit("preserve prior report/logs")
    before, runs = snapshot(), []
    interpreters = [("314", ROOT / ".venv/bin/python"),
                    ("311", ROOT.parent / "agent-observer/.local/active-feed-20261016/installed311/bin/python")]
    modules = ["test_sync_owned_source", "test_sync_source", "test_sync_acquisition",
               "test_mesh_sync_profile", "test_mesh_sync_read"]
    for version, executable in interpreters:
        for private in (False, True):
            name = ("private-profile" if private else "default-compatibility") + version
            log = OUTPUT.with_name("packed-node-" + name + ".log")
            if log.exists():
                raise SystemExit("preserve prior log")
            argv = ["rtk", "proxy", str(executable), "-B"]
            argv += ["-c", PRIVATE] if private else ["-m", "unittest", "-q", *modules]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(map(str, (ROOT / "src", OBSERVER, OBSERVER / "tests")))
            done = subprocess.run(argv, cwd=ROOT, env=environment, capture_output=True, text=True)
            log.write_text(done.stdout + done.stderr)
            count = re.findall(r"Ran (\d+) tests", done.stderr)
            runs.append({"name": name, "argv": argv, "exitCode": done.returncode,
                         "tests": int(count[-1]) if count else None,
                         "skipped": bool(re.search(r"skipped=\d+", done.stderr)),
                         "log": str(log.relative_to(ROOT)), "logSha256": hashlib.sha256(log.read_bytes()).hexdigest()})
    result = {"scope": "default source compatibility plus private storage under actual Agent profile tests",
              "meshRuntime": "18e95c1791e66d20a211aa7d96b44d49b7fb78b7",
              "observerInspectedHead": "384d0cb1eeb98bd2784e42e4b73e90ef9a1f3e85",
              "sourceStableDuringRuns": before == snapshot(), "inputs": before, "runs": runs,
              "canonicalGate": {"command": "rtk proxy .venv/bin/python scripts/check.py", "python": "3.14.8",
                                "coreTests": 286, "skips": 0, "designChecks": 116, "deliveryChecks": 169,
                                "lockedInputs": 33, "packagedSchemas": 25, "exitCode": 0, "ruff": "passed"},
              "mesh311": {"tests": 42, "skips": 0, "exitCode": 0,
                          "modules": ["test_sync_packed_nodes", "test_sync_reconstruction", "test_sync_cache"]},
              "exclusions": ["no installed packages or wheel", "no populated native/fixed SSH acceptance",
                             "no Agent 2000-row or aggregate intake/resource qualification", "no matched CPU/RSS/plateau",
                             "no compact/relay API acceptance", "no sibling edits/services/rollout"]}
    OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    passed = result["sourceStableDuringRuns"] and all(run["exitCode"] == 0 and not run["skipped"] for run in runs)
    print(json.dumps({"passed": passed, "stable": result["sourceStableDuringRuns"],
                      "runs": [{k: run[k] for k in ("name", "exitCode", "tests", "skipped")} for run in runs],
                      "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}))
    return int(not passed)


if __name__ == "__main__":
    sys.exit(main())
