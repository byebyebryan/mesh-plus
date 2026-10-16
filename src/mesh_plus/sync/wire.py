"""Closed generic/native sync framing. Domain table values stay profile-owned."""

import re
from hashlib import sha256

from ..protocol import check
from .canonical import (  # noqa: F401 - public internal preflight seam
    Atom,
    canonical,
    decode,
    decode_reservation,
)
from .commitment import framed
from .model import SPACES, NativeTag, hex_digest
from .reconstruction import TABLE_LIMITS, Operation

MAX_NATIVE = 8_404_992
MAX_HEAD = 49_152
MAX_MESSAGE = 8_470_528
MAX_PROOF = 65_536


def closed(value, names, code):
    check(type(value) is dict and set(value) == set(names.split()), code)


def cursor(value, tag, owner=None):
    check(type(value) is list and len(value) == 3 and type(value[0]) is str and
          (owner is None or value[0] == owner) and value[1:] == [tag.generation, tag.root], "sync_cursor")
    return tuple(value)


def entries(value, maximum, code):
    check(type(value) is list and len(value) <= maximum, code)
    result = {}
    for pair in value:
        check(type(pair) is list and len(pair) == 2, code)
        key = canonical(pair[0])
        check(key not in result, "sync_duplicate_key")
        result[key] = pair
    return result


def owner_clock(value, binding):
    closed(value, "bootId clockDomain boottimeMs ownerEpoch uid hostScope", "sync_owner_clock")
    check(type(value["boottimeMs"]) is int and value["boottimeMs"] >= 0, "sync_owner_clock")
    check(type(value["uid"]) is int and value["uid"] >= 0, "sync_owner_clock")
    check(type(value["clockDomain"]) is str and re.fullmatch(r"time:\[[0-9]+\]", value["clockDomain"]),
          "sync_owner_clock")
    for name in ("bootId", "clockDomain", "ownerEpoch", "uid", "hostScope"):
        check(name in binding and type(value[name]) is type(binding[name]) and value[name] == binding[name],
              "sync_owner_clock_binding")


def read_native(raw, descriptor):
    document = decode(raw, MAX_NATIVE)
    check(type(document) is dict and "descriptor" in document and
          canonical(document["descriptor"]) == descriptor.native_descriptor, "sync_native_descriptor")
    kind = document.get("kind")
    if kind == "baseline":
        closed(document, "kind descriptor nativeBinding tag cursor tables", "sync_baseline_shape")
        check(type(document["nativeBinding"]) is dict, "sync_native_binding")
        tag = NativeTag.parse(document["tag"])
        cursor(document["cursor"], tag, document["nativeBinding"].get("ownerEpoch"))
        check(type(document["tables"]) is dict and set(document["tables"]) == set(SPACES), "sync_table_registry")
        for name, table in document["tables"].items():
            entries(table, TABLE_LIMITS[name], "sync_table_capacity")
    elif kind == "transaction":
        closed(document, "kind descriptor nativeBindingDigest transactionId baseTag resultTag baseCursor resultCursor operations",
               "sync_transaction_shape")
        base, result = NativeTag.parse(document["baseTag"]), NativeTag.parse(document["resultTag"])
        check(document["nativeBindingDigest"] == base.binding == result.binding and
              result.generation == base.generation + 1, "sync_transaction_tag")
        before = cursor(document["baseCursor"], base)
        cursor(document["resultCursor"], result, before[0])
        hex_digest(document["transactionId"])
        content = {key: value for key, value in document.items() if key != "transactionId"}
        check(document["transactionId"] == sha256(b"mesh-sync-transaction\0" + framed(canonical(content))).hexdigest(),
              "sync_transaction_id")
        check(type(document["operations"]) is dict and set(document["operations"]) == set(SPACES),
              "sync_operation_registry")
        for name, changes in document["operations"].items():
            check(type(changes) is list and len(changes) <= TABLE_LIMITS[name] * 2, "sync_operation_capacity")
            seen = set()
            for operation in changes:
                check(type(operation) is list and len(operation) in (3, 4), "sync_operation_shape")
                check(operation[0] == "put" and len(operation) == 4 or
                      operation[0] == "remove" and len(operation) == 3 and operation[2] is not None,
                      "sync_operation_shape")
                if operation[2] is not None:
                    hex_digest(operation[2])
                key = canonical(operation[1])
                check(key not in seen, "sync_duplicate_operation")
                seen.add(key)
    elif kind == "head":
        check(len(raw) <= MAX_HEAD, "sync_head_capacity")
        closed(document, "kind descriptor nativeBindingDigest tag challenge ownerClock originalReceipts cohortHeads attenuation",
               "sync_head_shape")
        tag = NativeTag.parse(document["tag"])
        check(document["nativeBindingDigest"] == tag.binding, "sync_head_binding")
        for name in ("originalReceipts", "cohortHeads", "attenuation"):
            entries(document[name], 32, "sync_head_entry_capacity")
        for pair in document["originalReceipts"]:
            check(len(canonical(pair)) + 1 <= 768, "sync_head_receipt_capacity")
        for pair in document["cohortHeads"]:
            check(len(canonical(pair)) + 1 <= 384, "sync_head_cohort_capacity")
        fixed = {**document, "originalReceipts": [], "cohortHeads": []}
        check(len(canonical(fixed)) <= 8192, "sync_head_fixed_capacity")
        check(len(canonical(document["challenge"])) <= 4096, "sync_challenge_capacity")
    else:
        check(False, "sync_native_kind")
    return document


def operations(document):
    """Mint internal immutable operations only after strict frame checks."""
    return tuple(Operation(name, change[0], Atom.own(change[1]), change[2],
                           None if change[0] == "remove" else Atom.own(change[3]))
                 for name in SPACES for change in document["operations"][name])
