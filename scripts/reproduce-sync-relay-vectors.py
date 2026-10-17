#!/usr/bin/env python3
"""Stdlib A1 r2 binding/splicing/attenuation oracle, not a relay implementation.

Fixture descriptors and native roots grant no admission. No Mesh or Observer
runtime is imported. --check compares exact retained artifact bytes.
"""

import argparse
import json
from hashlib import sha256
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(canonical(value)).hexdigest()


def framed(raw):
    return len(raw).to_bytes(8, "big") + raw


def binding_digest(value, *, native=False):
    prefix = b"mesh-sync-native-binding\0" if native else b"mesh-sync-source-binding\0"
    return sha256(prefix + framed(canonical(value))).hexdigest()


def source_tag(binding, native_tag):
    root = sha256(b"mesh-sync-source\0" + framed(canonical(binding)) +
                  bytes.fromhex(native_tag[2])).hexdigest()
    return {"native": native_tag, "binding": binding_digest(binding), "root": root}


def splice(value, key, raw):
    """Reference framing only: canonical outer keys, one unchanged JSON value."""
    assert key in value
    return b"{" + b",".join(canonical(name) + b":" +
                            (raw if name == key else canonical(value[name]))
                            for name in sorted(value)) + b"}"


def lease(native_remaining, native_time, bridge_time, sent, received, margin=100):
    values = native_remaining, native_time, bridge_time, sent, received, margin
    if not all(type(value) is int and value >= 0 for value in values):
        raise ValueError("integer")
    if bridge_time < native_time:
        raise ValueError("clock")
    if not (100 <= margin <= 2000 and sent <= received <= sent + 2000):
        raise ValueError("deadline")
    remaining = max(0, native_remaining - (bridge_time - native_time))
    expiry = received + max(0, remaining - (received - sent) - margin)
    return {"remaining": remaining, "remoteExpiry": expiry}


