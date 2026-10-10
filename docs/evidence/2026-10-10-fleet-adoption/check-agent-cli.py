import json,subprocess,sys,os
from pathlib import Path
results=[]
for args in [['mesh','snapshot','--scope','local'],['mesh','snapshot','--scope','fleet'],['mesh','watch','--scope','fleet','--count','4']]:
 p=subprocess.run(['agent-observer',*args],capture_output=True,timeout=40)
 assert p.returncode==0,(args,p.stderr[:300])
 frames=[json.loads(x) for x in p.stdout.splitlines()]
 assert frames and frames[-1]['mesh']['status']=='complete'
 assert all(x['protocol']=='agent-observer.mesh-candidate.v1' for x in frames)
 results.append({'command':args,'exit':p.returncode,'bytes':len(p.stdout),'profiles':[x['protocol'] for x in frames],'statuses':[x['mesh']['status'] for x in frames],'hosts':[[h['hostId'] for h in x['mesh']['hosts']] for x in frames]})
Path(sys.argv[1]).write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({'state':'passed','host':os.uname().nodename,'cases':len(results)}))
