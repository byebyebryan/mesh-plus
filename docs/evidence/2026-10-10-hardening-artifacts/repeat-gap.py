import json,sys,time,unittest
from pathlib import Path
sys.path[:0]=['/home/bryan/code/tmux-observer/tests','/home/bryan/code/tmux-observer/tests_mesh']
from test_fleet_mesh import MeshFleetTests
started=time.monotonic();failures=[]
for i in range(50):
 result=unittest.TestResult();MeshFleetTests('test_grouped_refresh_gap_is_a_terminal_scope_revocation').run(result)
 if not result.wasSuccessful():failures.append({'iteration':i+1,'failures':len(result.failures),'errors':len(result.errors)})
 if (i+1)%10==0:print(json.dumps({'completed':i+1,'failed':len(failures)}),flush=True)
report={'state':'passed' if not failures else 'failed','cases':50,'failures':failures,'elapsedSeconds':time.monotonic()-started,'scope':'Owned actual IPC gap/control/full-resync; no ordinary native refresh'}
Path('/tmp/mesh-hardening/adoption/refresh-gap-50.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(bool(failures))
