from pathlib import Path
import os,fcntl,json,subprocess,time,hashlib
ROOT=Path("/home/bryan/code/mesh-plus-working-set")
OUT=Path(__file__).resolve().parent
PY="/home/bryan/code/mesh-plus/.venv/bin/python"
env=dict(os.environ,PATH=str(Path(PY).parent)+":"+os.environ["PATH"],PYTHONPATH=str(ROOT/"src"),PYTHONDONTWRITEBYTECODE="1")
files=["src/mesh_plus/transport.py","tests/test_transport.py","docs/terminal-lifetime.md"]
def pins():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
before=pins()
with open("/home/bryan/.cache/agent-active-feed-cpu.lock","r") as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 start=time.monotonic()
 with (OUT/"check.log").open("wb") as log:r=subprocess.run(["rtk","proxy",PY,"scripts/check.py"],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
 elapsed=time.monotonic()-start
assert before==pins()
report={"returncode":r.returncode,"elapsedSeconds":elapsed,"interpreter":PY,"sourcePins":before,"logSha256":hashlib.sha256((OUT/"check.log").read_bytes()).hexdigest(),"sharedLockHeld":True}
(OUT/"result.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report));raise SystemExit(r.returncode)
