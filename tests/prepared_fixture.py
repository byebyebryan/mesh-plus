"""Explicit test-only static promise; not an owner facade or runtime adapter."""

from collections.abc import Mapping

from mesh_plus.api import NativeState, PreparationDescriptor, PreparedRule


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(child) for key, child in value.items()}
    if type(value) is tuple:
        return [thaw(child) for child in value]
    return value


class StaticPreparation:
    def __init__(self, profile):
        self.profile = profile
        self.descriptor = PreparationDescriptor(1, profile.descriptor, "mesh-test-static-v1")

    def prepare_rules(self, state):
        native = NativeState(thaw(state.owner), thaw(state.records), thaw(state.clock), state.publisher,
                             state.emitted_ms, thaw(state.receipts))
        return tuple(PreparedRule(self.profile.record_identity(row), self.profile.record_receipts(row, native),
                                  self.profile.record_eligible(row, native)) for row in native.records)
