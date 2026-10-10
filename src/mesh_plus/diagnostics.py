"""Explicit diagnostics outside the frozen producer and Read contracts."""

import asyncio
import importlib.metadata
import time

from .transport import boottime_ms, within_deadline

FORMAT = "mesh-plus.diagnostics.v1"


def failure_code(error):
    # Exception messages and arbitrary adapter codes may contain private data.
    if isinstance(error, TimeoutError):
        return "deadline"
    if isinstance(error, (FileNotFoundError, ConnectionError, EOFError)):
        return "unavailable"
    if isinstance(error, ModuleNotFoundError):
        return "missing_dependency"
    code = getattr(error, "code", None)
    if isinstance(code, str) and code in {"scope_mismatch", "unsupported_contract", "unsupported_capability",
                                        "source_unavailable", "publisher_restart", "gap", "deadline",
                                        "ipc_directory_policy", "ipc_socket_policy", "source_config_policy"}:
        return code
    return "rejected"


def doctor():
    versions = {}
    for name in ("mesh-plus", "jsonschema", "tmux-observer", "agent-observer"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"format": FORMAT, "operation": "doctor", "ok": versions["jsonschema"] is not None,
            "versions": versions, "checks": {"observerPackagesOptional": True},
            "limits": ["Package availability only; no endpoint or deployment acceptance"]}


async def probe(connect, *, mode="snapshot", timeout_ms=5000):
    if mode not in {"snapshot", "subscribe"} or type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000:
        raise ValueError("probe_budget")
    client = None
    subscription = None
    started = time.perf_counter()
    async def exercise():
        nonlocal client, subscription
        client = await connect()
        if mode == "snapshot":
            await client.request(timeout_ms=timeout_ms)
        else:
            subscription = await client.subscribe()
            # Heartbeats are not evidence of a delivered baseline.
            while (await anext(subscription))["kind"] != "data":
                pass
        return client.inspect()
    report = {"format": FORMAT, "operation": "probe", "mode": mode, "ok": False}
    try:
        report["runtime"] = await within_deadline(exercise(), boottime_ms() + timeout_ms)
        report["ok"] = True
    except asyncio.CancelledError:
        raise
    except Exception as error:
        report["error"] = failure_code(error)
    finally:
        # Closing the channel owns all handles, including an unfinished admission.
        if client:
            await client.close()
        report["elapsedMs"] = round((time.perf_counter() - started) * 1000, 3)
    return report