def build():
    native_descriptor = {"protocol": "fixture.native/1", "version": 1,
                         "view": "full", "schema": "a" * 64}
    encoding = {"id": "fixture.compact/1", "schema": "b" * 64,
                "nativeDescriptor": digest(native_descriptor)}
    native_binding = {"protocol": "fixture.native/1", "hostScope": "fixture",
                      "uid": 1000, "ownerEpoch": "04" * 16, "bootId": "owner-boot",
                      "clockDomain": "time:[123]", "view": "full",
                      "sourceContexts": [], "scopeContinuity": []}
    native = [binding_digest(native_binding, native=True), 7, "11" * 32]
    full_binding = {"host": "fixture", "source": "full", "profile": "fixture.mesh-sync.v1",
                    "profileSchema": "c" * 64, "nativeDescriptor": digest(native_descriptor)}
    alias_binding = {**full_binding, "source": "second_alias"}
    tag = source_tag(full_binding, native)
    alias_tag = source_tag(alias_binding, native)
    request = {"readerEpoch": "01" * 16, "requestId": "fixture-1",
               "catalogRevision": "catalog-fixture", "hosts": ["fixture"],
               "route": "fixed-ssh", "channelEpoch": "02" * 16,
               "bridgeId": "03" * 16, "role": "transport-relay",
               "encodingDigest": digest(encoding)}
    material_request = {**request, "role": "material-publisher"}
    changed_encoding = {**encoding, "schema": "d" * 64}
    changed_request = {**request, "encodingDigest": digest(changed_encoding)}
    challenge = {"nonce": "05" * 32, "target": digest(tag), "request": digest(request)}
    key = ["fixture", "scope", "runtime"]
    head = {"kind": "head", "descriptor": native_descriptor,
            "nativeBindingDigest": native[0], "tag": native, "challenge": challenge,
            "ownerClock": {"bootId": "owner-boot", "clockDomain": "time:[123]",
                           "boottimeMs": 10000, "ownerEpoch": "04" * 16,
                           "uid": 1000, "hostScope": "fixture"},
            "originalReceipts": [[key, {"fixtureOnly": True}]],
            "cohortHeads": [], "attenuation": [[key, 500]]}
    # Whitespace deliberately distinguishes exact wire preservation from C(head).
    head_raw = json.dumps(head, ensure_ascii=False, indent=1).encode("utf-8")
    proof = {"protocol": "mesh.state-sync/1", "kind": "proof",
             "descriptor": {"fixtureOnly": True}, "sourceBinding": full_binding,
             "sourceTag": tag, "requestBinding": request, "challenge": challenge,
             "bridgeId": request["bridgeId"],
             "bridgeClock": {"bootId": "owner-boot", "timeNamespace": "time:123",
                             "boottimeMs": 10015},
             "head": head, "remaining": [[key, 485]]}
    proof_raw = splice(proof, "head", head_raw)
    outer = {"protocol": "mesh.state-sync/1", "kind": "delivery",
             "requestBinding": request, "sequence": 1, "payload": proof}
    outer_raw = splice(outer, "payload", proof_raw)
    assert json.loads(outer_raw) == outer
    assert outer_raw.count(head_raw) == 1
    assert head_raw != canonical(head)
    assert len(outer_raw) - len(head_raw) <= 16384 and len(outer_raw) <= 65536
    assert tag["native"] == alias_tag["native"] and tag["root"] != alias_tag["root"]
    assert len(canonical(request)) <= 4096
    assert len({digest(request), digest(material_request), digest(changed_request)}) == 3
    moved_native = [native[0], 8, "22" * 32]
    moved_tag = source_tag(full_binding, moved_native)
    assert digest(moved_tag) != challenge["target"]

    vectors = [
        {"name": "encoding-binding", "input": encoding, "sha256": digest(encoding)},
        {"name": "request-role-relay", "input": request, "sha256": digest(request)},
        {"name": "request-role-material", "input": material_request,
         "sha256": digest(material_request)},
        {"name": "request-other-encoding", "input": changed_request,
         "sha256": digest(changed_request)},
        {"name": "source-full", "binding": full_binding, "tag": tag},
        {"name": "source-second-alias", "binding": alias_binding, "tag": alias_tag},
        {"name": "nonce-challenge", "value": challenge,
         "canonical": canonical(challenge).decode(), "sha256": digest(challenge)},
        {"name": "proof-exact-native-splice", "nativeHead": head_raw.decode(),
         "nativeHeadSha256": sha256(head_raw).hexdigest(),
         "delivery": outer_raw.decode(), "deliverySha256": sha256(outer_raw).hexdigest(),
         "nativeBytes": len(head_raw), "allEnvelopeBytes": len(outer_raw) - len(head_raw),
         "totalBytes": len(outer_raw), "sequence": 1},
        {"name": "within-binding-moved-head", "requested": tag, "actual": moved_tag,
         "unchangedChallenge": challenge,
         "requiredReaderAction": "revoke; separate catch-up; at most one fresh nonce"},
    ]
    for name, args in (("attenuate-15ms", (500, 10000, 10015, 20000, 20060)),
                       ("zero-native-remaining", (0, 10000, 10015, 20000, 20060)),
                       ("elapsed-remaining", (500, 10000, 10500, 20000, 20060))):
        vectors.append({"name": name, "input": list(args), "output": lease(*args)})
    assert vectors[-3]["output"] == {"remaining": 485, "remoteExpiry": 20385}
    rejections = []
    for name, args in (("boolean-remaining", (True, 10000, 10015, 20000, 20060)),
                       ("negative-remaining", (-1, 10000, 10015, 20000, 20060)),
                       ("bridge-before-native", (500, 10000, 9999, 20000, 20060)),
                       ("whole-rtt-over-two-seconds", (500, 10000, 10015, 20000, 22001))):
        try:
            lease(*args)
        except ValueError as error:
            rejections.append({"name": name, "input": list(args), "reject": str(error)})
        else:
            raise AssertionError(name)
    return {"format": "mesh-a1-relay-api-r2-arithmetic", "fixtureOnly": True,
            "scope": "binding, exact native splicing and attenuation; no material or transport admission",
            "vectors": vectors, "rejections": rejections,
            "pendingRuntime": ["native scanner and independent Reader validation",
                               "role/encoding/callback replacement rejection",
                               "relay/cache and cross-alias handle rejection",
                               "all intake/output/pin/DTO peaks and at-cap rejection",
                               "paused watch, four-tx batch, head/control",
                               "GC-disabled held-error retirement and repeated cancellation",
                               "moved head and counted bounded recovery",
                               "installed IPC/SSH and dense/end-to-end gates"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--check", type=Path)
    args = parser.parse_args()
    result = build()
    raw = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    if args.output:
        args.output.write_bytes(raw)
    else:
        assert args.check.read_bytes() == raw, "retained fixture bytes differ"
    print(json.dumps({"vectors": len(result["vectors"]), "rejections": len(result["rejections"]),
                      "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
                      "scope": result["scope"]}, sort_keys=True))


if __name__ == "__main__":
    main()
