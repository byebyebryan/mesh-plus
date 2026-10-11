"""Explicit diagnostics outside the frozen producer and Read contracts."""

import asyncio
import importlib.metadata
import secrets
import time
from dataclasses import asdict

from .transport import boottime_ms, within_deadline

FORMAT = "mesh-plus.diagnostics.v1"
SDK_FORMAT = "mesh-plus.diagnostics.v2"


def sdk_failure_code(error):
    code = getattr(error, "code", None)
    if isinstance(code, str) and code in {"profile_descriptor", "profile_interface", "endpoint_codec_binding", "endpoint_codec_required",
                "endpoint_client_binding", "hello_binding", "authenticated_host_binding", "owner_digest",
                "proof_nonce", "proof_receipts", "native_roundtrip", "native_capacity", "local_clock_scope",
                "read_resync_required", "read_terminal_barrier", "scope_changed", "catalog_unavailable",
                "channel_rotation_required", "unsupported_operation", "unsupported_subscription"}:
        return code
    return failure_code(error)


def doctor_sdk():
    """Explicit v2 package/interface facts; never infer native compatibility."""
    from .api import SDK_INTERFACE_VERSION, descriptor
    return {**doctor(), "format": SDK_FORMAT, "sdkVersion": SDK_INTERFACE_VERSION,
            "profiles": [asdict(descriptor(domain)) for domain in ("tmux", "agent")],
            "limits": ["Package/interface facts only; no native compatibility or endpoint acceptance"]}


def _summary(response, now, rows, profile):
    from .api import reconstructed
    from .protocol import ProtocolError
    from .state import inspect_state
    from .view import remote_expiry
    hosts = []
    for index, host in enumerate(response["mesh"]["hosts"]):
        receipts = host["receipts"]
        current = sum(r["health"] in {"current", "partial"} and r["expiresAtMs"] > now for r in receipts)
        expired = sum(r["health"] in {"current", "partial"} and r["expiresAtMs"] <= now for r in receipts)
        if host["owner"] is not None:
            state = inspect_state(profile, profile.bind(host["hostId"], "default"), reconstructed(response, host, profile=profile))
            original_expired = 0
            for receipt in state.receipts:
                if receipt["health"] not in {"current", "partial"}:
                    continue
                expiry = receipt["expiry"]
                if host["local"]:
                    original_expired += expiry <= now
                elif host["delivery"]["proof"] is not None:
                    proof = host["delivery"]["proof"]
                    original_expired += remote_expiry(proof["sentAtMs"], proof["receivedAtMs"],
                                                     max(0, expiry - proof["bridgeEncodedAtMs"]), proof["marginMs"]) <= now
            expired = max(expired, original_expired)
        evidence = "current" if current else "expired" if expired else "nonpositive" if receipts else "absent"
        hosts.append({"index": index, "delivery": host["delivery"]["status"], "evidence": evidence,
                      "receipts": len(receipts), "currentReceipts": current, "expiredReceipts": expired,
                      "error": sdk_failure_code(ProtocolError(host["delivery"]["error"]["code"]))
                      if host["delivery"]["error"] else None})
    return {"deliveryStatus": response["mesh"]["status"], "hosts": hosts,
            "rawRecords": len(response["sessions"]), "currentRecordsAtSample": len(rows),
            "sampleBoottimeMs": now, "retainedAuthority": False}


async def assess(reader, *, mode="snapshot", timeout_ms=5000):
    """Own one bounded Reader acquisition and summarize evidence at that instant."""
    from .api import ReadGuard, current_sessions, validate_response
    from .evidence import clock_domain
    from .transport import finish_owned
    if mode not in {"snapshot", "subscribe"} or type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000:
        raise ValueError("assessment_budget")
    report = {"format": SDK_FORMAT, "operation": "assess", "mode": mode, "ok": False, "acquired": False,
              "limits": ["One cached evidence sample; cleanup revokes watch authority",
                         "Acquisition deadline excludes bounded owned cleanup grace"]}
    guard, stream = None, None
    started = time.perf_counter()
    async def exercise():
        nonlocal guard, stream
        if mode == "snapshot":
            response = await reader.snapshot(timeout_ms=timeout_ms)
            validate_response(response, profile=reader.profile)
        else:
            request_id = secrets.token_hex(16)
            guard = ReadGuard(reader.domain, request_id, host_ids=[e.host for e in reader.endpoints], profile=reader.profile)
            stream = reader.watch(request_id=request_id)
            async for response in stream:
                guard.accept(response)
                if "mesh" not in response:
                    from .protocol import ProtocolError
                    raise ProtocolError(response["error"]["code"])
                if response["mesh"]["kind"] in {"gap", "heartbeat"}:
                    continue
                states = [h["delivery"]["status"] for h in response["mesh"]["hosts"]]
                if "ready" in states or "connecting" not in states:
                    break
            else:
                raise EOFError()
        now = boottime_ms()
        rows = guard.current(now, clock_domain()) if guard else current_sessions(response, now, clock_domain(), profile=reader.profile)
        report["sample"] = _summary(response, now, rows, reader.profile)
        report["acquired"] = any(h["delivery"] == "ready" for h in report["sample"]["hosts"])
        report["ok"] = report["acquired"]
    operation = asyncio.create_task(exercise())
    async def cleanup():
        if not operation.done():
            operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        if guard:
            guard.disconnect()
        if stream:
            try:
                await stream.aclose()
            except Exception:
                report.update(ok=False, error="cleanup_incomplete")
        report["runtime"] = reader.inspect()
        report["elapsedMs"] = round((time.perf_counter() - started) * 1000, 3)
        if report["runtime"]["activeConnections"] or report["runtime"]["cleanupFailures"]:
            report.update(ok=False, error="cleanup_incomplete")
    try:
        await within_deadline(operation, boottime_ms() + timeout_ms)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        report.update(ok=False, acquired=False, error=sdk_failure_code(error))
        report.pop("sample", None)
    finally:
        await finish_owned(asyncio.create_task(cleanup()))
    return report


async def assess_configured(domain, *, mode="snapshot", timeout_ms=5000, **binding):
    """Include catalog resolution in the budget; never report route health."""
    from .configured_read import configured_reader
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000 or mode not in {"snapshot", "subscribe"}:
        raise ValueError("assessment_budget")
    if binding.get("report_routes", False):
        raise ValueError("assessment_route_reporting")
    binding["report_routes"] = False
    started = time.perf_counter()
    deadline = boottime_ms() + timeout_ms
    try:
        reader = await within_deadline(configured_reader(domain, **binding), deadline)
        remaining = deadline - boottime_ms()
        if remaining <= 0:
            raise TimeoutError()
        report = await assess(reader, mode=mode, timeout_ms=remaining)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        report = {"format": SDK_FORMAT, "operation": "assess", "mode": mode, "ok": False,
                  "acquired": False, "error": sdk_failure_code(error)}
    report["elapsedMs"] = round((time.perf_counter() - started) * 1000, 3)
    return report


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
