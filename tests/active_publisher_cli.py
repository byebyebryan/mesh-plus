"""Owned active-profile SSH fixture, never a normal Observer publisher."""

import argparse
import asyncio

from active_fixture import ActiveProfile, ActiveSource

from mesh_plus.api import Bridge, CachedPublisher
from mesh_plus.cli import stdio_channel


async def run(args):
    if args.owner_socket:
        from agent_observer.mesh_publisher import make_publisher

        publisher = make_publisher("fixture", "active", args.owner_socket,
                                   profile_id="agent-observer.mesh-active.v1")
    else:
        source = ActiveSource("remote", empty=args.empty)
        publisher = CachedPublisher("agent", "remote", "active", source, profile=ActiveProfile())
    channel = await stdio_channel()
    try:
        await Bridge(publisher).serve(channel)
    finally:
        await channel.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--empty", action="store_true")
    parser.add_argument("--owner-socket")
    asyncio.run(run(parser.parse_args()))
