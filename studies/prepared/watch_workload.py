"""Changing admitted fixtures; no acquisition, carrier or lease renewal."""

import copy
import hashlib

from mesh_plus.evidence import digest
from mesh_plus.protocol import encode


def publications(seed, profile, count, change):
    frames = []
    for index in range(count):
        frame = copy.deepcopy(seed)
        frame["mesh"]["reader"].update(sequence=index + 1, revision=index + 1)
        if change == "native":
            for row in frame["sessions"]:
                row["name"] = "watch-" + str(index)
            for host in frame["mesh"]["hosts"]:
                service = host["owner"]["service"]
                service["sequence"] += index
                service["viewRevision"] += index
                proof = host["delivery"]["proof"]
                if proof is not None:
                    records = [row for row in frame["sessions"] if profile.record_host(row) == host["hostId"]]
                    proof["payloadDigest"] = digest(profile.restore_native(host["owner"], records))
        frames.append(frame)
    assert len({digest(frame) for frame in frames}) == count
    assert all(host["receipts"] == original["receipts"] for frame in frames
               for host, original in zip(frame["mesh"]["hosts"], seed["mesh"]["hosts"]))
    return frames


def oracle(rows):
    return tuple((row["hostId"], row["sessionId"], row["name"]) for row in rows)


def normalized_digest(frames):
    """Cross-process shape/content oracle, removing volatile fixture evidence.

    Exact raw input bytes differ by process BOOTTIME, clock namespace and UUID.
    Compare row identities/names and stream ordering separately from those facts.
    """
    return hashlib.sha256(encode([{"rows": oracle(frame["sessions"]),
                                 "sequence": frame["mesh"]["reader"]["sequence"],
                                 "revision": frame["mesh"]["reader"]["revision"]} for frame in frames])).hexdigest()
