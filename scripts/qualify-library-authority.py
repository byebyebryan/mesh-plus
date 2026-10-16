"""Compare the selected process facade and explicit library using owned files.

No live config/health reads, route reports, picker history or service selection.
Run this same script with an independently installed Mesh wheel for acceptance.
"""

import argparse
import asyncio
import hashlib
import json
import os
import resource
import shutil
import statistics
import tempfile
import threading
import time
from pathlib import Path

import mesh_plus
from mesh_plus import authority as authority_module
from mesh_plus.authority import config_path, route_health_path
from mesh_plus.catalog import SSHPlusAuthority
from mesh_plus.library_authority import LibraryMeshAuthority


def require(value, reason):
    if not value:
        raise AssertionError(reason)


def signature(catalog):
    return {key: value for key, value in catalog.payload.items() if key != "generatedAt"}


def cpu(who):
    value = resource.getrusage(who)
    return value.ru_utime + value.ru_stime


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


async def qualify(args):
    executable = shutil.which(args.executable)
    require(executable, "process facade unavailable")
    selected_backend = os.environ.get("ROFI_SSH_PLUS_MESH_BACKEND", "mesh-plus")
    require(selected_backend == "mesh-plus", "selected facade is not the shared Mesh authority")
    selected_authority = args.selected_root / "mesh_plus/authority.py"
    require(selected_authority.is_file(), "selected Mesh authority bytes unavailable")
    before_environment = dict(os.environ)
    checks = []
    cases = []
    batches = []
    with tempfile.TemporaryDirectory(prefix="mesh-catalog-qualification-") as directory:
        root = Path(directory)
        os.environ.update(XDG_CONFIG_HOME=str(root / "config"), XDG_STATE_HOME=str(root / "state"),
                          PYTHONDONTWRITEBYTECODE="1")
        config = config_path()
        health = route_health_path()
        config.parent.mkdir(parents=True)
        health.parent.mkdir(parents=True)
        history = health.parent / "history.json"
        history.write_text('{"owned_by":"picker","unchanged":true}\n')
        text = ('schema_version = 1\nlocal_id = "fixture"\nlocal_display = "Fixture"\n'
                '[[hosts]]\nid = "remote"\naliases = ["remote-alias"]\n'
                'routes = ["remote-a", "remote-b"]\n')
        config.write_text(text)
        health.write_text('{"version":1,"routes":{}}\n')
        threads = threading.active_count()
        process = SSHPlusAuthority(executable)
        library = LibraryMeshAuthority()
        histories = sha(history)

        async def pair(name, *, failure=False):
            values = []
            for reader in (process, library):
                try:
                    values.append(signature(await reader.load()))
                except Exception as error:
                    if not failure:
                        raise
                    values.append({"error": type(error).__name__, "reason": str(error)[:160]})
                else:
                    require(not failure, name + " unexpectedly succeeded")
            if not failure:
                require(values[0] == values[1], name + " catalog mismatch")
            cases.append({"case": name, "bothRejected": failure, "equal": not failure,
                          **({"failures": values} if failure else {})})
            return values

        try:
            initial = (await pair("configured"))[0]
            checks.append("configured process/library semantic parity (generatedAt excluded)")
            stamp = int(time.time() * 1000)
            health.write_text(json.dumps({"version": 1, "routes": {
                "remote\u0000remote-a": {"lastReachableAt": None, "lastUnreachableAt": stamp}}}))
            changed = (await pair("health_only"))[0]
            require(changed["meshRevision"] == initial["meshRevision"], "health changed config revision")
            require(changed["hosts"][1]["routes"][0]["destination"] == "remote-b", "health ordering absent")
            checks.append("fresh health-only read changes routes, preserves config revision")
            old_stat = config.stat()
            replacement = config.with_suffix(".replacement")
            replacement.write_text(text.replace("remote-alias", "remote-other"))
            require(replacement.stat().st_size == old_stat.st_size, "same-size fixture")
            os.utime(replacement, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            os.replace(replacement, config)
            changed = (await pair("same_metadata_replacement"))[0]
            require(changed["meshRevision"] != initial["meshRevision"], "replacement was hidden")
            checks.append("fresh full load observes same-size/same-mtime atomic config replacement")
            for name, path, invalid in (("invalid_config", config, "unknown = true\n"),
                                        ("invalid_health", health, '{"version":1,"routes":[]}')):
                old = path.read_bytes()
                path.write_text(invalid)
                await pair(name, failure=True)
                path.write_bytes(old)
                await pair(name + "_recovery")
            old = config.read_bytes()
            config.unlink()
            await pair("missing_config_local_only")
            config.write_bytes(old)
            health.unlink()
            await pair("missing_health")
            health.write_text('{"version":1,"routes":{}}\n')
            checks.append("invalid config/health reject independently; recovery/missing-file semantics match")
            awaited_baseline = (await pair("restored"))[0]
            contents = {str(path.relative_to(root)): sha(path) for path in (config, health, history)}
            descriptors = len(list(Path("/proc/self/fd").iterdir()))
            for round_index in range(args.rounds):
                for name in ("process", "library", "library", "process"):
                    reader = process if name == "process" else library
                    await reader.load()  # Warm imports/validators outside timed batch.
                    latencies = []
                    start_self, start_child = cpu(resource.RUSAGE_SELF), cpu(resource.RUSAGE_CHILDREN)
                    started = time.perf_counter()
                    for _ in range(args.iterations):
                        before = time.perf_counter()
                        result = signature(await reader.load())
                        latencies.append(time.perf_counter() - before)
                        require(result == awaited_baseline, "timed semantic mismatch")
                    wall = time.perf_counter() - started
                    parent = cpu(resource.RUSAGE_SELF) - start_self
                    child = cpu(resource.RUSAGE_CHILDREN) - start_child
                    batches.append({"round": round_index, "kind": name, "calls": args.iterations,
                                    "parentCpuSeconds": parent, "reapedChildCpuSeconds": child,
                                    "totalCpuSeconds": parent + child, "wallSeconds": wall,
                                    "meanLatencyMs": statistics.mean(latencies) * 1000,
                                    "maxLatencyMs": max(latencies) * 1000})
            library.close()
            require(threading.active_count() == threads, "catalog thread did not retire")
            require(len(list(Path("/proc/self/fd").iterdir())) == descriptors, "file descriptor leak")
            require(contents == {str(path.relative_to(root)): sha(path) for path in (config, health, history)},
                    "catalog reader changed config/health/history content")
            require(sha(history) == histories, "picker history changed")
            require(health.stat().st_mode & 0o777 == 0o600, "canonical health permissions")
            require(health.parent.stat().st_mode & 0o777 == 0o700, "canonical directory permissions")
            checks.append("zero config/health/history content writes; canonical locks/permissions allowed")
            checks.append("all bounded subprocesses reaped, catalog threads retired, fd count unchanged")
        finally:
            library.close()
            os.environ.clear()
            os.environ.update(before_environment)
    summary = {}
    for name in ("process", "library"):
        values = [batch for batch in batches if batch["kind"] == name]
        total_calls = sum(batch["calls"] for batch in values)
        cost = sum(batch["totalCpuSeconds"] for batch in values) / total_calls
        summary[name] = {"calls": total_calls, "meanCpuMsPerLoad": cost * 1000,
                         "equivalentPercentOneCoreAtFiveSeconds": cost / 5 * 100,
                         "meanBatchLatencyMs": statistics.mean(batch["meanLatencyMs"] for batch in values)}
    summary["cpuReductionPercent"] = 100 * (1 - summary["library"]["meanCpuMsPerLoad"] /
                                          summary["process"]["meanCpuMsPerLoad"])
    return {"status": "passed", "scope": "owned disposable catalog inputs; serial ABBA without profiler",
            "checks": checks, "cases": cases, "summary": summary, "batches": batches,
            "inputs": {"meshPackage": str(Path(mesh_plus.__file__).resolve()),
                       "processExecutable": executable, "processExecutableSha256": sha(executable),
                       "selectedBackend": selected_backend, "selectedAuthority": str(selected_authority),
                       "selectedAuthoritySha256": sha(selected_authority),
                       "candidateAuthoritySha256": sha(authority_module.__file__)},
            "memory": {"combinedWorkerPeakRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       "largestReapedChildPeakRssKiB": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss},
            "limits": ["Not a live catalog/service selection or absolute five-second failure bound",
                       "No route-report writer exercised; health read has canonical lock/permission effects",
                       "Library explicitly limits each config/health source to 4MiB and regular files",
                       "Memory high-water marks are cumulative, not independent per-mode RSS comparisons"]}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="rofi-ssh-plus")
    parser.add_argument("--selected-root", type=Path, default=Path.home() / ".local/share/mesh-plus/python")
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    require(1 <= args.iterations <= 100 and 1 <= args.rounds <= 10, "bounded measurement arguments")
    report = await qualify(args)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "summary", "limits")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
