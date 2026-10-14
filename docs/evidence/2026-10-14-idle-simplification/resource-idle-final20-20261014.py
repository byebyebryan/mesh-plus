import subprocess,time,json
from pathlib import Path
r=Path('/tmp/mesh-idle-execution-20261014')
harness='/tmp/tmux-final-idle-harness-20261014/scripts/profile-idle-mesh'
for variant in ('before','installed20'):
 name='resource-only-'+variant
 command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(r/(variant+'-paths.json')),'--output',str(r/name),'--sessions','0','--seconds','15']
 with (r/(name+'.log')).open('w') as out:
  job=subprocess.Popen(command,stdout=out,stderr=subprocess.STDOUT)
  try:
   time.sleep(8)
   subprocess.run(['/tmp/mesh-idle-review-20261014/.venv/bin/python','/tmp/mesh-idle-review-20261014/scripts/sample-idle-resources.py','--run',str(r/name),'--output',str(r/'resources-final20.jsonl')],check=True)
  finally:status=job.wait()
 if status:raise SystemExit(name+' failed')
print('Matched resource-only fixtures complete; their CPU figures are excluded',flush=True)
