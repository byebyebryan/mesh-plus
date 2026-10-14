import subprocess,json,time,os,hashlib
from pathlib import Path
root=Path('/tmp/mesh-idle-execution-20261014')
harness='/tmp/tmux-final-idle-harness-20261014/scripts/profile-idle-mesh'
plan=dict(artifact='a20/a10',mesh='f7bef1e',observer='f693674',cases=['empty','active-two'],order=['before','installed20','installed20','before'],seconds=120,reason='bounded final-wheel regression screen after completed-expiry registration fix; a19 long runs remain separate')
(root/'final20-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
while not (root/'all-complete.json').exists():time.sleep(2)
for case in plan['cases']:
 for index,variant in enumerate(plan['order'],1):
  name=f'final20-{case}-{index}-{variant}'
  command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/(variant+'-paths.json')),'--output',str(root/name),'--sessions','0' if case=='empty' else '2','--seconds','120']
  if case=='active-two':command.append('--active')
  (root/(name+'-inputs.json')).write_text(json.dumps(dict(command=command,started=time.time(),loadAverage=os.getloadavg(),plan=plan),indent=2)+'\n')
  with (root/(name+'.log')).open('w') as out:
   status=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT).returncode
  if status:raise SystemExit(name+' failed')
  print(name,json.loads((root/name/'result.json').read_text())['cpu'],flush=True)
for variant in ('before','installed20'):
 name='final20-counts-'+variant
 command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/(variant+'-paths.json')),'--output',str(root/name),'--sessions','2','--seconds','30','--counters']
 with (root/(name+'.log')).open('w') as out:
  status=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT).returncode
 if status:raise SystemExit(name+' failed')
(root/'final20-complete.json').write_text(json.dumps(dict(state='complete',ended=time.time()))+'\n')
