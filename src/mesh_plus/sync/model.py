"""Immutable sync descriptors, typed patches and bounded proof projections."""

import re
from dataclasses import dataclass
from hashlib import sha256

from ..protocol import check
from ._constants import COMMITMENT, SYNC_INTERFACE_VERSION, SYNC_PROTOCOL
from .budget import OwnedUnit
from .canonical import Atom, canonical, decode

SPACES = ("records", "bodies", "observations", "memberships", "receipts", "cohorts", "scopes", "metadata")
FIELDS = ("runtime", "phase", "kind", "savedIdentity", "activity", "outcome", "workspace", "lastUpdated", "latestTurn")
HEX = re.compile(r"[0-9a-f]{64}\Z")


def hex_digest(value):
    check(type(value) is str and HEX.fullmatch(value) is not None, "sync_digest")
    return value


@dataclass(frozen=True, slots=True)
class IndexSpec(OwnedUnit):
    name: str
    key_schema: bytes
    value_schema: bytes
    max_entries: int = 36864
    max_value_bytes: int = 16384
    ordered: bool = False

    def __post_init__(self):
        check(type(self.name) is str and 0 < len(self.name) <= 128 and not self.name.startswith("$"), "sync_index_name")
        check(type(self.max_entries) is int and 0 < self.max_entries <= 36864, "sync_index_capacity")
        check(type(self.max_value_bytes) is int and 0 < self.max_value_bytes <= 65536, "sync_index_capacity")
        check(type(self.ordered) is bool, "sync_index_order")
        for schema in (self.key_schema, self.value_schema):
            check(type(schema) is bytes and len(schema) <= 65536, "sync_index_schema")
            document = decode(schema, 65536)
            check(canonical(document) == schema, "sync_index_schema")
            stack = [document]
            while stack:
                item = stack.pop()
                if type(item) is dict:
                    for name in ("$ref", "$dynamicRef"):
                        if name in item:
                            check(type(item[name]) is str and item[name].startswith("#"), "sync_external_schema_ref")
                    stack.extend(item.values())
                elif type(item) is list:
                    stack.extend(item)

    def owned_children(self):
        return (self.name, self.key_schema, self.value_schema, self.max_entries, self.max_value_bytes, self.ordered)


@dataclass(frozen=True, slots=True)
class SyncDescriptor(OwnedUnit):
    profile_id: str
    profile_schema_digest: str
    native_protocol: str
    native_version: int
    native_schema_digest: str
    native_descriptor: bytes
    indexes: tuple = ()
    spaces: tuple = SPACES
    fields: tuple = FIELDS
    sync_interface: int = SYNC_INTERFACE_VERSION

    def __post_init__(self):
        check(type(self.sync_interface) is int and self.sync_interface == 1, "sync_interface")
        for name in (self.profile_id, self.native_protocol):
            check(type(name) is str and 0 < len(name) <= 128 and name.isascii() and
                  not any(c.isspace() or ord(c) < 32 for c in name), "sync_descriptor_name")
        for value in (self.profile_schema_digest, self.native_schema_digest):
            hex_digest(value)
        check(type(self.native_version) is int and self.native_version == 1, "sync_native_version")
        check(type(self.native_descriptor) is bytes and len(self.native_descriptor) <= 16384, "sync_native_descriptor")
        check(canonical(decode(self.native_descriptor, 16384)) == self.native_descriptor, "sync_native_descriptor")
        check(type(self.spaces) is tuple and self.spaces == SPACES, "sync_spaces")
        check(type(self.fields) is tuple and 0 < len(self.fields) <= 64 and
              all(type(name) is str and 0 < len(name) <= 128 for name in self.fields) and
              len(set(self.fields)) == len(self.fields), "sync_fields")
        check(type(self.indexes) is tuple and len(self.indexes) <= 32 and
              all(type(spec) is IndexSpec for spec in self.indexes), "sync_indexes")
        check(len({spec.name for spec in self.indexes}) == len(self.indexes), "sync_duplicate_index")

    @property
    def native_descriptor_digest(self):
        return sha256(self.native_descriptor).hexdigest()

    def owned_children(self):
        return tuple(getattr(self, name) for name in self.__slots__)

    def wire(self):
        return {"protocol": SYNC_PROTOCOL, "syncInterface": self.sync_interface, "commitment": COMMITMENT,
                "profile": self.profile_id, "profileSchema": self.profile_schema_digest,
                "nativeProtocol": self.native_protocol, "nativeVersion": self.native_version,
                "nativeSchema": self.native_schema_digest, "nativeDescriptor": self.native_descriptor_digest,
                "spaces": list(self.spaces), "fields": list(self.fields),
                "indexes": [{"name": spec.name, "keySchema": sha256(spec.key_schema).hexdigest(),
                             "valueSchema": sha256(spec.value_schema).hexdigest(),
                             "maxEntries": spec.max_entries, "maxValueBytes": spec.max_value_bytes,
                             "ordered": spec.ordered}
                            for spec in self.indexes]}


