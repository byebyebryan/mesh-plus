"""Diagnostic acquisition and evidence qualification remain distinct."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mesh_plus.api import Bridge, Client, Endpoint, Reader
from mesh_plus.diagnostics import (
    assess,
    assess_configured,
    doctor,
    doctor_sdk,
    failure_code,
    sdk_failure_code,
)
from mesh_plus.protocol import ProtocolError
from mesh_plus.testing import profile_cases
from mesh_plus.testing.sample import Profile, Publisher
from mesh_plus.transport import IPCServer, boottime_ms, connect_ipc


class AssessmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_empty_and_warming_do_not_use_row_count_as_evidence(self):
        for kind, evidence in (("local", "current"), ("empty", "current"), ("warming", "nonpositive")):
            publisher = Publisher("agent", "local")
            if kind == "empty":
                publisher.frame["snapshot"]["sessions"] = []
            elif kind == "warming":
                # Reuse the reviewed warming native frame through the owner profile.
                case = next(c for c in profile_cases("agent") if c.case_id == "agent-warming")
                publisher.frame = next(iter(case.native.values()))
                publisher.host = publisher.frame["hostScope"]
                publisher.codec = publisher.state_profile.bind(publisher.host, publisher.source)
                from mesh_plus.evidence import clock_domain
                clock = clock_domain()
                publisher.frame["bootId"] = clock["bootId"]
                publisher.frame["clockDomain"] = "time:[" + clock["timeNamespace"].split(":")[1] + "]"
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "mesh.sock"
                server = await IPCServer(path, Bridge(publisher).serve).start()
                try:
                    for mode in ("snapshot", "subscribe"):
                        report = await assess_configured("agent", source="default", socket=path,
                                                         local_host=publisher.host, profile=publisher.state_profile, mode=mode)
                        self.assertTrue(report["ok"], report)
                        self.assertEqual(report["sample"]["hosts"][0]["evidence"], evidence)
                        self.assertFalse(report["sample"]["retainedAuthority"])
                        if kind != "local":
                            self.assertEqual(report["sample"]["currentRecordsAtSample"], 0)
                        text = json.dumps(report)
                        self.assertNotIn("nativeId", text)
                        self.assertNotIn(str(path), text)
                finally:
                    await server.close()
                self.assertEqual(publisher.watchers, 0)

    async def test_partial_delivery_and_expired_evidence_are_independent(self):
        publisher = Publisher("tmux", "local")
        publisher.frame["receipt"]["expiresAt"] = boottime_ms() - 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            async def local():
                return await Client.connect(await connect_ipc(path), host="local", source="default",
                                            profile=publisher.profile, codec=publisher.validate)
            async def failed():
                raise ConnectionError("private route")
            reader = Reader("tmux", [Endpoint("local", True, None, local, publisher.codec),
                                     Endpoint("remote", False, "sha256:" + "a" * 64, failed,
                                              publisher.state_profile.bind("remote", "default"))],
                            local_host="local", catalog_revision="sha256:" + "b" * 64, profile=publisher.state_profile)
            try:
                report = await assess(reader)
                self.assertTrue(report["acquired"], report)
                self.assertEqual(report["sample"]["deliveryStatus"], "partial")
                self.assertEqual(report["sample"]["currentRecordsAtSample"], 0)
                # Qualification retains original expiry even after Reader downgrade.
                self.assertEqual(report["sample"]["hosts"][0]["evidence"], "expired")
                self.assertEqual(report["runtime"]["activeConnections"], 0)
            finally:
                await server.close()

    async def test_missing_subscribe_is_rejected_without_poll_fallback(self):
        publisher = Publisher("tmux", "local")
        publisher.capabilities = ("snapshot", "proof")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            try:
                report = await assess_configured("tmux", source="default", socket=path, local_host="local",
                                                 profile=publisher.state_profile, mode="subscribe", timeout_ms=100)
                self.assertFalse(report["ok"])
                self.assertFalse(report["acquired"])
                self.assertEqual(publisher.watchers, 0)
            finally:
                await server.close()

    async def test_catalog_budget_and_cancellation_never_report_health(self):
        authority = AsyncMock()
        async def stalled():
            await asyncio.Event().wait()
        authority.load.side_effect = stalled
        report = await assess_configured("tmux", source="default", socket="/private/mesh.sock", authority=authority,
                                         profile=Profile("tmux"), timeout_ms=10)
        self.assertEqual(report["error"], "deadline")
        task = asyncio.create_task(assess_configured("tmux", source="default", socket="/private/mesh.sock",
                                                    authority=authority, profile=Profile("tmux")))
        await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        authority.report_route.assert_not_awaited()
        with self.assertRaises(ValueError):
            await assess_configured("tmux", report_routes=True)

    async def test_repeated_cancellation_waits_for_owned_watch_retirement(self):
        publisher = Publisher("tmux", "local")
        started, release = asyncio.Event(), asyncio.Event()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            reader = None
            try:
                from mesh_plus.api import configured_reader
                reader = await configured_reader("tmux", source="default", socket=path, local_host="local",
                                                 profile=publisher.state_profile)
                response = await reader.snapshot()
                class Iterator:
                    def __aiter__(self):
                        return self
                    async def __anext__(self):
                        return response
                    async def aclose(self):
                        started.set()
                        await release.wait()
                def watch(*, request_id):
                    response["mesh"].update(operation="watch", requestId=request_id)
                    return Iterator()
                reader.watch = watch
                task = asyncio.create_task(assess(reader, mode="subscribe"))
                await asyncio.wait_for(started.wait(), 1)
                for _ in range(3):
                    task.cancel()
                    await asyncio.sleep(.01)
                    self.assertFalse(task.done())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            finally:
                release.set()
                await server.close()

    async def test_repeated_cancellation_during_acquisition_retires_reader(self):
        publisher = Publisher("tmux", "local")
        client = AsyncMock()
        for name in ("guard", "inspect", "route_token"):
            delattr(client, name)
        client.request.return_value = publisher.wrap()
        started, release = asyncio.Event(), asyncio.Event()
        async def close():
            started.set()
            await release.wait()
        client.close.side_effect = close
        async def connect():
            return client
        reader = Reader("tmux", [Endpoint("local", True, None, connect, publisher.codec)],
                        local_host="local", profile=publisher.state_profile)
        task = asyncio.create_task(assess(reader))
        try:
            await asyncio.wait_for(started.wait(), 1)
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(.01)
                self.assertFalse(task.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(reader.inspect()["activeConnections"], 0)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    async def test_late_synchronous_validation_cannot_report_success(self):
        import time

        from mesh_plus import diagnostics
        from mesh_plus.api import configured_reader
        publisher = Publisher("tmux", "local")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            try:
                reader = await configured_reader("tmux", source="default", socket=path, local_host="local",
                                                 profile=publisher.state_profile)
                original = diagnostics._summary
                def delayed(*args):
                    report = original(*args)
                    time.sleep(.03)
                    return report
                with patch.object(diagnostics, "_summary", side_effect=delayed):
                    report = await assess(reader, timeout_ms=20)
                self.assertFalse(report["ok"])
                self.assertFalse(report["acquired"])
                self.assertEqual(report["error"], "deadline")
                self.assertNotIn("sample", report)
            finally:
                await server.close()


    def test_explicit_v2_keeps_v1_and_redaction(self):
        self.assertEqual(doctor()["format"], "mesh-plus.diagnostics.v1")
        self.assertNotIn("sdkVersion", doctor())
        self.assertEqual(doctor_sdk()["sdkVersion"], 1)
        self.assertEqual(failure_code(ProtocolError("endpoint_codec_binding")), "rejected")
        self.assertEqual(sdk_failure_code(ProtocolError("endpoint_codec_binding")), "endpoint_codec_binding")
        self.assertEqual(sdk_failure_code(ProtocolError("/private/secret")), "rejected")
