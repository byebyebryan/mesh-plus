"""Bounded owned DNS setup, without asyncio's lingering resolver threads."""

import asyncio
import contextlib
import ipaddress
import json
import ssl
import sys

from mesh_plus.protocol import check
from mesh_plus.transport import boottime_ms, finish_owned, within_deadline

PROGRAM = """
import json, socket, sys
addresses = []
for family, kind, protocol, canonical, address in socket.getaddrinfo(
        sys.argv[1], None, type=socket.SOCK_STREAM):
    if family in (socket.AF_INET, socket.AF_INET6) and address[0] not in addresses:
        addresses.append(address[0])
print(json.dumps(addresses[:16]))
"""


async def stop(process):
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            await within_deadline(process.wait(), boottime_ms() + 1000)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await within_deadline(process.wait(), boottime_ms() + 1000)


async def addresses(hostname):
    try:
        value = ipaddress.ip_address(hostname)
        check(getattr(value, "scope_id", None) is None, "wss_address_scope")
        return [str(value)]
    except ValueError:
        pass
    deadline = boottime_ms() + 3000
    creation = asyncio.create_task(asyncio.create_subprocess_exec(
        sys.executable, "-I", "-S", "-c", PROGRAM, hostname,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL))
    process = None
    try:
        process = await finish_owned(creation)
        raw, _ = await within_deadline(process.communicate(), deadline)
        check(process.returncode == 0 and len(raw) <= 4096, "wss_resolution_failed")
        values = json.loads(raw)
        check(type(values) is list and 1 <= len(values) <= 16 and
              all(isinstance(value, str) for value in values), "wss_resolution_failed")
        return [str(ipaddress.ip_address(value)) for value in values]
    finally:
        if process is None and creation.done() and not creation.cancelled() and creation.exception() is None:
            process = creation.result()
        if process is not None:
            await finish_owned(asyncio.create_task(stop(process)))


async def open_stream(hostname, port, context, *, server_hostname):
    # Literal addresses avoid getaddrinfo in the event-loop executor. The
    # original configured hostname still owns TLS certificate verification.
    selected = await addresses(hostname)
    deadline = boottime_ms() + 3000
    last = None
    for address in selected:
        try:
            return await within_deadline(asyncio.open_connection(
                address, port, ssl=context, server_hostname=server_hostname,
                ssl_handshake_timeout=3, ssl_shutdown_timeout=1, limit=65536), deadline)
        except OSError as error:
            last = error
            # Certificate/authentication errors must not try another address.
            if isinstance(error, ssl.SSLError):
                raise
    if last is not None:
        raise last
    raise OSError("wss_resolution_failed")
