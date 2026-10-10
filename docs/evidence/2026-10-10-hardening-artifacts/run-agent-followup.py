import importlib.util,secrets,shlex,sys
from pathlib import Path
import mesh_plus.configured_read as configured
from mesh_plus.remote import connect_catalog_host
from mesh_plus.transport import ssh_argv,subprocess_channel
spec=importlib.util.spec_from_file_location('owned_profile','/tmp/mesh-hardening/adoption/profile-fleet-followup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ENTRY='/home/bryan/.local/share/agent-observer/0.5.0a16-94705baebfa51a96-mesh-a10-bridge/bin/mesh-plus'
async def owned_ssh(destination,source_id,**kwargs):
 nonce=secrets.token_hex(16);argv=ssh_argv(destination,source_id,nonce=nonce,**kwargs)
 command=shlex.split(argv[-1]);assert command[5]=='mesh-plus';command[5]=ENTRY;argv[-1]=shlex.join(command)
 return await subprocess_channel(argv,reached_nonce=nonce)
async def candidate_connect(catalog,host,domain,source,*,authority=None):
 assert domain=='agent' and authority is None
 return await connect_catalog_host(catalog,host,domain,source,authority=None,connector=owned_ssh)
configured.connect_catalog_host=candidate_connect
raise SystemExit(m.main())
