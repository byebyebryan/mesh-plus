import hashlib,json,os,signal,subprocess,time
from pathlib import Path
root=Path('/home/bryan/code/mesh-plus')
private=Path('/tmp/mesh-hardening')
def birth(pid):
 try: return Path(f'/proc/{pid}/stat').read_text().rpartition(') ')[2].split()[19]
 except FileNotFoundError: return None
def descendants(pid):
 pending=[pid]; found={}
 while pending:
  current=pending.pop()
  if current in found: continue
  value=birth(current)
  if value is None: continue
  found[current]=value
  try:
   for task in Path(f'/proc/{current}/task').iterdir():
    pending.extend(int(n) for n in (task/'children').read_text().split())
  except FileNotFoundError: pass
 return found
started=time.monotonic()
with (private/'process-abort.log').open('wb') as log:
 process=subprocess.Popen([str(private/'venv/bin/python'),str(root/'scripts/measure-processes.py'),'--domain','tmux','--carrier','ssh','--frame',str(private/'native-tmux.json'),'--processes','4','--seconds','60','--report',str(private/'aborted-matrix.json')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 time.sleep(8)
 owned=descendants(process.pid)
 assert process.poll() is None and len(owned)>4
 process.send_signal(signal.SIGINT)
 try: process.wait(timeout=20)
 except subprocess.TimeoutExpired:
  os.killpg(process.pid,signal.SIGKILL)
  process.wait(timeout=5)
 time.sleep(1)
 remaining=[pid for pid,ticks in owned.items() if birth(pid)==ticks]
 report={'state':'passed' if not remaining else 'failed','ownedProcessesObserved':len(owned),'remainingOwnedProcesses':len(remaining),'elapsedSeconds':round(time.monotonic()-started,3),'harnessSha256':hashlib.sha256((root/'scripts/measure-processes.py').read_bytes()).hexdigest(),'acceptanceHarnessSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':['Four owned localhost SSH fixture workers; no ordinary endpoints or native collection','Real SIGINT of coordinator; successful graceful cleanup, not forced-kill coverage','Process identity rechecked by kernel birth ticks; input and traceback remain private']}
 (private/'process-abort.json').write_text(json.dumps(report,indent=2)+chr(10))
 print(json.dumps(report))
 for pid in remaining:
  if birth(pid)==owned[pid]:
   try: os.kill(pid,signal.SIGKILL)
   except ProcessLookupError: pass
 assert not remaining
