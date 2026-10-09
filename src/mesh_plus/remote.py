"""Configured SSH route attempts with authenticated reached-marker semantics."""

import asyncio
import time

from .client import Client
from .observer import ObserverCodec
from .protocol import check
from .transport import connect_ssh

TRANSPORT_FAILURES = ("could not resolve hostname", "name or service not known", "temporary failure in name resolution",
                      "connection refused", "connection timed out", "operation timed out", "no route to host",
                      "network is unreachable", "connection reset by peer", "kex_exchange_identification")


class SetupError(Exception):
    def __init__(self, code, route_token):
        self.code, self.route_token = code, route_token
        super().__init__(code)


async def connect_catalog_host(catalog, host, domain, source, *, authority=None, connector=connect_ssh):
    check(not host["local"] and bool(host["routes"]), "remote_host")
    codec = ObserverCodec(domain, host["id"], source)
    policy = catalog.payload["sshPolicy"]
    timeout = min(60, policy["connectTimeoutSeconds"] * policy["connectionAttempts"] + 3)
    last = None
    for route in host["routes"]:
        token = catalog.route_token(host["id"], route)
        channel = None
        try:
            channel = await connector(route["destination"], source, executable=policy["executable"],
                                      timeout_seconds=policy["connectTimeoutSeconds"], attempts=policy["connectionAttempts"])
            client = await Client.connect(channel, host=host["id"], source=source,
                                          profile=domain + "-observer.mesh-candidate.v1", codec=codec.validate,
                                          required=("snapshot", "proof", "subscribe"), timeout=timeout)
            client.route_token = token
            if authority and channel.reached:
                try:
                    await authority.report_route(host=host["id"], route=route["destination"], status="reachable",
                                                 revision=catalog.revision, observed_at=int(time.time() * 1000))
                except Exception:
                    # Health persistence failure cannot invalidate a checked domain channel.
                    pass
            return client
        except asyncio.CancelledError:
            if channel:
                await channel.close()
            raise
        except Exception as error:
            if channel:
                await channel.close()
            reached = bool(channel and channel.reached)
            diagnostics = bytes(channel.stderr_tail).decode(errors="replace").casefold() if channel else ""
            transport = not reached and (isinstance(error, TimeoutError) or
                                        any(marker in diagnostics for marker in TRANSPORT_FAILURES))
            code = "source_unavailable" if reached else "transport_failure" if transport else "setup_policy_failure"
            last = SetupError(code, token)
            if authority and (reached or transport):
                try:
                    await authority.report_route(host=host["id"], route=route["destination"],
                                                 status="reachable" if reached else "unreachable",
                                                 revision=catalog.revision, observed_at=int(time.time() * 1000))
                except Exception:
                    pass
            if not transport:
                raise last from error
    raise last
