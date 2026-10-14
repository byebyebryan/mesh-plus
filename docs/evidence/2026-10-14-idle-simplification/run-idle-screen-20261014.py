import subprocess,json,os,time
from pathlib import Path
root=Path('/tmp/mesh-idle-execution-20261014')
harness='/tmp/tmux-s1-idle-20261014/scripts/profile-idle-mesh'
cases=[(0,'B1','candidate'),(0,'B2','candidate'),(0,'A2','before'),(2,'A1','before'),(2,'B1','candidate'),(2,'B2','candidate'),(2,'A2','before')]
for sessions,label,variant in cases:
 name='s2-'+('empty' if sessions==0 else 'two')+'-'+label
 with (root/(name+'.log')).open('w') as out:
  command=['/usr/bin/python3.14','-I','-B',harness,'--runtime-paths',str(root/(variant+'-paths.json')),'--output',str(root/name),'--sessions',str(sessions),'--seconds','120']
  metadata=dict(command=command,loadAverage=os.getloadavg(),started=time.time(),meshInput='ef4d4cc' if variant=='candidate' else '7f5e26c',observerInput='31e3625')
  (root/(name+'-inputs.json')).write_text(json.dumps(metadata,indent=2)+'\n')
  status=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT).returncode
 if status:raise SystemExit(name+' failed')
 print(name,json.loads((root/name/'result.json').read_text())['cpu'],flush=True)
