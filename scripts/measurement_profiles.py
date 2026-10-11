"""Trusted, fixed benchmark profiles with the same reviewed native admission."""

from mesh_plus.api import ReferenceProfile
from mesh_plus.evidence import bridge_validator, digest
from mesh_plus.protocol import check
from mesh_plus.testing.sample import Profile


def make_profile(domain, kind):
    if kind == "reference":
        return ReferenceProfile(domain)
    if kind != "independent":
        raise ValueError("measurement_profile")
    if domain == "tmux":
        from tmux_observer.delivery import validate_service_frame as native_validate
    else:
        from agent_observer.service_public import validate_frame as native_validate
    profile = Profile(domain)
    bind = profile.bind
    class Codec:
        def __init__(self, host, source):
            self.host, self.source = host, source
            self.profile_id = profile.descriptor.profile_id
            self.projection = bind(host, source)

        def inspect_native(self, frame):
            native_validate(frame)
            return self.projection.inspect_native(frame)

        def validate_bridge(self, payload):
            bridge_validator().validate(payload)
            check(payload["hostId"] == self.host and payload["sourceId"] == self.source, "bridge_source_binding")
            check(payload["kind"] in {"candidate", "proof"} and payload["error"] is None and
                  payload["ownerFrame"] is not None, "bridge_success_shape")
            state = self.inspect_native(payload["ownerFrame"])
            check(payload["ownerDigest"] == digest(payload["ownerFrame"]), "owner_digest")
            check(state.clock == payload["clock"] and state.emitted_ms <= payload["encodedAtMs"], "bridge_clock")
            if payload["kind"] == "candidate":
                check(payload["nonce"] is None and not payload["remaining"], "candidate_receipts")
            else:
                check(payload["nonce"] is not None, "proof_nonce")
                expected = []
                for original in state.receipts:
                    receipt = dict(original)
                    expiry = receipt.pop("expiry")
                    remaining = max(0, expiry - payload["encodedAtMs"]) if receipt["health"] in {"current", "partial"} else 0
                    expected.append({**receipt, "remainingMs": remaining})
                check(payload["remaining"] == expected, "proof_receipts")
    profile.bind = Codec
    return profile
