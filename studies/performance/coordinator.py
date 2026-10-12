"""Balanced installed-owner SSH/WSS windows with separate two-host process accounting."""

import argparse
import asyncio
import json
import os
import secrets
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host import private_write  # noqa: E402

ROOT = Path("/tmp/mesh-perf-20261012")
PYTHON = str(ROOT / "baseline/bin/python")
MESH = str(ROOT / "baseline/lib/python3.14/site-packages")


async def spawn(argv):
    return await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE, limit=1048576)


def on_host(host, arguments, script="measure.py"):
    argv = [PYTHON, "-I", "-B", str(ROOT / script), *arguments]
    if host == "snap":
        return argv
    import shlex
    return ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ControlMaster=no",
            "-o", "ControlPath=none", "starship", shlex.join(argv)]


async def rpc(process, value):
    process.stdin.write((json.dumps(value) + "\n").encode())
    await process.stdin.drain()
    async with asyncio.timeout(5):
        raw = await process.stdout.readline()
    if not raw:
        raise ValueError("sampler_disconnected")
    return json.loads(raw)


async def retire(process):
    if process.returncode is not None:
        return
    process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), 5)
    except TimeoutError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 2)
        except TimeoutError:
            process.kill()
            await process.wait()


def resources(samples):
    groups, missing = {}, []
    for sample in samples:
        for item in sample["roles"]:
            if "error" in item:
                missing.append(item)
                continue
            identity = item["role"], item["pid"], item["birth"]
            groups.setdefault(identity, []).append((sample["time"], item))
    report = []
    for (role, pid, birth), points in groups.items():
        first, last = points[0], points[-1]
        seconds = last[0] - first[0]
        if seconds <= 0:
            missing.append({"role": role, "pid": pid, "error": "insufficient_lifetime"})
            continue
        pss = [point[1]["pssKiB"] for point in points if point[1].get("pssKiB") is not None]
        fds = [point[1]["fds"] for point in points if point[1].get("fds") is not None]
        report.append({"role": role, "pid": pid, "birth": birth, "seconds": seconds,
                       "cpuPercent": 100 * (last[1]["ticks"] - first[1]["ticks"]) / os.sysconf("SC_CLK_TCK") / seconds,
                       "pssMeanKiB": statistics.mean(pss) if pss else None,
                       "rssPeakKiB": max(point[1]["rssKiB"] for point in points),
                       "fdPeak": max(fds) if fds else None, "samples": len(points)})
    sampler = [(sample["time"], sample["sampler"]["ticks"]) for sample in samples]
    overhead = 100 * (sampler[-1][1] - sampler[0][1]) / os.sysconf("SC_CLK_TCK") / (sampler[-1][0] - sampler[0][0])
    system = 100 * (samples[-1]["systemBusyTicks"] - samples[0]["systemBusyTicks"]) / os.sysconf("SC_CLK_TCK") / (sampler[-1][0] - sampler[0][0])
    return {"roles": report, "samplerCpuPercent": overhead, "systemCpuPercent": system,
            "unattributedCpuPercent": max(0, system - overhead - sum(role["cpuPercent"] for role in report)), "errors": missing}


