"""Fresh-process bounded transport stress; synthetic frames, no native acceptance."""

import asyncio
import json
import os
import resource
import socket
import tempfile
from pathlib import Path

from carrier import Listener, connect
from fixtures import certificates, contexts, fingerprint

from mesh_plus.protocol import MAX_MESSAGE, PROTOCOL, check, encode


def rss_kib():
    fields = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    return int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024


async def main():
    report = {"format": "mesh-plus.wss-study.resources.v1", "scope": "synthetic transport stress, not native/profile state",
              "rssScope": "one worker containing TLS client and server; sampled and process peak, no global bound"}
    with tempfile.TemporaryDirectory(prefix="mesh-wss-resources-") as name:
        root = Path(name)
        await asyncio.to_thread(certificates, root)
        server_context, client_context = contexts(root)
        async def policy():
            return {fingerprint(root): ["beta", "default", "tmux-observer.mesh-candidate.v1"]}
        binding = ["beta", "default", "tmux-observer.mesh-candidate.v1"]
        result = {"protocol": PROTOCOL, "version": 1, "sequence": 1, "kind": "result",
                  "channelId": "00000000-0000-0000-0000-000000000000", "requestId": "stress",
                  "outcome": "ok", "payload": {"text": ""}, "error": None}
        result["payload"]["text"] = "x" * (MAX_MESSAGE - len(encode(result)))
        sent = []
        async def output(channel):
            sent.append(channel)
            for _ in range(4):
                await channel.send(result)
        listener = await Listener(server_context, output, policy, binding).start()
        peak = rss_kib()
        async def sample():
            nonlocal peak
            while True:
                peak = max(peak, rss_kib())
                await asyncio.sleep(.02)
        sampler = asyncio.create_task(sample())
        channel = await connect(listener.url, client_context)
        try:
            await asyncio.wait_for(asyncio.shield(channel.pump), 8)
            check(channel.closed and channel.metrics["peakQueueFrames"] == 2 and
                  channel.metrics["peakAssemblyBytes"] == MAX_MESSAGE, "study_stress_capacity")
            report["slowReader"] = {"messageBytes": MAX_MESSAGE, "peakQueuedFrames": 2,
                                    "peakAssemblyBytes": channel.metrics["peakAssemblyBytes"],
                                    "overloadClosed": True, "sampledPeakRssKiB": peak}
        finally:
            sampler.cancel()
            await asyncio.gather(sampler, return_exceptions=True)
            await channel.close()
            await listener.close()
        admitted = []
        async def input_only(channel):
            admitted.append(channel)
            await channel.pump
        listener = await Listener(server_context, input_only, policy, binding).start()
        channel = await connect(listener.url, client_context)
        try:
            channel.writer.write(b"\x81\xff" + (2 ** 32).to_bytes(8, "big"))
            await channel.writer.drain()
            await asyncio.wait_for(asyncio.shield(channel.pump), 3)
            check(admitted[0].metrics["peakAssemblyBytes"] == 0, "study_oversize_allocation")
            report["oversizedPeer"] = {"declaredBytes": 2 ** 32, "assembledBytes": 0, "closedBeforePayload": True}
        finally:
            await channel.close()
            await listener.close()
        listener = await Listener(server_context, input_only, policy, binding).start()
        sockets = []
        try:
            for _ in range(8):
                sock = socket.socket()
                sock.setblocking(False)
                await asyncio.wait_for(asyncio.get_running_loop().sock_connect(sock, ("127.0.0.1", listener.port)), 1)
                sockets.append(sock)
            await asyncio.sleep(.1)
            check(len(listener.tasks) == 4 and listener.peak_admitted == 4 and listener.dispatched == 0,
                  "study_handshake_admission")
            report["pendingTLS"] = {"offeredTCPConnections": 8, "admitted": 4, "dispatchedSources": 0,
                                    "rssKiB": rss_kib(), "kernelBacklogExcluded": True}
        finally:
            for sock in sockets:
                sock.close()
            await listener.close()
        check(not listener.tasks and not listener.channels and listener.unexpected == 0, "study_resource_cleanup")
        report["processPeakRssKiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["cleanup"] = {"listeners": 0, "channels": 0, "pendingTLS": 0, "unexpectedTasks": 0}
        report["status"] = "passed"
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
