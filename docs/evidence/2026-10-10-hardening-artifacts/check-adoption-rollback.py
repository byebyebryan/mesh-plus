import ast,base64,hashlib,importlib.machinery,importlib.util,json,stat,tempfile,types,zipfile
from pathlib import Path
helper=Path('/tmp/mesh-hardening/adoption/adopt10.py')
tree=ast.parse(helper.read_text());outer=next(n for n in tree.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and ast.unparse(n.test).startswith("args.operation == 'capture'"));inner=next(n for n in outer.orelse if isinstance(n,ast.If));code=compile(ast.Module(body=inner.orelse,type_ignores=[]),str(helper),'exec')
loader=importlib.machinery.SourceFileLoader('owned_ops','/tmp/mesh-hardening/adoption/managed-baseline-source/scripts/tmux-observer-operations');spec=importlib.util.spec_from_loader(loader.name,loader);old=importlib.util.module_from_spec(spec);loader.exec_module(old)
results=[]
for failure in (False,True):
 with tempfile.TemporaryDirectory() as name:
  home=Path(name);old.HOME=home;payloads={};selected={};trace=[]
  for kind in ('core','frontend'):
   root=home/kind;root.mkdir();(root/'payload').write_bytes(b'selected')
   archive=home/(kind+'.zip');info=zipfile.ZipInfo('payload');info.external_attr=(stat.S_IFREG|0o644)<<16
   with zipfile.ZipFile(archive,'w') as z:z.writestr(info,b'baseline')
   files={'payload':{'bytes':8,'sha256':hashlib.sha256(b'baseline').hexdigest()}}
   payloads[kind]={'prefix':kind,'archive':str(archive),'archiveSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':files};selected[kind]={'prefix':kind}
  (home/'control').write_bytes(b'selected');(home/'control').chmod(0o644)
  baseline={'data':base64.b64encode(b'baseline').decode(),'mode':0o644}
  captured={'payloads':payloads,'controls':{'control':baseline}};actual={'control':old.node(home/'control')}
  args=types.SimpleNamespace(operation='restore',source='new',baseline_source='old')
  def check(source,label,cap):
   expected=b'baseline' if source=='old' else b'selected'
   assert all((home/k/'payload').read_bytes()==expected for k in ('core','frontend'))
   assert (home/'control').read_bytes()==expected;trace.append(label)
   if failure and label=='restored':raise RuntimeError('owned restored-cohort check failed')
  def payload_check(value):assert all((home/k/'payload').read_bytes()==b'selected' for k in ('core','frontend'))
  namespace={'old':old,'args':args,'captured':captured,'actual':actual,'controls':['control'],'home':home,'selection':lambda source:selected,'verify':check,'verify_payloads':payload_check,'stop_topology':lambda cap,label,**kwargs:trace.append(label),'start_topology':lambda cap,label:trace.append(label)}
  try:exec(code,namespace)
  except RuntimeError:
   assert failure
  else:assert not failure
  expected=b'selected' if failure else b'baseline'
  assert all((home/k/'payload').read_bytes()==expected for k in ('core','frontend')) and (home/'control').read_bytes()==expected
  assert not list(home.glob('.tmux-rollback-*'))
  results.append({'injectedPostStartFailure':failure,'state':'passed','trace':trace})
report={'state':'passed','scope':'Actual archived filesystem/control transaction; unit operations and live verifiers mocked; not live rollback acceptance','helperSha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'cases':results}
Path('/tmp/mesh-hardening/adoption/adoption-rollback-owned.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
