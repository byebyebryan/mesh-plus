"""Optional process-local admission handoff. Serialized bytes own the facts.

This is not a wire token, digest cache, or sandbox for installed profile code.
Only the exact admitting profile instance and unchanged callbacks may consume it.
"""

from dataclasses import dataclass

from .protocol import check, decode_json, encode
from .state import NativeState, ProfileDescriptor

ADMISSION_INTERFACE_VERSION = 1
_CAPACITY = 16 * 1024 * 1024
_CALLBACKS = ("bind", "validate_response", "restore_native", "record_host", "record_identity",
              "record_receipts", "record_eligible")


def _binding(profile):
    return profile.descriptor, tuple(getattr(profile, name) for name in _CALLBACKS)


@dataclass(frozen=True, init=False, repr=False, eq=False, slots=True)
class AdmittedResponse:
    """Opaque owned admission from Reader; exports are detached mutable JSON."""

    _profile: object
    _binding: tuple
    _payload: bytes
    _header: bytes
    _states: bytes

    def __init__(self):
        raise TypeError("AdmittedResponse is produced by Reader")

    @classmethod
    def _owned(cls, response, states, profile):
        value = object.__new__(cls)
        # Native records already equal each host's aggregate projection. Store
        # only receipts/chronology and counts beside the immutable response.
        summaries = {host: {"clock": state.clock, "publisher": state.publisher,
                            "emitted": state.emitted_ms, "receipts": state.receipts,
                            "count": len(state.records)} for host, state in states.items()}
        for name, item in (("_profile", profile), ("_binding", _binding(profile)),
                           ("_payload", encode(response)), ("_header", encode({**response, "sessions": []})),
                           ("_states", encode(summaries))):
            object.__setattr__(value, name, item)
        return value

    def _open(self, profile):
        actual = profile.descriptor
        check(profile is self._profile and type(actual) is ProfileDescriptor and
              all(type(getattr(actual, key)) is int for key in ("sdk_version", "native_version", "frame_bytes")) and
              _binding(profile) == self._binding, "admission_binding")
        response = self.snapshot()
        summaries = decode_json(self._states, _CAPACITY)
        states, offset = {}, 0
        for host in response["mesh"]["hosts"]:
            if host["owner"] is None:
                continue
            summary = summaries[host["hostId"]]
            end = offset + summary["count"]
            states[host["hostId"]] = NativeState(host["owner"], response["sessions"][offset:end],
                                                summary["clock"], summary["publisher"], summary["emitted"],
                                                summary["receipts"])
            offset = end
        return response, states

    def snapshot(self):
        return decode_json(self._payload, _CAPACITY)

    def context(self):
        return decode_json(self._header, _CAPACITY)
