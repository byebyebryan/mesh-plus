"""Dedicated own-tick sampler using the reviewed PID-birth accounting primitives."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "performance"))
from measure import process  # noqa: E402


def sample(roles):
    current = []
    for role in roles:
        current.append({**process(role["pid"], role["birth"]), "role": role["role"]})
    fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:9]
    busy = sum(int(value) for index, value in enumerate(fields) if index not in (3, 4))
    return {"time": time.monotonic(), "roles": current, "systemBusyTicks": busy,
            "sampler": process(os.getpid(), memory=False)}


if __name__ == "__main__":
    for raw in sys.stdin:
        print(json.dumps(sample(json.loads(raw))), flush=True)
