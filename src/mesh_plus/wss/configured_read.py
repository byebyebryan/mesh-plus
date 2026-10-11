"""Explicit mixed IPC/SSH/WSS selection; no fallback or route-health writes."""

from pathlib import Path

from mesh_plus.client import Client
from mesh_plus.protocol import check
from mesh_plus.reader import Endpoint
from mesh_plus.remote import connect_catalog_host
from mesh_plus.state import check_binding, resolve_profile
from mesh_plus.transport import connect_ipc

from .carrier import connect
from .configuration import WSSReader


async def configured_reader(domain, *, selection, source, socket, scope="fleet", hosts=(), profile=None):
    """Compose an immutable selection using the existing pure domain profile.

    The caller owns Selection.close(). Registered remote hosts use WSS; other
    selected remote hosts retain their captured SSH route and token. WSS
    failures remain host outcomes, never a reason to switch carriers.
    """
    profile = resolve_profile(domain, profile)
    check(not selection.job.closed, "wss_configuration_closed")
    await selection.check()
    catalog = selection.catalog
    selected = catalog.select(scope, hosts)
    path = Path(socket)
    check(path.is_absolute(), "configured_socket_path")
    bindings = {binding.host: binding for binding in selection.bindings}
    endpoints, admitted = [], []
    for host in selected:
        host_id = host["id"]
        codec = profile.bind(host_id, source)
        check_binding(codec, host_id, source, profile.descriptor.profile_id)
        binding = bindings.get(host_id)
        if host["local"]:
            async def connect_local(codec=codec, host_id=host_id):
                return await Client.connect(await connect_ipc(path), host=host_id, source=source,
                                            profile=profile.descriptor.profile_id, codec=codec.validate_bridge)
            endpoints.append(Endpoint(host_id, True, None, connect_local, codec))
        elif binding is not None:
            check(binding.source == source and binding.profile == profile.descriptor.profile_id,
                  "wss_reader_binding")

            async def connect_remote(binding=binding, codec=codec):
                channel = await connect(binding.url, selection.context)
                return await Client.connect(channel, host=binding.host, source=binding.source,
                                            profile=binding.profile, codec=codec.validate_bridge)
            endpoints.append(Endpoint(host_id, False, binding.token, connect_remote, codec))
            admitted.append(binding)
        else:
            async def connect_ssh(host=host, codec=codec):
                return await connect_catalog_host(catalog, host, domain, source, authority=None,
                                                  profile=profile, codec=codec)
            endpoints.append(Endpoint(host_id, False, catalog.route_token(host_id, host["routes"][0]),
                                      connect_ssh, codec))
    return WSSReader(domain, endpoints, local_host=catalog.local_host, catalog_revision=selection.revision,
                     catalog_check=selection.check, profile=profile, bindings=admitted)