@dataclass(frozen=True, slots=True)
class NativeTag(OwnedUnit):
    binding: str
    generation: int
    root: str

    def __post_init__(self):
        hex_digest(self.binding)
        hex_digest(self.root)
        check(type(self.generation) is int and 0 <= self.generation < 2**64, "sync_generation")

    @classmethod
    def parse(cls, value):
        check(type(value) is list and len(value) == 3, "sync_tag")
        return cls(*value)

    def wire(self):
        return [self.binding, self.generation, self.root]

    def owned_children(self):
        return (self.binding, self.generation, self.root)


@dataclass(frozen=True, slots=True)
class SourceTag(OwnedUnit):
    native: NativeTag
    binding: str
    root: str

    def __post_init__(self):
        check(type(self.native) is NativeTag, "sync_tag")
        hex_digest(self.binding)
        hex_digest(self.root)

    def wire(self):
        return {"native": self.native.wire(), "binding": self.binding, "root": self.root}

    def owned_children(self):
        return self.native, self.binding, self.root


@dataclass(frozen=True, slots=True)
class IndexWrite:
    index: str
    key: object
    value: object


@dataclass(frozen=True, slots=True)
class IndexRemove:
    index: str
    key: object


@dataclass(frozen=True, slots=True)
class FieldTokenWrite:
    record_ref: object
    field: str
    token: str | None


@dataclass(frozen=True, slots=True)
class RuleWrite:
    key: object
    value: object


@dataclass(frozen=True, slots=True)
class DerivedMembershipOperation:
    op: str
    key: object
    expected: str | None
    value: str | None = None


@dataclass(frozen=True, slots=True)
class DomainIndexPatch:
    writes: tuple = ()
    removes: tuple = ()
    field_tokens: tuple = ()
    membership_expansion: tuple = ()
    changed_rules: tuple = ()
    removed_rules: tuple = ()
    affected_scopes: tuple = ()
    invalidations: tuple = ()

    def __post_init__(self):
        check(all(type(getattr(self, name)) is tuple for name in self.__slots__), "sync_patch_tuple")


@dataclass(frozen=True, slots=True)
class OriginalReceipt(OwnedUnit):
    key: Atom
    value_hash: str
    accepted: int
    health: str
    expiry_ms: int | None

    def __post_init__(self):
        check(type(self.key) is Atom, "sync_receipt_key")
        hex_digest(self.value_hash)
        check(type(self.accepted) is int and self.accepted >= 0, "sync_receipt_accepted")
        check(type(self.health) is str and self.health in
              {"current", "partial", "stale", "unknown", "unsupported", "unavailable", "warming"},
              "sync_receipt_health")
        check(self.expiry_ms is None or type(self.expiry_ms) is int and self.expiry_ms >= 0, "sync_receipt_expiry")
        if self.health in {"current", "partial"}:
            check(self.accepted > 0 and self.expiry_ms is not None, "sync_receipt_positive")

    def owned_children(self):
        return (self.key, self.value_hash, self.accepted, self.health, self.expiry_ms)


@dataclass(frozen=True, slots=True)
class HeadRules:
    original_receipts: tuple = ()
    allowed_receipts: tuple | None = None

    def __post_init__(self):
        check(type(self.original_receipts) is tuple and len(self.original_receipts) <= 32 and
              all(type(item) is OriginalReceipt for item in self.original_receipts), "sync_head_receipts")
        check(self.allowed_receipts is None or type(self.allowed_receipts) is tuple, "sync_head_restrictions")
