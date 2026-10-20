"""Closed app-level packet contract for the opt-in complete-view feed."""

import json
import math
import re
from functools import lru_cache
from importlib.resources import files
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ..protocol import MAX_MESSAGE, ProtocolError, check
from .budget import FeedLimits

FEED_PROTOCOL = "mesh-plus.view-change-feed.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,127}")
_SOURCE_ID = re.compile(r"[a-z][a-z0-9_]{0,127}")
_HOST_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,16383}")


@lru_cache(maxsize=1)
def _validator():
    schema = json.loads(files("mesh_plus.view_feed").joinpath("packet.schema.json").read_text())
    return Draft202012Validator(schema)


def _string_bytes(value):
    """Exact compact JSON string length without allocating an encoded copy."""
    total = 2
    for char in value:
        point = ord(char)
        check(point != 0 and not 0xD800 <= point <= 0xDFFF, "view_feed_unicode")
        if char in {'"', "\\", "\b", "\f", "\n", "\r", "\t"}:
            total += 2
        elif point < 0x20:
            total += 6
        elif point < 0x80:
            total += 1
        elif point < 0x800:
            total += 2
        elif point < 0x10000:
            total += 3
        else:
            total += 4
    return total


def json_size(value, *, maximum=None, depth=0):
    """Count compact UTF-8 JSON bytes while bounding traversal depth."""
    check(depth <= 64, "tree_depth")
    kind = type(value)
    if kind is str:
        result = _string_bytes(value)
    elif kind in (int, float):
        if kind is float:
            check(math.isfinite(value), "nonfinite")
        # Avoid Python's decimal conversion limit on adversarial giant integers.
        if kind is int and value.bit_length() > 12_000_000:
            raise ProtocolError("message_capacity")
        result = len(json.dumps(value, separators=(",", ":"), allow_nan=False).encode("ascii"))
    elif kind in (bool, type(None)):
        result = 4 if value is True or value is None else 5 if value is False else 4
    elif isinstance(value, dict):
        result = 2
        first = True
        for key, child in value.items():
            check(type(key) is str, "invalid_json")
            result += (0 if first else 1) + _string_bytes(key) + 1
            result += json_size(child, maximum=maximum, depth=depth + 1)
            first = False
            if maximum is not None:
                check(result <= maximum, "message_capacity")
    elif isinstance(value, list):
        result = 2
        for index, child in enumerate(value):
            result += (0 if index == 0 else 1) + json_size(child, maximum=maximum, depth=depth + 1)
            if maximum is not None:
                check(result <= maximum, "message_capacity")
    else:
        raise ProtocolError("invalid_json")
    if maximum is not None:
        check(result <= maximum, "message_capacity")
    return result


def _key(value):
    check(isinstance(value, list) and 0 < len(value) <= 16 and
          all(type(part) in (str, int) for part in value), "view_feed_identity")
    check(all(type(part) is not str or len(part) <= 16384 for part in value), "view_feed_identity")
    return tuple(value)


def _uuid(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _packet_shape(packet, limits):
    check(type(limits) is FeedLimits, "view_feed_limits")
    check(isinstance(packet, dict), "view_feed_packet")
    try:
        _validator().validate(packet)
    except (ValidationError, RecursionError) as error:
        raise ProtocolError("view_feed_schema") from error

    check(_uuid(packet["streamId"]), "view_feed_stream")
    binding = packet["binding"]
    check(_HOST_ID.fullmatch(binding["hostId"]) is not None and
          _SOURCE_ID.fullmatch(binding["sourceId"]) is not None and
          _PROFILE_ID.fullmatch(binding["profileId"]) is not None and
          _DIGEST.fullmatch(binding["contractDigest"]) is not None and
          _uuid(binding["bridgeId"]) and type(binding["nativePublisher"]) is str and
          0 < len(binding["nativePublisher"]) <= 256 and
          isinstance(binding["selector"], dict), "view_feed_binding")
    check(isinstance(binding["nativeClock"], dict) and
          set(binding["nativeClock"]) == {"bootId", "timeNamespace"} and
          type(binding["nativeClock"]["bootId"]) is str and
          type(binding["nativeClock"]["timeNamespace"]) is str,
          "view_feed_binding")

    target = packet["target"]
    check(type(target["revision"]) is int and 1 <= target["revision"] <= 9007199254740991 and
          _DIGEST.fullmatch(target["digest"]) is not None, "view_feed_target")
    envelope = packet["envelope"]
    check(envelope["kind"] == "candidate" and envelope["nonce"] is None and envelope["error"] is None and
          envelope["ownerDigest"] == target["digest"] and envelope["hostId"] == binding["hostId"] and
          envelope["sourceId"] == binding["sourceId"] and envelope["bridgeId"] == binding["bridgeId"] and
          envelope["clock"] == binding["nativeClock"], "view_feed_envelope")
    check(_uuid(binding["bridgeId"]), "view_feed_binding")

    kind = packet["kind"]
    if kind == "replacement":
        check(packet["base"] is None and isinstance(packet["records"], list) and
              packet["upserts"] == [] and packet["removals"] == [] and isinstance(packet["order"], list),
              "view_feed_replacement")
        check(packet["reason"] != "delta", "view_feed_reason")
        keys = [_key(key) for key in packet["order"]]
        check(len(keys) == len(set(keys)) and len(keys) == len(packet["records"]), "view_feed_order")
    else:
        check(packet["reason"] == "delta", "view_feed_reason")
        base = packet["base"]
        check(type(base["revision"]) is int and base["revision"] >= 1 and
              target["revision"] == base["revision"] + 1 and _DIGEST.fullmatch(base["digest"]) is not None and
              packet["records"] is None, "view_feed_base")
        if packet["order"] is not None:
            keys = [_key(key) for key in packet["order"]]
            check(len(keys) == len(set(keys)), "view_feed_order")

    upsert_keys = []
    for item in packet["upserts"]:
        upsert_keys.append(_key(item["key"]))
    removal_keys = [_key(key) for key in packet["removals"]]
    check(len(upsert_keys) == len(set(upsert_keys)) and
          len(removal_keys) == len(set(removal_keys)) and
          not set(upsert_keys).intersection(removal_keys), "view_feed_operations")
    count = len(packet["records"] or [])
    count += len(upsert_keys) + len(removal_keys)
    if packet["order"] is not None:
        check(isinstance(packet["order"], list), "view_feed_order")
        count += len(packet["order"])
    check(count <= limits.max_records * 3, "view_feed_record_capacity")
    return packet


def validate_packet(packet, limits=None):
    """Validate only packet structure and application-level invariants.

    Base ownership, identity matching, reconstruction and native admission are
    deliberately handled by ``FeedReceiver.apply``.
    """
    limits = FeedLimits() if limits is None else limits
    size = json_size(packet, maximum=min(limits.max_packet_bytes, MAX_MESSAGE))
    check(size <= limits.max_packet_bytes, "view_feed_packet_capacity")
    _packet_shape(packet, limits)
    if packet["kind"] == "replacement":
        check(len(packet["records"]) <= limits.max_records and
              len(packet["order"]) <= limits.max_records, "view_feed_record_capacity")
    else:
        check(len(packet["upserts"]) <= limits.max_records and
              len(packet["removals"]) <= limits.max_records and
              (packet["order"] is None or len(packet["order"]) <= limits.max_records),
              "view_feed_record_capacity")
    return packet

