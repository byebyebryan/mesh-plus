#!/usr/bin/env python3
"""Same-model compact patch review arithmetic; no codec, cache or stage execution."""

import argparse
import copy
import hashlib
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "scripts/reproduce-sync-codec-vectors.py"
FIXTURE = ROOT / "tests/fixtures/delta-sync/codec-review-vectors-r1.json"


def require(condition, code):
    if not condition:
        raise ValueError(code)


def compact_patch(expansion):
    # This predicate specifies the accepted Python callback boundary, not the
    # JSON wire or an implemented engine guard. Reject before any cell writer.
    require(type(expansion) is tuple, "patch_tuple")
    require(not expansion, "compact_callback_expansion")


def build():
    model = runpy.run_path(str(MODEL))
    source_raw = FIXTURE.read_bytes()
    source = json.loads(source_raw)
    model_raw = (json.dumps(model["vectors"](), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    require(model_raw == source_raw, "r1_fixture_changed")
    canonical, cells, tables = (model[name] for name in ("canonical", "cells", "tables"))
    before_rows, before_specs = source["beforeRows"], source["beforeGroups"]
    before_groups = model["groups"](before_rows, before_specs, 1)
    before_cells = cells(before_rows, before_groups)
    before_tables = tables(before_rows, before_cells, 1)
    before_bytes = canonical(before_tables)
    by_name = {case["name"]: case for case in source["positiveCases"]}
    token_case = by_name["unchanged-mask-token-change"]
    require(token_case["groupChanges"] == [], "omitted_mask_not_omitted")
    ref = [1, before_rows[0]["birth"]]
    equal_assertion = [[model["COHORTS"][0], ref, 17, ref, 17]]
    positives = []

    def positive(name, case, group_changes):
        compact_patch(())
        rows = model["overlay"](before_rows, case["recordEdits"], 2)
        groups = model["apply_groups"](before_rows, rows, before_groups, group_changes)
        membership = cells(rows, groups)
        state = tables(rows, membership, 2, before_tables)
        require(canonical(state) == canonical(case["logicalTables"]), "logical_table_mismatch")
        summary = model["summary"](state, 2)
        require(summary == case["after"], "logical_root_mismatch")
        changed = [json.loads(key) for key in sorted(before_cells.keys() | membership.keys())
                   if before_cells.get(key) != membership.get(key)]
        require(len(changed) == case["logicalMembershipKeysTouched"], "cell_change_count")
        positives.append({"name": name, "callbackExpansion": {"type": "tuple", "items": []},
                          "groupChanges": group_changes, "membershipKeysChanged": changed,
                          "after": summary, "logicalTables": state})
        return membership

    changed_cells = positive("retained-token-change-with-omitted-mask", token_case, [])
    positive("retained-token-change-with-equal-mask-assertion", token_case, equal_assertion)
    body_case = by_name["body-change-no-field-token-change"]
    positive("body-only-change-with-omitted-mask", body_case, [])
    require(positives[0]["after"] == positives[1]["after"], "assertion_changed_roots")
    changed_key = canonical(positives[0]["membershipKeysChanged"][0])
    require(json.loads(changed_key)[-1] == "activity", "retained_field")
    require(before_cells[changed_key] != changed_cells[changed_key], "token_not_changed")
    require(before_groups == model["apply_groups"](
        before_rows, model["overlay"](before_rows, token_case["recordEdits"], 2), before_groups, []),
        "omitted_mask_changed")

    correct = {"op": "put", "key": json.loads(changed_key),
               "expected": before_cells[changed_key], "value": changed_cells[changed_key]}
    wrong = {**correct, "value": "00" * 32}
    foreign = copy.deepcopy(correct)
    foreign["key"][0] = ["foreign", "namespace", "runtime"]
    removed = {"op": "remove", "key": correct["key"], "expected": correct["expected"]}
    bad_inputs = [
        ("nonempty-correct-callback-cell", (correct,)),
        ("nonempty-wrong-token", (wrong,)),
        ("nonempty-duplicate-callback-cell", (correct, copy.deepcopy(correct))),
        ("nonempty-conflicting-callback-cells", (correct, wrong)),
        ("nonempty-callback-removal", (removed,)),
        ("nonempty-foreign-cohort-cell", (foreign,)),
        ("nonempty-malformed-member", (None,)),
        ("empty-list-is-not-callback-tuple", []),
        ("null-is-not-callback-tuple", None),
    ]
    rejected = []
    for name, expansion in bad_inputs:
        calls = 0
        try:
            compact_patch(expansion)
            calls += 1  # the cell expansion phase cannot start on rejection
        except ValueError as error:
            require(calls == 0 and canonical(before_tables) == before_bytes, "guard_order")
            rejected.append({"name": name, "inputType": type(expansion).__name__,
                             "callbackExpansion": expansion, "expectedModelError": str(error),
                             "cellExpanderCalls": calls, "oldToyTablesUnchanged": True})
        else:
            raise AssertionError("unexpected acceptance: " + name)

    return {"format": "mesh-compact-patch-review-supplement",
            "scope": "Same-model toy arithmetic and Python callback-shape guard only; no independent/native/runtime admission or rollback acceptance",
            "modelSha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(),
            "r1FixtureSha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "tupleNotation": "Callback inputs are Python tuples; JSON arrays in this fixture describe their contents, not wire membership edits",
            "before": model["summary"](before_tables, 1),
            "positiveCases": positives, "rejectionCases": rejected,
            "expandedRoute": "Unchanged G0 DomainIndexPatch.membership_expansion semantics; this supplement neither models nor executes that runtime path",
            "pendingRuntime": ["compact callback guard before patch application", "semantic field-token validation and admitted old masks",
                               "generic sparse cell/index/root expansion", "atomic provisional rollback and GC-disabled held errors",
                               "unchanged expanded-route admission", "actual Agent raw schema and joined restore vectors"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--check", type=Path)
    args = parser.parse_args()
    result = build()
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if args.output:
        path = args.output.resolve()
        require(path.is_relative_to(ROOT), "owning_repo_output")
        with path.open("xb") as stream:
            stream.write(raw)
    else:
        require(args.check.read_bytes() == raw, "fixture_bytes")
    print(json.dumps({"positiveCases": len(result["positiveCases"]),
                      "rejectionCases": len(result["rejectionCases"]),
                      "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                      "scope": result["scope"]}, sort_keys=True))


if __name__ == "__main__":
    main()
