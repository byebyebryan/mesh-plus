import subprocess,json,os,time
from pathlib import Path
root=Path('/tmp/mesh-idle-execution-20261014')
harness='/tmp/tmux-qualification-harness-20261014/scripts/profile-idle-mesh'
plan=dict(cases=['two','active-two'],order=['before','candidate','candidate','before'],seconds=120,primaryPlan='qualification-plan.json',scope='secondary clean small-roster and active-update CPU regression screen',inputs={'before':'7f5e26c','candidate':'ef4d4cc','observer':'31e3625','harness':'b07e484'})
(root/'secondary-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
while not (root/'qualification-complete.json').exists():time.sleep(2)
for case in plan['cases']:
 for index,variant in enumerate(plan['order']):
  name=f'qualified-{case}-{index+1}-{variant}'
  command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/(variant+'-paths.json')),'--output',str(root/name),'--sessions','2','--seconds','120']
  if case=='active-two':command.append('--active')
  metadata=dict(command=command,loadAverage=os.getloadavg(),started=time.time(),inputs=plan['inputs'])
  (root/(name+'-inputs.json')).write_text(json.dumps(metadata,indent=2)+'\n')
  with (root/(name+'.log')).open('w') as out:
   status=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT).returncode
  if status:raise SystemExit(name+' failed')
  print(name,json.loads((root/name/'result.json').read_text())['cpu'],flush=True)
(root/'secondary-complete.json').write_text(json.dumps(dict(state='complete',ended=time.time()))+'\n')
