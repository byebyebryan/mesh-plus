"""Interrupt each study carrier and require its owned runner cleanup."""
import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_carriers import case  # noqa: E402


async def main():
    for carrier in ('wss', 'tcp'):
        task = asyncio.create_task(case(SimpleNamespace(rows=32, steps=100, interval=.1), carrier, 2, 'push'))
        await asyncio.sleep(1)
        task.cancel()
        try:
            await asyncio.wait_for(task, 5)
        except asyncio.CancelledError:
            print(carrier, 'owned cancellation passed')
        else:
            raise AssertionError('cancellation missing')
os.umask(0o077)
asyncio.run(main())
