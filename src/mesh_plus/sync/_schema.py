"""Owned index schemas; third-party validator state is operation-scoped.

Only trusted configured descriptors supply schemas. No wire-selected code or
remote schema resolver is installed here. Descriptor construction rejects
external references; local references retain jsonschema's normal semantics.
"""

import sys
from dataclasses import dataclass

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .budget import OwnedUnit, _payload_size
from .canonical import decode, decode_reservation, thaw


def _no_retrieve(uri):
    raise NoSuchResource(ref=uri)


_LOCAL_REGISTRY = Registry(retrieve=_no_retrieve)


@dataclass(frozen=True, slots=True)
class OwnedSchema(OwnedUnit):
    document: object
    private_bytes: int
    scratch_bytes: int

    @classmethod
    def retain(cls, raw, ledger):
        with ledger.reserve(decode_reservation(raw, 65536)) as reservation:
            document = decode(raw, 65536)
            schema = cls(document, _payload_size(document), 1024 * 1024 + 32 * len(raw))
            ledger.retain(schema, reservation=reservation)
            return schema

    def owned_intrinsic(self):
        return self.private_bytes + sys.getsizeof(self.private_bytes) + sys.getsizeof(self.scratch_bytes)

    def validate(self, atom, ledger):
        # Avoid a retained jsonschema/referencing registry per cache/index.
        # Reserve compiler, resolver, validation stack and detached instance
        # scratch before entering the reviewed third-party validation routine.
        # The fixed-schema peak also remains subject to the external RSS gate.
        with ledger.reserve(self.scratch_bytes + atom.copy_budget):
            validator, instance = None, None
            try:
                instance = thaw(atom.value)
                validator = Draft202012Validator(self.document, registry=_LOCAL_REGISTRY)
                validator.validate(instance)
            finally:
                validator = instance = None
