"""Synthetic operation-controlled cache, validated by the pinned pure Tmux facade."""

import copy
import hashlib
import json

from tmux_observer.mesh_profile import TmuxMeshProfile

from mesh_plus.testing.sample import Publisher


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Trace:
    def __init__(self, rows, *, expired=False):
        if type(rows) is not int or not 1 <= rows <= 1024:
            raise ValueError("trace_rows")
        self.profile = TmuxMeshProfile()
        self.codec = self.profile.bind("beta", "controlled")
        self.frame = Publisher("tmux", "beta", profile=self.profile).frame
        seed = self.frame["snapshot"]["sessions"][0]
        self.frame["snapshot"]["sessions"] = [
            {**copy.deepcopy(seed), "sessionId": "$" + str(100 + index), "name": "trace-00000"}
            for index in range(rows)
        ]
        if expired:
            keys = {"encodedAt", "startedAt", "finishedAt", "acceptedAt", "expiresAt", "lastAttemptAt"}

            def age(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key in keys and type(item) is int:
                            value[key] -= 20000
                        else:
                            age(item)
                elif isinstance(value, list):
                    for item in value:
                        age(item)
            age(self.frame)
        self.step = 0
        self.original_receipts = copy.deepcopy(self.codec.inspect_native(self.frame).receipts)

    def advance(self, step):
        if type(step) is not int or step != self.step + 1:
            raise ValueError("trace_step_order")
        value = copy.deepcopy(self.frame)
        value["viewRevision"] += 1
        value["sequence"] += 1
        for row in value["snapshot"]["sessions"]:
            row["name"] = "trace-" + str(step).zfill(5)
        state = self.codec.inspect_native(value)
        if state.receipts != self.original_receipts:
            raise ValueError("trace_receipts_changed")
        self.frame, self.step = value, step

    def describe(self):
        # Normalize only this synthetic evidence; runtime frames keep actual clocks.
        value = copy.deepcopy(self.frame)
        anchor = value["encodedAt"]
        keys = {"encodedAt", "startedAt", "finishedAt", "acceptedAt", "expiresAt", "lastAttemptAt"}

        def normalize(item):
            if isinstance(item, dict):
                for key, child in item.items():
                    if key in keys and type(child) is int:
                        item[key] = child - anchor
                    elif key == "bootId":
                        item[key] = "normalized-boot"
                    elif key == "timeNamespace":
                        item[key] = "normalized-time"
                    else:
                        normalize(child)
            elif isinstance(item, list):
                for child in item:
                    normalize(child)
        normalize(value)
        return {"step": self.step, "rows": len(value["snapshot"]["sessions"]),
                "normalizedFrameSha256": hashlib.sha256(canonical(value).encode()).hexdigest(),
                "originalReceiptsUnchanged": True}
