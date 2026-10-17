#!/usr/bin/env python3
"""Stdlib review arithmetic only; no Mesh/Observer codec or domain admission."""

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

FIELDS = ("runtime", "phase", "kind", "savedIdentity", "activity", "outcome", "workspace", "lastUpdated", "latestTurn")
SPACES = ("records", "bodies", "observations", "memberships", "receipts", "cohorts", "scopes", "metadata")
BINDING = {"hostScope": "review-host", "ownerEpoch": "review-owner", "view": "full", "contextGeneration": 1}
DIGEST = hashlib.sha256(b"codec-arithmetic-review-only-r1").digest()
COHORTS = (["provider", "namespace", "runtime"], ["provider", "namespace", "history"])


def require(condition, code):
    if not condition:
        raise ValueError(code)


def valid(value):
    kind = type(value)
    require(kind in (dict, list, str, int, bool, type(None)), "json_type")
    if kind is str:
        require(not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "json_surrogate")
    if kind in (dict, list):
        for key, child in value.items() if kind is dict else enumerate(value):
            if kind is dict:
                require(type(key) is str, "json_key")
                valid(key)
            valid(child)


def canonical(value):
    valid(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def frame(raw):
    return len(raw).to_bytes(8, "big") + raw


def hash_parts(*parts):
    return hashlib.sha256(b"".join(parts)).digest()


def map_root(space, entries):
    name = frame(space.encode())
    leaves, seen = [], set()
    for key, value in entries:
        k = canonical(key)
        require(k not in seen, "duplicate_key")
        seen.add(k)
        digest = hash_parts(b"mesh-sync-key\0", name, frame(k))
        v = hash_parts(b"mesh-sync-value\0", name, frame(canonical(value)))
        leaves.append((int.from_bytes(digest, "big"), hash_parts(b"mesh-sync-leaf\0", name, digest, frame(k), v)))
    require(len({key for key, _ in leaves}) == len(leaves), "key_collision")
    leaves.sort()

    def tree(rows):
        if len(rows) == 1:
            return rows[0][1]
        p = 256 - (rows[0][0] ^ rows[-1][0]).bit_length()
        left = [row for row in rows if not row[0] & (1 << (255 - p))]
        right = [row for row in rows if row[0] & (1 << (255 - p))]
        prefix = ((rows[0][0] >> (256 - p)) << ((8 - p % 8) % 8)).to_bytes((p + 7) // 8, "big")
        return hash_parts(b"mesh-sync-branch\0", name, p.to_bytes(2, "big"), frame(prefix), tree(left), tree(right))

    return (tree(leaves) if leaves else hash_parts(b"mesh-sync-empty\0", name)).hex()


def row(native_id, alias, birth=1):
    return {"identity": ["review-host", "provider", "namespace", "native-id", native_id],
            "alias": alias, "birth": ["review-owner", birth], "title": "review",
            "fields": {field: {"value": field} for field in FIELDS}}


def aliases(rows, generation):
    result, identities = {}, set()
    for item in rows:
        identity, birth, alias = item["identity"], item["birth"], item["alias"]
        require(len(identity) == 5 and identity[0] == BINDING["hostScope"], "alias_scope")
        require(type(alias) is int and 1 <= alias < 2**64, "alias_range")
        require(birth[0] == BINDING["ownerEpoch"] and type(birth[1]) is int and 1 <= birth[1] <= generation, "alias_birth")
        require(alias not in result and canonical(identity) not in identities, "alias_duplicate")
        result[alias] = item
        identities.add(canonical(identity))
    return result


def resolve(index, alias, birth, *, binding=BINDING):
    require(canonical(binding) == canonical(BINDING), "alias_scope")
    require(type(alias) is int and alias in index, "alias_unknown")
    require(canonical(index[alias]["birth"]) == canonical(birth), "alias_birth")
    return index[alias]


def overlay(before, edits, generation):
    result = {canonical(item["identity"]): item for item in before}
    seen = set()
    for op, identity, item in edits:
        key = canonical(identity)
        require(key not in seen, "record_duplicate_operation")
        seen.add(key)
        old = result.get(key)
        if op == "remove":
            require(old is not None and item is None, "record_remove")
            del result[key]
        else:
            require(op == "put" and item["identity"] == identity, "record_put")
            if old is not None:
                require(old["alias"] == item["alias"] and old["birth"] == item["birth"], "record_rebirth")
            else:
                require(item["birth"][1] == generation, "record_new_birth")
            result[key] = item
    output = list(result.values())
    aliases(output, generation)
    return output


def group_key(cohort, item):
    return canonical([cohort, item["identity"], item["birth"]])


def mask(value, *, old=False):
    require(type(value) is int and (1 if old else 0) <= value <= 511, "mask_range")
    return value


def groups(rows, specs, generation):
    index, result = aliases(rows, generation), {}
    for cohort, alias, birth, bits in specs:
        mask(bits, old=True)
        item = resolve(index, alias, birth)
        key = group_key(cohort, item)
        require(key not in result, "mask_duplicate")
        result[key] = bits
    return result


def apply_groups(before_rows, after_rows, before_groups, changes):
    before, after = aliases(before_rows, 1), aliases(after_rows, 2)
    result, seen = dict(before_groups), set()
    for cohort, old_ref, expected, new_ref, new_mask in changes:
        require((old_ref is None) == (expected is None), "mask_before_ref")
        mask(new_mask)
        require((new_ref is None) == (new_mask == 0), "mask_after_ref")
        require(not (expected is None and new_mask == 0), "mask_empty")
        old = None if old_ref is None else resolve(before, *old_ref)
        new = None if new_ref is None else resolve(after, *new_ref)
        if old is not None and new is not None:
            require(group_key(cohort, old) == group_key(cohort, new), "mask_reference")
        key = group_key(cohort, old if old is not None else new)
        require(key not in seen, "mask_duplicate")
        seen.add(key)
        if expected is None:
            require(key not in before_groups, "mask_expected")
        else:
            mask(expected, old=True)
            require(before_groups.get(key, 0) == expected, "mask_expected")
        if new_mask:
            result[key] = new_mask
        else:
            result.pop(key, None)
    return result


def field_token(item, field):
    return hash_parts(b"mesh-sync-field\0", frame(DIGEST), frame(canonical(item["identity"])),
                      frame(canonical(item["birth"])), frame(field.encode()), frame(canonical(item["fields"][field]))).hex()


def cells(rows, grouped):
    by_ref = {canonical([item["identity"], item["birth"]]): item for item in rows}
    result = {}
    for key, bits in grouped.items():
        cohort, identity, birth = json.loads(key)
        item = by_ref.get(canonical([identity, birth]))
        require(item is not None, "mask_orphan")
        for i, field in enumerate(FIELDS):
            if bits & (1 << i):
                result[canonical([cohort, identity, birth, field])] = field_token(item, field)
    return result


def tables(rows, membership, generation, previous=None):
    result = {space: [] for space in SPACES}
    for item in rows:
        identity, birth = item["identity"], item["birth"]
        body = {"identity": identity, "fields": item["fields"], "title": item["title"]}
        body_id = hash_parts(b"mesh-sync-body\0", frame(DIGEST), frame(canonical(body))).hex()
        result["records"].append([identity, {"alias": item["alias"], "birth": birth, "body": body_id,
                                              "order": [0, identity], "scope": identity[1:3]}])
        result["bodies"].append([body_id, body])
        result["observations"].append([[identity, birth], {"reviewOnly": True}])
        result["scopes"].append([[*identity[1:3], "member", identity], birth])
    result["memberships"] = [[json.loads(key), value] for key, value in sorted(membership.items())]
    for cohort in COHORTS:
        members = [[key[1:], value] for key, value in result["memberships"] if key[0] == cohort]
        root = map_root("cohort-members", members)
        old = None if previous is None else next(value for key, value in previous["cohorts"] if key == cohort)
        version = old["seal"][0] if old is not None and old["seal"][1:] == [root, len(members)] else generation
        result["cohorts"].append([cohort, {"receipt": cohort, "seal": [version, root, len(members)]}])
        result["receipts"].append([cohort, {"reviewAccepted": generation}])
    result["metadata"] = [["reviewGeneration", generation]]
    return result


def summary(state, generation):
    table_roots = [[space, map_root(space, state[space]), len(state[space])] for space in sorted(SPACES)]
    native = hash_parts(b"mesh-sync-native\0", frame(canonical(BINDING)), generation.to_bytes(8, "big"), frame(canonical(table_roots)))
    return {"tables": table_roots, "nativeRoot": native.hex()}


def strict_json(raw):
    def integer(token):
        require(token != "-0", "json_negative_zero")
        return int(token)

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "json_duplicate")
            result[key] = value
        return result

    def reject(_value):
        raise ValueError("json_number")

    result = json.loads(raw, object_pairs_hook=pairs, parse_int=integer, parse_float=reject, parse_constant=reject)
    valid(result)
    return result


def vectors():
    a, b = row("a", 1), row("β", 2)
    before = [a, b]
    specs = [[COHORTS[0], 1, a["birth"], 17], [COHORTS[0], 2, b["birth"], 1]]
    old_groups = groups(before, specs, 1)
    old_cells = cells(before, old_groups)
    old_tables = tables(before, old_cells, 1)
    positives, rejections = [], []

    def positive(name, edits, changes, expected_specs):
        after = overlay(before, edits, 2)
        new_groups = apply_groups(before, after, old_groups, changes)
        expected_groups = groups(after, expected_specs, 2)
        require(new_groups == expected_groups, "vector_group_mismatch")
        desired = cells(after, expected_groups)
        # Sparse arithmetic expansion: group changes and changed token inputs,
        # rather than a replacement membership table supplied by the codec.
        expanded = dict(old_cells)
        touched = set()
        before_by_ref = {canonical([x["identity"], x["birth"]]): x for x in before}
        after_by_ref = {canonical([x["identity"], x["birth"]]): x for x in after}
        for key in old_groups.keys() | new_groups.keys():
            cohort, identity, birth = json.loads(key)
            ref = canonical([identity, birth])
            old, new = before_by_ref.get(ref), after_by_ref.get(ref)
            for i, field in enumerate(FIELDS):
                old_on, new_on = old_groups.get(key, 0) & (1 << i), new_groups.get(key, 0) & (1 << i)
                changed = old is None or new is None or canonical(old["fields"][field]) != canonical(new["fields"][field])
                if bool(old_on) != bool(new_on) or new_on and changed:
                    cell = canonical([cohort, identity, birth, field])
                    if new_on:
                        expanded[cell] = field_token(new, field)
                    else:
                        expanded.pop(cell, None)
                    touched.add(cell)
        require(expanded == desired, "vector_cell_mismatch")
        explicit = tables(after, desired, 2, old_tables)
        compact = tables(after, expanded, 2, old_tables)
        require(canonical(explicit) == canonical(compact), "vector_table_mismatch")
        count = 0
        for edit_order in itertools.permutations(edits):
            for group_order in itertools.permutations(changes):
                perm_rows = overlay(before, edit_order, 2)
                require(apply_groups(before, perm_rows, old_groups, group_order) == expected_groups, "vector_order")
                count += 1
        positives.append({"name": name, "recordEdits": edits, "groupChanges": changes, "expectedGroups": expected_specs,
                          "logicalMembershipKeysTouched": len(touched), "permutations": count,
                          "after": summary(explicit, 2), "logicalTables": explicit})

    def rejected(name, run):
        try:
            run()
        except ValueError as error:
            rejections.append({"name": name, "expectedError": str(error)})
        else:
            raise AssertionError("unexpected acceptance: " + name)

    def change(old, expected, new, bits):
        return [COHORTS[0], old, expected, new, bits]

    a_ref, b_ref = [1, a["birth"]], [2, b["birth"]]
    positive("unchanged-mask-assertion", [], [change(a_ref, 17, a_ref, 17)], specs)
    positive("sparse-bit-insert", [], [change(a_ref, 17, a_ref, 19)], [[COHORTS[0], 1, a["birth"], 19], specs[1]])
    positive("sparse-bit-remove", [], [change(a_ref, 17, a_ref, 1)], [[COHORTS[0], 1, a["birth"], 1], specs[1]])
    positive("group-remove", [], [change(a_ref, 17, None, 0)], [specs[1]])
    positive("absent-group-insert", [], [[COHORTS[1], None, None, b_ref, 2]], [*specs, [COHORTS[1], 2, b["birth"], 2]])
    changed = copy.deepcopy(a)
    changed["fields"]["activity"] = {"value": "changed"}
    positive("unchanged-mask-token-change", [["put", a["identity"], changed]], [], specs)
    changed = copy.deepcopy(a)
    changed["title"] = "changed title only"
    positive("body-change-no-field-token-change", [["put", a["identity"], changed]], [], specs)
    c = row("c", 1, 2)
    reuse_edits = [["remove", a["identity"], None], ["put", c["identity"], c]]
    reuse_changes = [change(a_ref, 17, None, 0), change(None, None, [1, c["birth"]], 17)]
    positive("same-transaction-alias-reuse", reuse_edits, reuse_changes, [[COHORTS[0], 1, c["birth"], 17], specs[1]])
    after_reuse = overlay(before, reuse_edits, 2)
    for value in (0, -1, 512, True, 1.0, "1", None):
        rejected("baseline-mask-" + repr(value), lambda value=value: groups(before, [[COHORTS[0], 1, a["birth"], value]], 1))
    for value in (-1, 512, True, 1.0, "1", None):
        rejected("new-mask-" + repr(value), lambda value=value: apply_groups(before, before, old_groups, [change(a_ref, 17, a_ref, value)]))
    for name, changes in [
        ("expected-null-present", [change(None, None, a_ref, 1)]),
        ("expected-zero", [change(a_ref, 0, a_ref, 1)]),
        ("wrong-before-mask", [change(a_ref, 1, a_ref, 1)]),
        ("duplicate-identical-groups", [change(a_ref, 17, a_ref, 1)] * 2),
        ("null-to-zero", [change(None, None, None, 0)]),
        ("missing-before-ref", [change(None, 17, a_ref, 1)]),
        ("non-null-after-removal", [change(a_ref, 17, a_ref, 0)]),
    ]:
        rejected(name, lambda changes=changes: apply_groups(before, before, old_groups, changes))
    rejected("alias-reuse-crosses-group-ref", lambda: apply_groups(before, after_reuse, old_groups,
             [change(a_ref, 17, [1, c["birth"]], 17)]))
    rejected("duplicate-alias-definition", lambda: aliases([a, row("c", 1)], 1))
    rejected("duplicate-identity-definition", lambda: aliases([a, row("a", 3)], 1))
    rejected("duplicate-record-remove-reinsert", lambda: overlay(before, [["remove", a["identity"], None], ["put", a["identity"], a]], 2))
    changed = copy.deepcopy(a)
    changed["alias"] = 3
    rejected("surviving-record-alias-change", lambda: overlay(before, [["put", a["identity"], changed]], 2))
    rejected("unknown-alias", lambda: resolve(aliases(before, 1), 99, a["birth"]))
    rejected("stale-birth-after-reuse", lambda: resolve(aliases(after_reuse, 2), 1, a["birth"]))
    rejected("foreign-binding", lambda: resolve(aliases(before, 1), 1, a["birth"], binding={**BINDING, "view": "active"}))
    for raw in ('{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}', '{"x":-0}', '{"x":1.0}',
                '{"x":NaN}', '{"x":Infinity}', '{"x":"\\ud800"}', '\ufeff{}', '{}{}'):
        rejected("strict-json-" + raw, lambda raw=raw: strict_json(raw))
    optional = []
    for value in ({}, {"value": None}, {"value": 0}, {"value": False}):
        item = copy.deepcopy(a)
        item["fields"]["workspace"] = value
        optional.append({"value": value, "fieldToken": field_token(item, "workspace")})
    require(len({x["fieldToken"] for x in optional}) == 4, "optional_token_collision")
    return {"scope": "stdlib review arithmetic; toy values are not Agent API 4 rows, codec/runtime/domain/GC/resource acceptance",
            "nativeBinding": BINDING, "descriptorDigest": DIGEST.hex(), "fields": FIELDS,
            "beforeRows": before, "beforeGroups": specs, "before": summary(old_tables, 1),
            "positiveCases": positives, "rejectionCases": rejections, "optionalValueTokens": optional,
            "pendingRuntimeCases": ["callback/root failure rolls back aliases/indexes/cells",
                                    "codec/schema/callback replacement revokes refs", "head creates no body plan",
                                    "retired plan/iterator/context rejects", "GC-disabled held-error cleanup",
                                    "inclusive quota prepayment and real sparse visit counts",
                                    "Observer joined native extraction/body/observation equivalence"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--check", type=Path)
    args = parser.parse_args()
    result = vectors()
    data = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if args.output:
        path = args.output.resolve()
        require(path.is_relative_to(Path(__file__).resolve().parents[1]), "owning_repo_output")
        with path.open("xb") as stream:
            stream.write(data)
    else:
        require(args.check.read_bytes() == data, "vector_bytes_mismatch")
    print(json.dumps({"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                      "positiveCases": len(result["positiveCases"]), "rejectionCases": len(result["rejectionCases"]),
                      "scope": "review arithmetic only; joint confirmation pending"}, sort_keys=True))


if __name__ == "__main__":
    main()
