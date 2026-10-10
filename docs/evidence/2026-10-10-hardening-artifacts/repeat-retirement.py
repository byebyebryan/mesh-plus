import sys,time,json,unittest
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=['/home/bryan/code/tmux-observer/tests','/home/bryan/code/tmux-observer/tests_mesh']
from test_fleet_mesh import MeshFleetTests
start=MeshFleetTests.start
def steady_start(self,root):
 with patch('mesh_plus.client.ROTATION_HANDLES',4080):return start(self,root)
fails=[];before=time.monotonic()
with patch.object(MeshFleetTests,'start',steady_start):
 for i in range(30):
  result=unittest.TestResult();MeshFleetTests('test_rotation_can_overlap_retiring_local_bridge_handler').run(result)
  if not result.wasSuccessful():fails.append({'iteration':i+1,'errors':len(result.errors),'failures':len(result.failures)})
  if (i+1)%5==0:print(json.dumps({'completed':i+1,'failed':len(fails)}),flush=True)
Path('/tmp/mesh-hardening/adoption/retirement-steady.json').write_text(json.dumps({'state':'failed' if fails else 'passed','cases':30,'failures':fails,'elapsedSeconds':time.monotonic()-before,'scope':'Actual IPC; production budget for initial readiness, synthetic budget 4 for three retirement/rotation overlaps'},indent=2)+'\n')
raise SystemExit(bool(fails))
