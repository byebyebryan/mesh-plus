#!/usr/bin/env python3
"""R2 reference spelling arithmetic only; no native codec/schema or cache admission."""
import argparse
import copy
import itertools
import json
from hashlib import sha256
from pathlib import Path

EPOCH = "00000000-0000-4000-8000-000000000001"
RUNTIME, HISTORY = ["codex", "namespace", "runtime"], ["codex", "namespace", "history"]
A, B = ["fixture", "codex", "namespace", "thread", "a"], ["fixture", "codex", "namespace", "thread", "b"]
C = ["fixture", "codex", "namespace", "thread", "c"]
BEFORE, AFTER = {7: [A, [EPOCH, 1]], 8: [C, [EPOCH, 1]]}, {7: [B, [EPOCH, 2]], 8: [C, [EPOCH, 1]]}


def require(test, code):
    if not test:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def catalog(value):
    require(type(value) is dict and set(value) == {"before", "after"}, "catalog_shape")
    result = {}
    for side, keys in value.items():
        require(type(keys) is list and len(keys) <= 32, "catalog_capacity")
        seen = set()
        for key in keys:
            require(type(key) is list and len(key) == 3 and all(type(part) is str and part for part in key),
                    "receipt_key")
            encoded = canonical(key)
            require(encoded not in seen, "receipt_duplicate")
            seen.add(encoded)
        result[side] = keys
    return result


def record(raw, side, *, epoch=EPOCH):
    require(type(raw) is list and len(raw) == 2, "record_shape")
    alias, birth = raw
    require(type(alias) is int and 1 <= alias < 2**64, "alias_range")
    require(type(birth) is int and 1 <= birth <= 2, "birth_range")
    require(epoch == EPOCH, "foreign_binding")
    definitions = BEFORE if side == "before" else AFTER
    require(alias in definitions, "unknown_alias")
    full = definitions[alias]
    require(full[1] == [epoch, birth], "stale_birth")
    return full


def group_side(raw, side, refs):
    require(type(raw) is list and len(raw) == 3, "side_shape")
    index, alias, birth = raw
    require(type(index) is int and 0 <= index < len(refs[side]), "receipt_index")
    return refs[side][index], record([alias, birth], side)


def bits(value, *, old=False):
    require(type(value) is int and (1 if old else 0) <= value <= 511, "mask_range")


def baseline(raw, refs):
    require(type(raw) is list and len(raw) == 2, "baseline_shape")
    side, mask = raw
    bits(mask, old=True)
    cohort, ref = group_side(side, "after", refs)
    return {"cohort": cohort, "record_ref": ref, "old_mask": 0, "new_mask": mask}


def changed(raw, refs):
    require(type(raw) is list and len(raw) == 4, "change_shape")
    before, old, after, new = raw
    require((before is None) == (old is None), "old_absence")
    if old is not None:
        bits(old, old=True)
    bits(new)
    require((after is None) == (new == 0), "new_absence")
    require(not (old is None and new == 0), "empty_edit")
    prior = None if before is None else group_side(before, "before", refs)
    target = None if after is None else group_side(after, "after", refs)
    if prior is not None and target is not None:
        require(prior == target, "cross_group_edit")
    cohort, ref = target if target is not None else prior
    return {"cohort": cohort, "record_ref": ref, "old_mask": 0 if old is None else old, "new_mask": new}


def changes(rows, refs):
    result, seen = [], set()
    for raw in rows:
        value = changed(raw, refs)
        marker = canonical([value["cohort"], value["record_ref"]])
        require(marker not in seen, "duplicate_group")
        seen.add(marker)
        result.append(value)
    return sorted(result, key=lambda value: canonical([value["cohort"], value["record_ref"]]))


