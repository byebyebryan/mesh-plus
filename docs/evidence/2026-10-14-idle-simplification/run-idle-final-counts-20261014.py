import subprocess,json,time
from pathlib import Path
root=Path('/tmp/mesh-idle-execution-20261014')
while not (root/'secondary-complete.json').exists():time.sleep(2)
harness='/tmp/tmux-final-idle-harness-20261014/scripts/profile-idle-mesh'
for variant in ('before','candidate'):
 name='final-counts-'+variant
 command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/(variant+'-paths.json')),'--output',str(root/name),'--sessions','2','--seconds','30','--counters']
 with (root/(name+'.log')).open('w') as out:
  status=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT).returncode
 if status:raise SystemExit(name+' failed')
 print(name+' complete',flush=True)
command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/'installed19-paths.json'),'--output',str(root/'installed-one-reader'),'--sessions','2','--seconds','15','--readers','1']
with (root/'installed-one-reader.log').open('w') as out:
 status=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT).returncode
if status:raise SystemExit('one-reader failed')
(root/'all-complete.json').write_text(json.dumps(dict(state='complete',ended=time.time()))+'\n')
