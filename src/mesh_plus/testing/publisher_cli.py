"""Disposable fixture publisher for owned conformance SSH, never an Observer."""

import argparse
import asyncio

from ..bridge import Bridge
from ..cli import stdio_channel
from .sample import Publisher


async def run(args):
    channel = await stdio_channel()
    try:
        await Bridge(Publisher(args.domain, "remote", "configured_source")).serve(channel)
    finally:
        await channel.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True, choices=("tmux", "agent"))
    asyncio.run(run(parser.parse_args()))
