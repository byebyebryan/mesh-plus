import asyncio,json,sys,tempfile,uuid
from pathlib import Path
from mesh_plus import client as client_module
from mesh_plus.bridge import Bridge
from mesh_plus.configured_read import configured_reader
from mesh_plus.library_authority import LibraryMeshAuthority
from mesh_plus.observer import ObserverAdapter,clock_domain
from mesh_plus.transport import IPCServer,boottime_ms
from mesh_plus.view import ReadGuard,row_host

async def run(domain,report):
 authority=LibraryMeshAuthority();server=None;temporary=tempfile.TemporaryDirectory(prefix='mesh-native-rotation-');reader=None;stream=None
 original=client_module.ROTATION_HANDLES;client_module.ROTATION_HANDLES=4
 events=[];epochs={};revoked=set();recovered=set();request=uuid.uuid4().hex
 try:
  catalog=await authority.load();source='tmux_default' if domain=='tmux' else 'agent';socket=Path('/run/user/1000/mesh-plus-agent/read.sock')
  if domain=='tmux':
   socket=Path(temporary.name)/'bridge.sock';adapter=ObserverAdapter(domain,catalog.local_host,source,Path('/run/user/1000/tmux-observer/owner.sock'));server=await IPCServer(socket,Bridge(adapter).serve).start()
  reader=await configured_reader(domain,source=source,socket=socket,authority=authority)
  guard=ReadGuard(domain,request);stream=reader.watch(proof_interval=.1,request_id=request)
  async def consume():
   async for frame in stream:
    guard.accept(frame)
    if 'mesh' not in frame:raise RuntimeError('terminal')
    current=guard.current(boottime_ms(),clock_domain())
    for h in frame['mesh']['hosts']:
     host=h['hostId'];d=h['delivery'];epochs[host]=max(epochs.get(host,0),d['epoch'])
     if (d.get('error') or {}).get('code')=='channel_rotation_required':
      assert all(row_host(domain,row)!=host for row in current);revoked.add(host);events.append({'host':host,'event':'revoked','epoch':d['epoch']})
     elif host in revoked and d['status']=='ready':
      recovered.add(host)
    if all(epochs.get(h['id'],0)>=3 for h in catalog.hosts) and len(recovered)==len(catalog.hosts):return
  await asyncio.wait_for(consume(),20)
  assert revoked==recovered=={h['id'] for h in catalog.hosts}
 finally:
  if stream is not None:await stream.aclose()
  if server is not None:await server.close()
  client_module.ROTATION_HANDLES=original;authority.close();temporary.cleanup()
 metrics=reader.inspect()
 Path(report).write_text(json.dumps({'state':'cleanup_check','domain':domain,'epochs':epochs,'metrics':metrics},indent=2)+'\n')
 assert not metrics['activeConnections'] and not metrics['cleanupFailures'] and not metrics['partial']
 result={'state':'passed','domain':domain,'epochs':epochs,'revokedHosts':sorted(revoked),'recoveredHosts':sorted(recovered),'events':events,'metrics':metrics,'testOnlyHandleBudget':4,'testOnlyProofIntervalSeconds':.1,'ordinaryCollectorCadenceChanged':False,'limits':['Actual cached services and SSH; private additional Reader with accelerated Client budget and proof interval','Not prolonged production-budget rotation or independent native provider truth']}
 Path(report).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'state':'passed','domain':domain,'epochs':epochs,'rotations':metrics['rotations']}))

asyncio.run(run(*sys.argv[1:]))
