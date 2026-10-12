"""Differential pure native admission against an exact installed baseline; no source acquisition."""

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import random
import sys
import time
from pathlib import Path


def package(name, root):
    path = root / "agent_observer"
    spec = importlib.util.spec_from_file_location(name, path / "__init__.py", submodule_search_locations=[str(path)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(name + ".contract"), importlib.import_module(name + ".service_contract")


def outcome(function, *args):
    try:
        function(*args)
        return "accepted"
    except Exception as error:
        return type(error).__name__, str(error)


def paths(value, path=()):
    yield path
    if isinstance(value, dict):
        for key, child in value.items():
            yield from paths(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from paths(child, (*path, index))


def run(args):
    baseline, old_service = package("_shape_baseline", args.baseline)
    candidate, new_service = package("_shape_candidate", args.candidate)
    checked = 0
    kinds = ("null", "object", "array", "string", "integer", "boolean", "unsupported")
    values = (None, True, False, -1, 0, 1, 2**64, 1.0, "", "ok", "a\x00b", "a\u202eb", [], [1], {}, {"a": 1})
    for kind in kinds:
        for spec in ({"type": kind}, {"type": ["null", kind]}, {"anyOf": [{"type": kind}, {"type": "null"}]}):
            for value in values:
                if outcome(baseline.validate_shape, value, spec) != outcome(candidate.validate_shape, value, spec):
                    raise ValueError("shape_admission_diverged")
                checked += 1
    frame = json.loads(args.frame.read_text())
    if outcome(old_service.validate_frame, frame) != "accepted" or outcome(new_service.validate_frame, frame) != "accepted":
        raise ValueError("baseline_native_fixture_invalid")
    rng = random.Random(20261012)
    positions = list(paths(frame))
    replacements = [None, True, False, -1, 2**64, 1.0, "", "bad\x00value", "unsupported", [], {}]
    for _ in range(args.mutations):
        data = copy.deepcopy(frame)
        path = rng.choice(positions)
        replacement = copy.deepcopy(rng.choice(replacements))
        if path:
            node = data
            for part in path[:-1]:
                node = node[part]
            node[path[-1]] = replacement
        else:
            data = replacement
        if outcome(old_service.validate_frame, data) != outcome(new_service.validate_frame, data):
            raise ValueError("native_admission_diverged")
        checked += 1
    timings = []
    for block in range(4):
        for label, service in (("baseline", old_service), ("candidate", new_service), ("candidate", new_service), ("baseline", old_service)):
            started = time.process_time()
            for _ in range(args.rounds):
                service.validate_frame(frame)
            timings.append({"block": block, "label": label, "rounds": args.rounds, "cpuSeconds": time.process_time() - started})
    report = {"status": "passed", "checks": checked, "mutations": args.mutations, "timings": timings,
              "rows": len(frame["snapshot"]["sessions"]), "frameSha256": hashlib.sha256(args.frame.read_bytes()).hexdigest(),
              "python": sys.version.split()[0], "inputs": {label: hashlib.sha256((root / "agent_observer/contract.py").read_bytes()).hexdigest()
                  for label, root in (("baseline", args.baseline), ("candidate", args.candidate))},
              "scope": "pure native/type differential exact finite results plus four ABBA fixed-frame CPU blocks; no publisher/network/resource acceptance"}
    from host import private_write
    private_write(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "timings"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mutations", type=int, default=600)
    parser.add_argument("--rounds", type=int, default=24)
    args = parser.parse_args()
    if not 1 <= args.mutations <= 1000 or not 1 <= args.rounds <= 100:
        parser.error("bounded mutation/round counts required")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    run(args)
