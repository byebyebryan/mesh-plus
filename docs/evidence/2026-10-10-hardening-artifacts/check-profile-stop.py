import sys,asyncio,tempfile,importlib.util,types,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/home/bryan/code/mesh-plus/tests')
from test_reader_runtime import CachedPublisher
from mesh_plus.bridge import Bridge
from mesh_plus.transport import IPCServer,connect_ipc
from mesh_plus.client import Client
from mesh_plus.reader import Reader,Endpoint
spec=importlib.util.spec_from_file_location('owned_profile','/home/bryan/code/mesh-plus/scripts/profile-fleet.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Authority:
 def close(self):pass
async def check():
 with tempfile.TemporaryDirectory() as name:
  servers=[];endpoints=[]
  for host in ('local','remote'):
   pub=CachedPublisher('agent',host);path=Path(name)/host
   servers.append(await IPCServer(path,Bridge(pub).serve,max_clients=2).start())
   async def connect(pub=pub,path=path):return await Client.connect(await connect_ipc(path),host=pub.host,source='default',profile=pub.profile,codec=pub.validate)
   endpoints.append(Endpoint(host,host=='local',None if host=='local' else 'sha256:'+'a'*64,connect))
  async def catalog():return 'sha256:'+'b'*64
  async def reader(*args,**kwargs):return Reader('agent',endpoints,local_host='local',catalog_revision=await catalog(),catalog_check=catalog)
  args=types.SimpleNamespace(domain='agent',source='default',socket=Path('/unused'),scope='fleet',readers=1,seconds=30,native_socket=False,proof_interval=.1,minimum_host_rotations=2,stop_after_rotations=True,progress_report=None)
  try:
   with patch.object(m,'LibraryMeshAuthority',Authority),patch.object(m,'configured_reader',reader),patch('mesh_plus.client.ROTATION_HANDLES',4):v=await m.profile(args)
   assert v['state']=='passed' and v['elapsedSeconds']<30 and all(n>=2 for n in v['frames'][0]['hostRecoveries'].values())
   Path('/tmp/mesh-hardening/adoption/profile-stop-owned.json').write_text(json.dumps(v,indent=2)+'\n');print('Owned two-host IPC stop/coverage/cleanup passed')
  finally:
   for s in servers:await s.close()
asyncio.run(check())
