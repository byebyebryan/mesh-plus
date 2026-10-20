"""Explicit view-feed configuration using the existing catalog/route policy."""

import re
from pathlib import Path

from ..catalog import SSHPlusAuthority
from ..protocol import check
from ..reader import Endpoint, Reader
from ..remote import connect_catalog_host
from ..state import check_binding, resolve_profile
from ..transport import connect_ipc, connect_ssh
from .delivery import ViewFeedClient, _selector


async def configured_reader(domain, *, source, socket, scope="fleet", hosts=(),
                            local_host=None, authority=None, report_routes=False,
                            profile=None, selector=None, limits=None):
    """Return an ordinary Reader whose endpoints explicitly require view feed.

    No connection or provider collection occurs during construction. Configured
    remote routes run only the fixed view-feed-bridge command and preserve the
    existing reached-marker, authentication and route-reporting policy.
    """
    check(domain in {"tmux", "agent"}, "observer_domain")
    check(isinstance(source, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", source), "configured_source_id")
    check(type(report_routes) is bool, "route_reporting_policy")
    check(scope in {"local", "fleet", "hosts"} and (scope == "hosts") == bool(hosts), "selection_shape")
    check(local_host is None or (scope in {"local", "fleet"} and not hosts), "standalone_scope")
    profile = resolve_profile(domain, profile)
    selector = _selector({} if selector is None else selector)
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

    async def feed_connect(channel, *, host, source, profile, timeout=3, **_kwargs):
        check(profile == state_profile.descriptor.profile_id, "view_feed_profile")
        return await ViewFeedClient.connect(channel, host=host, source=source, profile=state_profile,
                                            selector=selector, limits=limits, timeout=min(timeout, 15))

    async def feed_ssh(destination, source_id, **kwargs):
        return await connect_ssh(destination, source_id, view_feed=True, **kwargs)

    state_profile = profile
    for host in selected:
        codec = profile.bind(host["id"], source)
        check_binding(codec, host["id"], source, profile.descriptor.profile_id)
        if host["local"]:
            async def connect_local(host_id=host["id"]):
                return await ViewFeedClient.connect(await connect_ipc(path), host=host_id, source=source,
                                                    profile=profile, selector=selector, limits=limits)
            endpoints.append(Endpoint(host["id"], True, None, connect_local, codec))
        else:
            async def connect_remote(selected_host=host, codec=codec):
                return await connect_catalog_host(catalog, selected_host, domain, source,
                                                  authority=authority if report_routes else None,
                                                  profile=profile, codec=codec, connector=feed_ssh,
                                                  client_factory=feed_connect)
            endpoints.append(Endpoint(host["id"], False, catalog.route_token(host["id"], host["routes"][0]),
                                      connect_remote, codec))

    async def catalog_check():
        return (await authority.load()).revision

    return Reader(domain, endpoints, local_host=local_host, catalog_revision=catalog.revision if catalog else None,
                  catalog_check=catalog_check if catalog else None, profile=profile)
