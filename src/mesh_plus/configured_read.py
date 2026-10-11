"""Configured state-reader binding shared by read clients, without collection.

The caller supplies an authenticated catalog authority or an explicit local
host. Route reporting is an explicit transport policy, disabled for read-only
consumers. No connection is opened until the returned Reader executes a read.
"""

import re
from pathlib import Path

from .catalog import SSHPlusAuthority
from .client import Client
from .protocol import check
from .reader import Endpoint, Reader
from .remote import connect_catalog_host
from .state import check_binding, resolve_profile
from .transport import connect_ipc


async def configured_reader(domain, *, source, socket, scope="fleet", hosts=(),
                            local_host=None, authority=None, report_routes=False, profile=None):
    """Resolve one immutable local/fleet scope; return its owned state Reader."""
    check(domain in {"tmux", "agent"}, "observer_domain")
    check(isinstance(source, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", source), "configured_source_id")
    check(type(report_routes) is bool, "route_reporting_policy")
    check(scope in {"local", "fleet", "hosts"} and (scope == "hosts") == bool(hosts), "selection_shape")
    check(local_host is None or (scope in {"local", "fleet"} and not hosts), "standalone_scope")
    profile = resolve_profile(domain, profile)
    authority = SSHPlusAuthority() if authority is None else authority
    if local_host is not None:
        check(isinstance(local_host, str) and len(local_host) <= 16384 and
              re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", local_host), "configured_host_id")
    catalog = None if local_host is not None else await authority.load()
    local_host = local_host if local_host is not None else catalog.local_host
    selected = [{"id": local_host, "local": True}] if catalog is None else catalog.select(scope, hosts)
    path = Path(socket)
    check(path.is_absolute(), "configured_socket_path")
    endpoints = []
    for host in selected:
        codec = profile.bind(host["id"], source)
        check_binding(codec, host["id"], source, profile.descriptor.profile_id)
        if host["local"]:
            async def connect_local(host_id=host["id"], codec=codec):
                return await Client.connect(await connect_ipc(path), host=host_id, source=source,
                                            profile=profile.descriptor.profile_id, codec=codec.validate_bridge)
            endpoints.append(Endpoint(host["id"], True, None, connect_local, codec))
        else:
            async def connect_remote(selected_host=host, codec=codec):
                return await connect_catalog_host(catalog, selected_host, domain, source,
                                                  authority=authority if report_routes else None, profile=profile, codec=codec)
            endpoints.append(Endpoint(host["id"], False,
                                      catalog.route_token(host["id"], host["routes"][0]), connect_remote, codec))

    async def catalog_check():
        return (await authority.load()).revision

    return Reader(domain, endpoints, local_host=local_host, catalog_revision=catalog.revision if catalog else None,
                  catalog_check=catalog_check if catalog else None, profile=profile)
