import ast,base64,hashlib,importlib.machinery,importlib.util,json,stat,tempfile,types,zipfile
from pathlib import Path
helper=Path('/tmp/mesh-hardening/adoption/adopt10.py');tree=ast.parse(helper.read_text());outer=next(n for n in tree.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and ast.unparse(n.test).startswith("args.operation == 'capture'"));inner=next(n for n in outer.orelse if isinstance(n,ast.If));code=compile(ast.Module(body=inner.body,type_ignores=[]),str(helper),'exec')
loader=importlib.machinery.SourceFileLoader('owned_ops','/tmp/mesh-hardening/adoption/managed-baseline-source/scripts/tmux-observer-operations');spec=importlib.util.spec_from_loader(loader.name,loader);old=importlib.util.module_from_spec(spec);loader.exec_module(old)
results=[]
for failure in ('none','partial-apply','post-start'):
 with tempfile.TemporaryDirectory() as name:
  home=Path(name);old.HOME=home;payloads={};selected={};trace=[]
  for kind in ('core','frontend'):
   root=home/kind;root.mkdir();(root/'payload').write_bytes(b'baseline')
   archive=home/(kind+'.zip');info=zipfile.ZipInfo('payload');info.external_attr=(stat.S_IFREG|0o644)<<16
   with zipfile.ZipFile(archive,'w') as z:z.writestr(info,b'baseline')
   files={'payload':{'bytes':8,'sha256':hashlib.sha256(b'baseline').hexdigest()}}
   payloads[kind]={'prefix':kind,'archive':str(archive),'archiveSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':files};selected[kind]={'prefix':kind}
  (home/'control').write_bytes(b'baseline');(home/'control').chmod(0o644)
  captured={'payloads':payloads,'controls':{'control':old.node(home/'control')}};args=types.SimpleNamespace(operation='select',source='new',baseline_source='old')
  def check(source,label,cap):
   expected=b'baseline' if source=='old' else b'selected'
   assert all((home/k/'payload').read_bytes()==expected for k in ('core','frontend')) and (home/'control').read_bytes()==expected
   trace.append(label)
   if failure=='post-start' and label=='selected':raise RuntimeError('owned selected-cohort check failed')
  def payload_check(value):assert all((home/k/'payload').read_bytes()==b'baseline' for k in ('core','frontend'))
  def run(argv,label):
   trace.append(label)
   if label=='select-apply':
    (home/'core/payload').write_bytes(b'selected');(home/'control').write_bytes(b'selected')
    if failure=='partial-apply':raise RuntimeError('owned partial apply')
    (home/'frontend/payload').write_bytes(b'selected')
   return b''
  namespace={'old':old,'args':args,'captured':captured,'controls':['control'],'home':home,'selection':lambda source:selected,'verify':check,'verify_payloads':payload_check,'run':run,'stop_topology':lambda cap,label,**kwargs:trace.append(label),'start_topology':lambda cap,label:trace.append(label)}
  try:exec(code,namespace)
  except RuntimeError:assert failure!='none'
  else:assert failure=='none'
  expected=b'selected' if failure=='none' else b'baseline'
  assert all((home/k/'payload').read_bytes()==expected for k in ('core','frontend')) and (home/'control').read_bytes()==expected
  assert not list(home.glob('.tmux-rollback-*'));results.append({'failureStage':failure,'state':'passed','trace':trace})
report={'state':'passed','scope':'Actual archived filesystem/control restoration after partial apply or post-start rejection; live units/apply/verifiers mocked; not live adoption acceptance','helperSha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'cases':results}
Path('/tmp/mesh-hardening/adoption/adoption-select-owned.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
