from pathlib import Path
import subprocess,json,sys,os
host,source=sys.argv[1:3];root=Path(source);home=Path.home();work=Path('/tmp/mesh-a8-adoption')
forced=[]
if len(sys.argv)>3:
 assert sys.argv[3:]==['--captured-baseline']
 import base64,stat
 def node(path):
  if path.is_symlink():return {'link':os.readlink(path)}
  if not path.exists():return None
  return {'data':base64.b64encode(path.read_bytes()).decode(),'mode':stat.S_IMODE(path.stat().st_mode)}
 controls=json.loads((home/'.local/state/tmux-observer/rollback/20261010-mesh-a8/baseline.json').read_text())['controls']
 controls.update(json.loads((home/'.local/state/agent-observer/mesh-rollback/20261010-a8/controls.json').read_text()))
 for rel,value in controls.items():assert node(home/rel)==value,'foreign baseline control drift: '+rel
 forced=['--force']
targets=['.local/share/rofi/extensions/tmux-plus','.local/share/mesh-plus/0.1.0a9/python','.local/share/tmux-observer/python','.local/share/tmux-observer/bin/tmux-observer-client','.local/bin/mesh-plus','.local/bin/agent-observer','.config/systemd/user/mesh-plus-agent.service','.config/systemd/user/tmux-observer-owner@.service','.config/systemd/user/tmux-observer-fleet@.service']
def run(args,label,timeout=120):
 with (work/(label+'-'+host+'.log')).open('wb') as out:
  p=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
 if p.returncode:raise RuntimeError(label+' failed; see private log')
(home/'.local/share/mesh-plus/0.1.0a9').mkdir(parents=True,exist_ok=True)
run(['chezmoi','--source',source,'apply',*forced,'--dry-run','--verbose',*[str(home/t) for t in targets]],'dry-run')
assert subprocess.run(['pgrep','-x','rofi'],stdout=subprocess.DEVNULL).returncode==1
units=subprocess.check_output(['systemctl','--user','list-units','--type=service','--state=active','--no-legend','--plain','tmux-observer-fleet@*.service']).decode().splitlines();assert len(units)==1
fleet=units[0].split()[0]
run(['systemctl','--user','stop',fleet,'tmux-observer-owner@'+host+'.service','mesh-plus-agent.service'],'stop')
try:
 run(['chezmoi','--source',source,'apply',*forced,'--verbose',*[str(home/t) for t in targets]],'apply')
finally:
 run(['systemctl','--user','daemon-reload'],'reload')
 run(['systemctl','--user','start','tmux-observer-owner@'+host+'.service','mesh-plus-agent.service'],'start-owner')
 run(['systemctl','--user','start','tmux-observer-desktop.service'],'start-desktop')
run([str(root/'scripts/tmux-observer-operations'),'verify','--host',host,'--output',str(work/('tmux-verify-'+host+'.json'))],'tmux-verify')
run([str(root/'scripts/agent-observer-mesh-operations'),'--host',host],'agent-verify')
print(json.dumps({'host':host,'state':'passed','scopedTargets':len(targets)}))
