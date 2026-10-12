"""Isolated real-tailnet owner admission and channel-retirement probes; metadata only."""

import argparse
import asyncio
import json
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host import installed, private_write, profile  # noqa: E402


async def run(args):
    from mesh_plus.api import Client
    from mesh_plus.wss import Selection
    from mesh_plus.wss.carrier import connect
    from mesh_plus.wss.configuration import tls_context

    directory = args.material
    selection = Selection.load(directory / "catalog.json", directory / (args.domain + "-registry.json"),
                               directory / "ca.pem", directory / (args.domain + "-client.pem"), directory / (args.domain + "-client.key"))
    binding = next(binding for binding in selection.bindings if binding.host == args.peer)
    codec = profile(args.domain).bind(binding.host, binding.source)
    clients = []
    checks = []

    async def acquire(context):
        channel = await connect(binding.url, context)
        try:
            return await Client.connect(channel, host=binding.host, source=binding.source, profile=binding.profile,
                                        codec=codec.validate_bridge, timeout=3)
        except BaseException:
            await channel.close()
            raise

    async def rejects(context):
        admitted = None
        try:
            admitted = await acquire(context)
        except Exception:
            return
        finally:
            if admitted:
                await admitted.close()
        raise ValueError("unexpected_admission")

    try:
        # Full Mesh handshakes occupy the listener's four slots; fifth must reject.
        for _ in range(4):
            clients.append(await acquire(selection.context))
        await rejects(selection.context)
        for client in clients:
            proof = await client.request("proof", {"nonce": "f" * 32})
            if proof["nonce"] != "f" * 32:
                raise ValueError("healthy_capacity_proof")
        checks.append("four_active_owner_channels_fifth_rejects_healthy_channels_prove")
        for client in clients:
            await client.close()
        clients.clear()
        await asyncio.sleep(.3)
        context = ssl.create_default_context(cafile=str(directory / "ca.pem"))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        await rejects(context)
        checks.append("missing_client_certificate_rejected")
        other = "agent" if args.domain == "tmux" else "tmux"
        wrong = tls_context(directory / "ca.pem", directory / (other + "-client.pem"), directory / (other + "-client.key"))
        await rejects(wrong)
        checks.append("trusted_other_domain_client_certificate_not_authorized")
        # Repeated owned reconnects exercise both poll and push with original source proofs.
        for _ in range(12):
            client = await acquire(selection.context)
            clients.append(client)
            sub = None
            try:
                await client.request("proof", {"nonce": "e" * 32})
                sub = await client.subscribe()
                async with asyncio.timeout(5):
                    await anext(sub)
            finally:
                if sub:
                    await sub.close()
                await client.close()
                clients.remove(client)
        checks.append("twelve_poll_push_reconnects_retired")
    finally:
        for client in clients:
            await client.close()
        selection.close()
    report = {"status": "passed", "host": args.host, "peer": args.peer, "domain": args.domain, "checks": checks,
              "scope": "actual installed owner factories over tailnet WSS; cached semantics, not independent provider oracle",
              "excluded": ["physical suspend", "maximum domain frame", "credential provisioning rotation", "ordinary deployment"]}
    private_write(args.output, report)
    print(json.dumps(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("snap", "starship"), required=True)
    parser.add_argument("--peer", choices=("snap", "starship"), required=True)
    parser.add_argument("--domain", choices=("tmux", "agent"), required=True)
    parser.add_argument("--material", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mesh-root", type=Path)
    args = parser.parse_args()
    installed(args)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
