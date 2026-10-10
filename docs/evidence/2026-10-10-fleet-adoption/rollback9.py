from pathlib import Path
import subprocess,json,sys,base64,os
host,source,oldsource=sys.argv[1:];home=Path.home();work=Path('/tmp/mesh-a8-adoption');current=Path(source);old=Path(oldsource)
def run(args,label):
 with (work/(label+'-'+host+'.log')).open('wb') as out:
  p=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,timeout=180)
 if p.returncode:raise RuntimeError(label+' failed; see private log')
def node(p):
 if p.is_symlink():return {'link':os.readlink(p)}
 return {'data':base64.b64encode(p.read_bytes()).decode(),'mode':p.stat().st_mode&0o777}
controls=json.loads((home/'.local/state/agent-observer/mesh-rollback/20261010-a8/controls.json').read_text());selected={n:node(home/n) for n in controls}
run([str(current/'scripts/agent-observer-mesh-operations'),'--host',host],'rollback-agent-before')
run(['systemctl','--user','stop','mesh-plus-agent.service'],'rollback-stop-bridge')
try:
 run([str(current/'scripts/tmux-observer-operations'),'rollback','--host',host,'--before',str(home/'.local/state/tmux-observer/rollback/20261010-mesh-a8/baseline.json'),'--output',str(work/('final-rollback-'+host+'.json'))],'rollback-pair')
 for n,v in controls.items():
  p=home/n;assert node(p)==selected[n],'foreign Agent control drift'
  temp=p.with_name('.mesh-rollback-owned-'+p.name);assert not temp.exists() and not temp.is_symlink()
  if 'link' in v:temp.symlink_to(v['link'])
  else:temp.write_bytes(base64.b64decode(v['data']));temp.chmod(v['mode'])
  temp.replace(p)
 run(['systemctl','--user','daemon-reload'],'rollback-reload')
 run(['systemctl','--user','start','tmux-observer-owner@'+host+'.service','mesh-plus-agent.service','tmux-observer-desktop.service'],'rollback-start')
 run([str(old/'scripts/tmux-observer-operations'),'verify','--host',host,'--output',str(work/('final-baseline-tmux-'+host+'.json'))],'rollback-baseline-tmux')
 run([str(old/'scripts/agent-observer-mesh-operations'),'--host',host],'rollback-baseline-agent')
 run(['/usr/bin/python3',str(work/'check-agent-cli.py'),str(work/('final-baseline-agent-cli-'+host+'.json'))],'rollback-baseline-cli')
 run(['/usr/bin/python3',str(work/'protected.py'),str(work/'protected-after-rollback.json'),str(work/'protected-before.json')],'rollback-protected')
finally:
 run(['systemctl','--user','daemon-reload'],'reselect-reload')
 run(['systemctl','--user','start','tmux-observer-owner@'+host+'.service','mesh-plus-agent.service','tmux-observer-desktop.service'],'reselect-start-prerequisites')
 run(['/usr/bin/python3',str(work/'deploy9.py'),host,source,'--captured-baseline'],'reselect-final')
run(['/usr/bin/python3',str(work/'check-agent-cli.py'),str(work/('final-reselected-agent-cli-'+host+'.json'))],'reselect-cli')
run(['/usr/bin/python3',str(work/'protected.py'),str(work/'protected-final.json'),str(work/'protected-before.json')],'reselect-protected')
result={'host':host,'state':'passed','baseline':'Observer a2 / Plus a2 / shared Mesh a7 and private Agent SDK a4','reselected':'Observer a4 / Plus a4 / shared and private SDK a9','collectorPreserved':True,'nativeSessionsPreserved':True,'limits':['Serial live paired selection rollback; no provider/session actions or physical suspend']}
(work/('final-rollback-reselection-'+host+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
