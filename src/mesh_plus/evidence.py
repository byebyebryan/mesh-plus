"""Pure networking clock, canonical digest and bridge schema helpers."""

import hashlib
import json
import os
import re
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from .protocol import check


def clock_domain():
    namespace = re.fullmatch(r"time:\[([0-9]+)\]", os.readlink("/proc/self/ns/time"))
    check(namespace is not None, "clock_domain")
    return {"bootId": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "timeNamespace": "time:" + namespace[1]}


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def bridge_validator():
    return Draft202012Validator(json.loads(files("mesh_plus").joinpath("schemas", "bridge-reply.schema.json").read_text()))

