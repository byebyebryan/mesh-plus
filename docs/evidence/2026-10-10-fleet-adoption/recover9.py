from pathlib import Path
import subprocess,json,sys,time
host,source=sys.argv[1:];root=Path(source);work=Path('/tmp/mesh-a8-adoption')
def run(args,label):
 with (work/(label+'-'+host+'.log')).open('wb') as out:
  p=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,timeout=90)
 if p.returncode:raise RuntimeError(label+' failed')
def pid():return int(subprocess.check_output(['systemctl','--user','show','mesh-plus-agent.service','-p','MainPID','--value']))
run([str(root/'scripts/tmux-observer-operations'),'recover','--host',host,'--output',str(work/('final-tmux-recovery-'+host+'.json'))],'recovery-tmux')
before=pid();run(['systemctl','--user','restart','mesh-plus-agent.service'],'recovery-agent-restart');after=pid();assert before!=after and after>0
deadline=time.monotonic()+30
while True:
 try:
  run([str(root/'scripts/agent-observer-mesh-operations'),'--host',host],'recovery-agent-verify');break
 except RuntimeError:
  if time.monotonic()>=deadline:raise
  time.sleep(.25)
run(['/usr/bin/python3',str(work/'check-agent-cli.py'),str(work/('final-recovered-agent-cli-'+host+'.json'))],'recovery-agent-cli')
run(['/usr/bin/python3',str(work/'protected.py'),str(work/'protected-after-recovery.json'),str(work/'protected-before.json')],'recovery-protected')
result={'host':host,'state':'passed','agentBridgePidBefore':before,'agentBridgePidAfter':after,'collectorPreserved':True,'kernelPeerAndInterpreterVerified':True,'nativeSessionsPreserved':True,'scope':'Selected cached publishers and Reader restart; no provider or native session actions'}
(work/('final-agent-recovery-'+host+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
