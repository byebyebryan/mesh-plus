"""Capture one cached native frame into an explicitly private replay input."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

from mesh_plus.library_authority import LibraryMeshAuthority
from mesh_plus.observer import ObserverAdapter


async def capture(args):
    authority = LibraryMeshAuthority()
    try:
        catalog = await authority.load()
        adapter = ObserverAdapter(args.domain, catalog.local_host, args.source, args.socket)
        payload = await adapter.snapshot({})
        raw = json.dumps(payload["ownerFrame"], separators=(",", ":")).encode() + b"\n"
        # Refuse overwrite, symlink traversal at the leaf, or a public parent.
        if args.output.parent.stat().st_mode & 0o077:
            raise ValueError("private_input_directory_required")
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
        print(json.dumps({"domain": args.domain, "bytes": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest(),
                          "rows": len(payload["ownerFrame"]["snapshot"]["sessions"])}))
    finally:
        authority.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=("tmux", "agent"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--socket", type=Path, required=True, help="native cached service socket")
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(capture(parser.parse_args()))