def build():
    refs = catalog({"before": [RUNTIME, HISTORY], "after": [HISTORY, RUNTIME]})
    remove, insert = [[0, 7, 1], 1, None, 0], [None, None, [1, 7, 2], 1]
    expected = [{"cohort": RUNTIME, "record_ref": BEFORE[7], "old_mask": 1, "new_mask": 0},
                {"cohort": RUNTIME, "record_ref": AFTER[7], "old_mask": 0, "new_mask": 1}]
    permutations = []
    for order in itertools.permutations((remove, insert)):
        value = changes(order, refs)
        require(value == expected, "permutation")
        permutations.append(value)
    removed = catalog({"before": [RUNTIME, HISTORY], "after": [HISTORY]})
    require(changed(remove, removed) == expected[0], "removed_receipt_before")
    before_support = group_side([0, 7, 1], "before", refs)
    after_support = group_side([0, 7, 2], "after", refs)
    require(before_support[0] == RUNTIME and after_support[0] == HISTORY, "side_selection")
    positive = [
        {"name": "reorder-and-alias-reuse", "receiptRefs": refs, "raw": [remove, insert], "normalized": expected},
        {"name": "reordered-input-equivalence", "permutations": len(permutations), "normalized": expected},
        {"name": "old-receipt-removed-after", "receiptRefs": removed, "raw": remove, "normalized": expected[0]},
        {"name": "receipt-index-zero-valid", "before": before_support, "after": after_support},
        {"name": "baseline-after-only", "raw": [[1, 7, 2], 511], "normalized": baseline([[1, 7, 2], 511], refs)},
        {"name": "surviving-row-receipt-reorder", "raw": [[0, 8, 1], 1, [1, 8, 1], 1],
         "normalized": changed([[0, 8, 1], 1, [1, 8, 1], 1], refs)},
    ]
    rejections = []

    def reject(name, call):
        try:
            call()
        except ValueError as error:
            rejections.append({"name": name, "error": str(error)})
        else:
            raise AssertionError(name)

    reject("reuse-combined-in-one-group", lambda: changed([[0, 7, 1], 1, [1, 7, 2], 1], refs))
    reject("wrong-old-birth", lambda: changed([[0, 7, 2], 1, None, 0], refs))
    reject("wrong-new-birth", lambda: changed([None, None, [1, 7, 1], 1], refs))
    reject("foreign-binding", lambda: record([7, 1], "before", epoch="other-owner"))
    reject("unknown-alias", lambda: record([99, 1], "before"))
    reject("cross-cohort-index-rebind", lambda: changed([[0, 8, 1], 1, [0, 8, 1], 1], refs))
    reject("duplicate-logical-group", lambda: changes([remove, copy.deepcopy(remove)], refs))
    reject("old-zero", lambda: changed([[0, 7, 1], 0, None, 0], refs))
    reject("absent-to-zero", lambda: changed([None, None, None, 0], refs))
    reject("new-null", lambda: changed([None, None, [1, 7, 2], None], refs))
    reject("missing-before", lambda: changed([None, 1, None, 0], refs))
    reject("new-side-with-zero", lambda: changed([[0, 7, 1], 1, [1, 7, 2], 0], refs))
    for value in (True, False, None, -1, 2):
        reject("receipt-index-" + repr(value), lambda value=value: group_side([value, 7, 1], "before", refs))
    for value in (True, 0, -1, 512):
        reject("baseline-mask-" + repr(value), lambda value=value: baseline([[1, 7, 2], value], refs))
    reject("old-fallback-to-after-index", lambda: group_side([1, 7, 1], "before", catalog({"before": [RUNTIME], "after": [HISTORY, RUNTIME]})))
    reject("new-fallback-to-before-index", lambda: group_side([1, 7, 2], "after", removed))
    reject("duplicate-receipt-key", lambda: catalog({"before": [RUNTIME, copy.deepcopy(RUNTIME)], "after": []}))
    reject("catalog-extra-field", lambda: catalog({"before": [], "after": [], "other": []}))
    reject("catalog-over-cap", lambda: catalog({"before": [["p", str(i), "runtime"] for i in range(33)], "after": []}))
    return {"format": "mesh-compact-r2-reference-arithmetic", "positiveCases": positive,
            "rejectionCases": rejections, "strictSchemaAccepted": False,
            "pendingRuntime": ["compact patch single-writer enforcement", "admitted before-mask checks",
                               "complete native schema/context and receipt existence", "staged rollback and lifetime"],
            "scope": "reference resolution and masks only; no native/domain, staged rollback, lifetime, CPU or transport acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--output", type=Path)
    choice.add_argument("--check", type=Path)
    args = parser.parse_args()
    result = build()
    raw = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    if args.output:
        require(not args.output.exists(), "preserve_evidence")
        args.output.write_bytes(raw)
    else:
        require(args.check.read_bytes() == raw, "fixture_bytes")
    print(json.dumps({"positive": len(result["positiveCases"]), "rejections": len(result["rejectionCases"]),
                      "sha256": sha256(raw).hexdigest(), "bytes": len(raw), "scope": result["scope"]}))


if __name__ == "__main__":
    main()
