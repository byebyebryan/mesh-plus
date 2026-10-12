"""Fresh-process cached watch acquisition timings, descriptive only."""

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coordinator import MESH, ROOT, on_host, retire, spawn  # noqa: E402
from host import private_write  # noqa: E402


async def run(args):
    cases = []
    for host in ("snap", "starship"):
        peer = "starship" if host == "snap" else "snap"
        for domain in ("tmux", "agent"):
            for index in range(20):
                # Alternate carrier order so cache/environment drift is visible.
                for carrier in (("ssh", "wss") if index % 2 == 0 else ("wss", "ssh")):
                    worker = await spawn(on_host(host, ["reader", "--host", host, "--peer", peer, "--domain", domain,
                        "--carrier", carrier, "--case", secrets.token_hex(16), "--material", str(ROOT / "material" / host), "--mesh-root", MESH]))
                    try:
                        async with asyncio.timeout(30):
                            ready = json.loads(await worker.stdout.readline())
                            worker.stdin.write(b"stop\n")
                            await worker.stdin.drain()
                            result = json.loads(await worker.stdout.readline())["result"]
                            await worker.wait()
                        if worker.returncode or result["failures"] or result["metrics"]["cleanupFailures"]:
                            raise ValueError("cold_cleanup_or_delivery")
                        cases.append({"host": host, "peer": peer, "domain": domain, "carrier": carrier,
                                      "index": index, "coldMs": ready["coldMs"], "inventories": result["inventories"]})
                    finally:
                        await retire(worker)
                print(json.dumps({"host": host, "domain": domain, "acquisitionsPerCarrier": index + 1}), flush=True)
    private_write(args.output, {"status": "passed", "cases": cases,
        "scope": "twenty fresh-process healthy cached watch/proof acquisitions per host/domain/carrier; timing starts after profile/selection construction; excludes interpreter/import/credential setup; no collection and no tail significance claim"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
