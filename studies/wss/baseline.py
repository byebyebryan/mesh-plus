"""Capture exact study inputs without importing experimental runtime."""

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture():
    paths = [ROOT / "contracts/LOCK.json", ROOT / "src/mesh_plus/authority.py"]
    paths += sorted((ROOT / "src").rglob("*.py"))
    paths += sorted((ROOT / "src/mesh_plus/schemas").glob("*.json"))
    return {
        "format": "mesh-plus.wss-study.baseline.v1",
        "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in
                     ("mesh-plus", "jsonschema", "websockets", "tmux-observer", "agent-observer")},
        "runtimeInputs": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        "releasedWheel": {"name": "mesh_plus-0.1.0a13-py3-none-any.whl",
                          "sha256": "62b42bc76e7d79d95d89c41ee6f73c5e0169d24e2f1ac911c151c13f1f2b6f07"},
        "excluded": ["sibling source acceptance", "deployment", "WAN", "physical suspend",
                     "normal runtime promotion", "browser access"],
    }


if __name__ == "__main__":
    print(json.dumps(capture(), indent=2))
