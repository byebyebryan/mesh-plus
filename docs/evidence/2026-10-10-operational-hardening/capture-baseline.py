"""Read-only installed selections and service incarnations; no native records."""

import hashlib
import json
import subprocess
from pathlib import Path

home = Path.home()
roots = {"mesh": home / ".local/share/mesh-plus/0.1.0a9/python/mesh_plus",
         "tmux": home / ".local/share/tmux-observer/python/tmux_observer",
         "tmuxClient": home / ".local/share/tmux-observer/python/tmux_observer_client",
         "agentBridge": home / ".local/share/agent-observer/0.5.0a12-e292e689a1dd1b32-mesh-a9",
         "agentReader": home / ".local/share/agent-observer/0.5.0a13-646a067dcba3b1a3-mesh-a9"}
artifacts = {name: {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in {".py", ".json"}}
             for name, root in roots.items()}
listed = subprocess.check_output(["systemctl", "--user", "list-units", "--all", "--plain", "--no-legend"], text=True)
units = [line.split()[0] for line in listed.splitlines()
         if line.split()[0].startswith(("tmux-observer-", "mesh-plus-agent.", "agent-observer."))]
services = {}
for unit in units:
    fields = subprocess.check_output(["systemctl", "--user", "show", unit, "-p", "MainPID",
                                     "-p", "ActiveState", "-p", "ExecMainStartTimestampMonotonic"], text=True)
    value = dict(line.split("=", 1) for line in fields.splitlines())
    pid = int(value["MainPID"])
    if pid:
        value["processBirthTicks"] = Path(f"/proc/{pid}/stat").read_text().rpartition(") ")[2].split()[19]
    services[unit] = value
controls = {}
for relative in (".config/systemd/user/agent-observer.service", ".config/systemd/user/mesh-plus-agent.service",
                 ".config/mesh-plus/sources.toml", ".config/kitty/kitty.conf"):
    path = home / relative
    if path.is_file():
        controls[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps({"format": "mesh-plus.installed-baseline.v1", "artifacts": artifacts,
                  "services": services, "protectedControlDigests": controls}, indent=2))
