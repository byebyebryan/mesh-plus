from pathlib import Path
import fcntl,subprocess,json,hashlib,os
OUT=Path(__file__).resolve().parent/'gc-review-3';OUT.mkdir(mode=0o700)
ROOT=Path('/home/bryan/.cache/agent-observer-working-set-20261018');after=ROOT/'final-mesh-bfa91a69';before=ROOT/'final-mesh-b9e8488e'
code=r'''
import gc;gc.disable()
import sys,json,unittest,tempfile,contextlib,shutil,hashlib
from pathlib import Path
source,tests,output,mode=sys.argv[1:];output=Path(output);output.mkdir(mode=0o700)
sys.path[:0]=[source,tests]
import test_transport
test_transport.SOURCE_ROOT=Path(source)
real=tempfile.TemporaryDirectory
class audited_temp(real):
 def cleanup(self):
  p=Path(self.name)/'close-receipt.json'
  if p.exists():shutil.copyfile(p,output/'captured-close-receipt.json')
  return super().cleanup()
tempfile.TemporaryDirectory=audited_temp
names=['test_transport.TransportTests.test_client_close_reaches_bridge_after_delayed_forward_and_exits_normally'] if mode=='before' else ['test_transport','test_terminal_lifetime']
r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
modules={}
for name,m in sys.modules.items():
 if name=='mesh_plus' or name.startswith('mesh_plus.'):
  p=Path(m.__file__);modules[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
x={'mode':mode,'gcDisabled':not gc.isenabled(),'tests':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'skips':len(r.skipped),'modules':modules,'closeReceipt':json.loads((output/'captured-close-receipt.json').read_text())}
assert x['closeReceipt']['bridgeReaped'] is True
if mode=='before':assert (r.testsRun,len(r.failures),len(r.errors),len(r.skipped))==(1,1,0,0) and x['closeReceipt']['bridgeReturncode']==1
else:assert r.wasSuccessful() and not r.skipped and r.testsRun==39 and x['closeReceipt']['bridgeReturncode']==0
(output/'result.json').write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
'''
pyths={'314':'/home/bryan/code/mesh-plus/.venv/bin/python','311':'/home/bryan/code/agent-observer/.local/active-feed-20261016/installed311/bin/python'}
res=[]
with open('/home/bryan/.cache/agent-active-feed-cpu.lock') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for py,p in pyths.items():
  for mode,source in [('before',before),('after',after)]:
   target=OUT/(py+'-'+mode)
   with (OUT/(py+'-'+mode+'.log')).open('wb') as f:r=subprocess.run(['rtk','proxy',p,'-I','-B','-c',code,str(source/'src'),str(after/'tests'),str(target),mode],stdout=f,stderr=subprocess.STDOUT,timeout=45)
   assert r.returncode==0,(py,mode,r.returncode)
   x=json.loads((target/'result.json').read_text())
   for a in x['modules'].values():assert str(Path(a['path']).resolve()).startswith(str(source/'src')) and hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()==a['sha256']
   res.append({'python':py,'mode':mode,'tests':x['tests'],'errors':x['errors'],'failures':x['failures'],'skips':x['skips'],'loadedMeshPins':len(x['modules']),'bridgeReaped':True,'bridgeReturncode':x['closeReceipt']['bridgeReturncode'],'resultSha256':hashlib.sha256((target/'result.json').read_bytes()).hexdigest()})
(OUT/'summary.json').write_text(json.dumps({'cases':res,'sharedLock':True,'testOnlyAudit':'capturesclose-receiptbeforetemporarydirectory cleanup; normativeSourceandtestfilesunchanged'},indent=2)+'\n');print(json.dumps(res,indent=2))
