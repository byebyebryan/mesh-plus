import subprocess,json,os,time,hashlib
from pathlib import Path
root=Path('/tmp/mesh-idle-execution-20261014')
harness='/tmp/tmux-s1-idle-20261014/scripts/profile-idle-mesh'
# Predeclared before long-run results: empty fleet is the primary rare-session use case.
plan=dict(primaryCase='empty headless two-host fleet',secondaryCase='two sessions per host, 120-second ABBA',blocks=2,secondsPerRun=300,order=['before','candidate','candidate','before'],inputs={'before':'7f5e26c','candidate':'ef4d4cc','observer':'31e3625'},gate='saving exceeds baseline variability, 20 percent Fleet CPU is initial target; no sample reduction or active-workload regression',exclusions=['SSH daemon helpers','tmux servers','physical suspend','live deployment'])
(root/'qualification-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
# Only begin after the separate screen driver completes; no simultaneous fixtures.
while not (root/'screen-complete.json').exists():time.sleep(2)
for block in (1,2):
 for index,variant in enumerate(plan['order']):
  name=f'qualified-empty-{block}-{index+1}-{variant}'
  command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/(variant+'-paths.json')),'--output',str(root/name),'--sessions','0','--seconds','300']
  record=dict(command=command,loadAverage=os.getloadavg(),started=time.time(),inputs=plan['inputs'])
  (root/(name+'-inputs.json')).write_text(json.dumps(record,indent=2)+'\n')
  with (root/(name+'.log')).open('w') as log:
   status=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
  if status:raise SystemExit(name+' failed')
  print(name,json.loads((root/name/'result.json').read_text())['cpu'],flush=True)
(root/'qualification-complete.json').write_text(json.dumps(dict(state='complete',ended=time.time()))+'\n')