async def window(args, host, domain, carrier, block, position):
    peer = "starship" if host == "snap" else "snap"
    case = secrets.token_hex(16)
    worker, samplers, listener = None, [], None
    result = {"case": case, "host": host, "peer": peer, "domain": domain, "carrier": carrier,
              "block": block, "position": position, "warmupSeconds": args.warmup, "measurementSeconds": args.seconds}
    try:
        if carrier == "wss":
            listener = await spawn(on_host(peer, ["serve", "--host", peer, "--domain", domain,
                "--material", str(ROOT / "material" / peer), "--address", "100.84.31.64" if peer == "starship" else "100.70.82.105",
                "--port", "9443" if domain == "tmux" else "9444", "--output", str(ROOT / "cases" / case / "wss.json"), "--mesh-root", MESH], "host.py"))
            async with asyncio.timeout(15):
                result["listener"] = json.loads(await listener.stdout.readline())
        worker = await spawn(on_host(host, ["reader", "--host", host, "--peer", peer, "--domain", domain,
                                          "--carrier", carrier, "--case", case, "--material", str(ROOT / "material" / host), "--mesh-root", MESH]))
        async with asyncio.timeout(30):
            ready = json.loads(await worker.stdout.readline())
        result["coldMs"] = ready["coldMs"]
        local = await spawn(on_host(host, ["sample"]))
        remote = await spawn(on_host(peer, ["sample"]))
        samplers = [local, remote]
        result["controlsBefore"] = await asyncio.gather(rpc(local, {"controls": True, "host": host, "peer": peer}),
                                                       rpc(remote, {"controls": True, "host": peer, "peer": host}))
        discovered = await rpc(remote, {"discover": case, "host": peer, "domain": domain, "carrier": carrier})
        local_roles = [{"role": "reader-consumer", "pid": ready["ready"]["pid"], "birth": ready["ready"]["birth"]}]
        await asyncio.sleep(args.warmup)
        worker.stdin.write(b"mark\n")
        await worker.stdin.drain()
        async with asyncio.timeout(5):
            result["readerBefore"] = json.loads(await worker.stdout.readline())
        samples = {"readerHost": [], "publisherHost": []}
        started = time.monotonic()
        target = started
        while target <= started + args.seconds:
            await asyncio.sleep(max(0, target - time.monotonic()))
            pair = await asyncio.gather(rpc(local, {"roles": local_roles, "tree": True}),
                                        rpc(remote, {"roles": discovered["discovered"]}))
            samples["readerHost"].append(pair[0])
            samples["publisherHost"].append(pair[1])
            target += .5
        result["resources"] = {key: resources(value) for key, value in samples.items()}
        result["samples"] = samples
        worker.stdin.write(b"mark\n")
        await worker.stdin.drain()
        async with asyncio.timeout(5):
            result["readerAfter"] = json.loads(await worker.stdout.readline())
        result["controlsAfter"] = await asyncio.gather(rpc(local, {"controls": True, "host": host, "peer": peer}),
                                                      rpc(remote, {"controls": True, "host": peer, "peer": host}))
        worker.stdin.write(b"stop\n")
        await worker.stdin.drain()
        async with asyncio.timeout(15):
            receipt = json.loads(await worker.stdout.readline())
            await worker.wait()
        if worker.returncode:
            raise ValueError("worker_failed")
        result["reader"] = receipt["result"]
        total = sum(role["cpuPercent"] for endpoint in result["resources"].values() for role in endpoint["roles"]
                    if role["role"] in {"reader-consumer", "ssh-client", "publisher", "ssh-server-session"})
        result["attributableCpuPercent"] = total
        issues = result["reader"]["failures"] + [error["error"] for endpoint in result["resources"].values() for error in endpoint["errors"]]
        # Exact identity stability is required for candidate/carrier decision; evolving inventory is descriptive.
        if len(result["reader"]["inventories"]) != 1:
            issues.append("inventory_changed")
        if result["controlsBefore"] != result["controlsAfter"]:
            issues.append("controls_incarnation_or_path_changed")
        result["status"] = "accepted_window" if not issues else "excluded_window"
        result["exclusions"] = issues
    except Exception as error:
        result["status"] = "failed_window"
        result["error"] = type(error).__name__
    finally:
        if worker:
            await retire(worker)
        for sampler in samplers:
            await retire(sampler)
        if listener is not None:
            stopper = await spawn(on_host(peer, ["stop-listener", "--case", case]))
            async with asyncio.timeout(10):
                await stopper.communicate()
            if stopper.returncode:
                raise ValueError("listener_stop_ownership_failed")
            await asyncio.wait_for(listener.wait(), 10)
            result["listenerRetired"] = listener.returncode == 0
            if not result["listenerRetired"]:
                result["status"] = "failed_window"
                result["error"] = "listener_retirement_failed"
    private_write(args.output / (case + ".json"), result)
    print(json.dumps({key: result.get(key) for key in ("case", "host", "domain", "carrier", "block", "position", "status", "exclusions", "error", "attributableCpuPercent")}), flush=True)
    return result


async def run(args):
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    cases = []
    for host in args.hosts:
        for domain in args.domains:
            for block in range(args.blocks):
                for position, carrier in enumerate(("ssh", "wss", "wss", "ssh")):
                    cases.append(await window(args, host, domain, carrier, block, position))
    private_write(args.output / "index.json", {"cases": [{key: case.get(key) for key in ("case", "host", "domain", "carrier", "block", "position", "status", "exclusions", "error", "attributableCpuPercent")} for case in cases],
                  "scope": "remote owner cached endpoint watch, unchanged proof cadence; ordinary native CPU separate; sampler CPU separate; root sshd PSS may be inaccessible"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hosts", nargs="+", choices=("snap", "starship"), default=["snap", "starship"])
    parser.add_argument("--domains", nargs="+", choices=("tmux", "agent"), default=["tmux", "agent"])
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--warmup", type=float, default=15)
    parser.add_argument("--seconds", type=float, default=120)
    args = parser.parse_args()
    if not args.output.is_absolute() or not 1 <= args.blocks <= 4 or not 1 <= args.seconds <= 600 or not 0 <= args.warmup <= 30:
        parser.error("bounded timing and absolute private output required")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
