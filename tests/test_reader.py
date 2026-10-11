import asyncio
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema.exceptions import ValidationError
from test_observer import native_fixture

from mesh_plus.catalog import Catalog
from mesh_plus.observer import ObserverAdapter, clock_domain
from mesh_plus.protocol import ProtocolError
from mesh_plus.reader import Endpoint, PublicationState, Reader
from mesh_plus.transport import boottime_ms
from mesh_plus.view import ReadGuard, current_sessions, reconstructed, validate_response

ROOT = Path(__file__).resolve().parents[1]


class CachedClient:
    def __init__(self, domain, host, *, wrong_nonce=False):
        self.adapter = ObserverAdapter(domain, host, "default", "/unused")
        self.codec = self.adapter.validate
        self.frame = native_fixture(domain)
        self.wrong_nonce = wrong_nonce
        self.closed = False
        now = boottime_ms() - 100
        shift = now - self.adapter.emitted(self.frame)

        def rewrite(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"hostId", "hostScope", "authority"}:
                        value[key] = host
                    elif key in {"encodedAt", "startedAt", "finishedAt", "acceptedAt", "expiresAt", "lastAttemptAt",
                                 "emittedBoottimeMs", "sampledBoottimeMs", "expiresBoottimeMs"} and type(item) is int:
                        value[key] += shift
                    else:
                        rewrite(item)
            elif isinstance(value, list):
                for item in value:
                    rewrite(item)
        rewrite(self.frame)

    async def request(self, operation="snapshot", parameters=None, **_):
        nonce = parameters["nonce"] if operation == "proof" else None
        if self.wrong_nonce and nonce:
            nonce = "0" * 32
        return self.adapter.wrap(copy.deepcopy(self.frame), nonce)

    async def close(self):
        self.closed = True


class ViewTests(unittest.TestCase):
    def test_repeated_structure_never_bypasses_native_checks_or_python_types(self):
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/tmux-local.json").read_text())
        validate_response(response)
        validate_response(copy.deepcopy(response))
        with patch("mesh_plus.observer.ObserverCodec.native", side_effect=ProtocolError("native_rejected")):
            with self.assertRaisesRegex(ProtocolError, "native_rejected"):
                validate_response(response)
        changed = copy.deepcopy(response)
        changed["sessions"] = tuple(changed["sessions"])
        with self.assertRaises(ValidationError):
            validate_response(changed)
        changed = copy.deepcopy(response)
        changed["mesh"]["hosts"][0]["receipts"][0]["expiresAtMs"] += 1
        with self.assertRaisesRegex(ProtocolError, "local_expiry_changed"):
            validate_response(changed)
        clock = response["mesh"]["reader"]["clock"]
        self.assertEqual(current_sessions(response, 2**52, clock), [])

    def test_stream_guard_quarantines_cross_request_and_requires_gap_resync(self):
        view = json.loads((ROOT / "contracts/mesh-read-v1/examples/tmux-local.json").read_text())
        view["mesh"].update(operation="watch", requestId="a" * 32)
        view["mesh"]["reader"].update(sequence=1, revision=1)
        guard = ReadGuard("tmux", "a" * 32, host_ids=view["mesh"]["scope"]["hostIds"])
        guard.accept(view)
        crossed = copy.deepcopy(view)
        crossed["mesh"].update(requestId="b" * 32)
        crossed["mesh"]["reader"]["sequence"] = 2
        with self.assertRaisesRegex(ProtocolError, "read_request_binding"):
            guard.accept(crossed)
        self.assertEqual(guard.sequence, 1)
        control = {"protocol": view["protocol"], "schemaVersion": 1,
                   "mesh": {key: view["mesh"][key] for key in ("meshProtocol", "requestId", "operation", "access")}}
        control["mesh"].update(reader={**view["mesh"]["reader"], "sequence": 2}, kind="gap")
        guard.accept(control)
        self.assertEqual(guard.current(2000, view["mesh"]["reader"]["clock"]), [])
        replacement = copy.deepcopy(view)
        replacement["mesh"]["reader"]["sequence"] = 3
        with self.assertRaisesRegex(ProtocolError, "read_resync_required"):
            guard.accept(replacement)
        replacement["mesh"]["kind"] = "resync"
        guard.accept(replacement)
        guard.accept({"meshProtocol": 1, "requestId": "a" * 32,
                      "error": {"code": "scope_changed", "message": "Resubscribe"}})
        with self.assertRaisesRegex(ProtocolError, "read_terminal_barrier"):
            guard.accept(replacement)

    def test_interleaved_host_rows_are_rejected(self):
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/agent-fleet.json").read_text())
        response["sessions"].reverse()
        with self.assertRaisesRegex(ProtocolError, "row_host_order"):
            validate_response(response)

    def test_stream_guard_requires_resync_for_host_reconnect_and_no_epoch_regression(self):
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/tmux-local.json").read_text())
        response["mesh"].update(operation="watch", requestId="a" * 32)
        guard = ReadGuard("tmux", "a" * 32)
        guard.accept(response)
        replacement = copy.deepcopy(response)
        replacement["mesh"]["reader"].update(sequence=2, revision=2)
        replacement["mesh"]["hosts"][0]["delivery"]["epoch"] += 1
        with self.assertRaisesRegex(ProtocolError, "read_resync_required"):
            guard.accept(replacement)
        self.assertEqual(guard.sequence, 1)
        replacement["mesh"]["kind"] = "resync"
        guard.accept(replacement)
        replacement["mesh"]["reader"].update(sequence=3, revision=3)
        replacement["mesh"]["hosts"][0]["delivery"]["epoch"] -= 1
        with self.assertRaisesRegex(ProtocolError, "read_host_epoch_regression"):
            guard.accept(replacement)
        self.assertTrue(guard.current(2000, response["mesh"]["reader"]["clock"]))
        guard.disconnect()
        self.assertEqual(guard.current(2000, response["mesh"]["reader"]["clock"]), [])

    def test_native_receipt_health_cannot_be_reclassified(self):
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/agent-local.json").read_text())
        response["mesh"]["hosts"][0]["receipts"][0]["health"] = "partial"
        with self.assertRaisesRegex(ProtocolError, "receipt_health_upgrade"):
            validate_response(response)

    def test_all_frozen_profiles_and_expiry(self):
        for path in (ROOT / "contracts/mesh-read-v1/examples").glob("*.json"):
            if path.name.startswith(("tmux-", "agent-")):
                response = json.loads(path.read_text())
                with self.subTest(path=path.name):
                    validate_response(response)
                    self.assertEqual(current_sessions(response, 2**52, response["mesh"]["reader"]["clock"]), [])

    def test_missing_receipt_and_forged_proof_rejected(self):
        path = ROOT / "contracts/mesh-read-v1/examples/agent-fleet.json"
        response = json.loads(path.read_text())
        response["mesh"]["hosts"][0]["receipts"].pop()
        with self.assertRaisesRegex(ProtocolError, "receipt_scope"):
            validate_response(response)
        response = json.loads(path.read_text())
        response["mesh"]["hosts"][1]["delivery"]["proof"]["payloadDigest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ProtocolError, "remote_proof_binding"):
            validate_response(response)

    def test_one_expired_component_revokes_its_provider_only(self):
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/agent-local.json").read_text())
        host = response["mesh"]["hosts"][0]
        codex = host["owner"]["service"]["sources"][0]
        history = next(c for c in codex["components"] if c["name"] == "history")
        history["expiresBoottimeMs"] = 2500
        receipt = next(r for r in host["receipts"] if r["sourceId"].startswith("codex:") and r["component"] == "history")
        receipt.update(expiresAtMs=2500, remainingMs=500)
        rows = current_sessions(response, 3000, response["mesh"]["reader"]["clock"])
        self.assertTrue(rows)
        self.assertTrue(all(row["identity"]["provider"] == "claude" for row in rows))
        receipt.update(health="stale", expiresAtMs=None, remainingMs=0)
        response["mesh"]["reader"]["encodedAtMs"] = 3000
        rows = current_sessions(response, 3000, response["mesh"]["reader"]["clock"])
        self.assertTrue(rows)
        self.assertTrue(all(row["identity"]["provider"] == "claude" for row in rows))

    def test_unsaved_stale_runtime_is_not_renewed_by_history(self):
        response = json.loads((ROOT / "contracts/mesh-read-v1/examples/agent-local.json").read_text())
        row = response["sessions"][0]
        row["hasSavedHistory"] = False
        clock = response["mesh"]["reader"]["clock"]
        self.assertIn(row, current_sessions(response, 2000, clock))
        # A detected runtime fault precedes the producer's finite retirement.
        # Saved metadata remains independently current; the raw row is retained.
        for name in ("runtime", "phase", "outcome"):
            if row[name] is not None:
                row[name].update(value="unknown", health="stale", reason="service_source_expired")
        row["blockedReasons"] = []
        host = response["mesh"]["hosts"][0]
        source = host["owner"]["service"]["sources"][0]
        metadata = host["owner"]["metadata"]["sources"][0]
        metadata["coverage"]["runtime"].update(status="unavailable", reason="collection_failed")
        metadata["sourceHealth"] = "partial"
        component = next(c for c in source["components"] if c["name"] == "runtime")
        component.update(health="stale", lastResult="collection_failed")
        receipt = next(r for r in host["receipts"] if r["sourceId"].startswith("codex:") and r["component"] == "runtime")
        receipt.update(health="stale", expiresAtMs=None, remainingMs=0)
        validate_response(response)
        self.assertNotIn(row, current_sessions(response, 2000, clock))
        self.assertIn(row, response["sessions"])
        self.assertTrue(any(r["identity"]["provider"] == "claude" for r in current_sessions(response, 2000, clock)))
        row["hasSavedHistory"] = True
        self.assertIn(row, current_sessions(response, 2000, clock))

    def test_catalog_fixture_parity_and_identity_collision(self):
        path = ROOT / "reference/rofi-ssh-plus/contracts/host-mesh-v1/fixtures/valid/list-multi-route.json"
        payload = json.loads(path.read_text())
        catalog = Catalog(payload)
        self.assertEqual(catalog.select("local")[0]["id"], "alpha")
        self.assertEqual(catalog.select("hosts", ["gamma", "beta"])[0]["id"], "gamma")
        route = catalog.hosts[1]["routes"][0]
        self.assertTrue(catalog.route_token("beta", route).startswith("sha256:"))
        payload["hosts"][2]["aliases"].append("beta")
        with self.assertRaisesRegex(ProtocolError, "catalog_ambiguous_identity"):
            Catalog(payload)


class ReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_concurrency_is_four_across_selected_hosts(self):
        active, maximum = 0, 0
        def endpoint(index):
            host = "host" + str(index)
            async def connect():
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                try:
                    await asyncio.sleep(.02)
                    return CachedClient("tmux", host)
                finally:
                    active -= 1
            return Endpoint(host, index == 0, None if index == 0 else "sha256:" + "a" * 64, connect)
        reader = Reader("tmux", [endpoint(i) for i in range(8)], local_host="host0",
                        catalog_revision="sha256:" + "b" * 64)
        response = await reader.snapshot()
        self.assertEqual(response["mesh"]["status"], "complete")
        self.assertEqual(maximum, 4)
    async def test_wire_request_preserves_correlation_and_rejects_before_dispatch(self):
        calls = []
        async def connect():
            calls.append(True)
            return CachedClient("tmux", "local")
        reader = Reader("tmux", [Endpoint("local", True, None, connect)], local_host="local")
        request = {"meshProtocol": 1, "requestId": "a" * 32, "profile": "tmux-observer.mesh-candidate.v1",
                   "operation": "snapshot", "access": "cached", "selection": {"mode": "local", "hostIds": []},
                   "extensions": {}}
        frames = [frame async for frame in reader.execute(request)]
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["mesh"]["requestId"], request["requestId"])
        calls.clear()
        request["selection"] = {"mode": "hosts", "hostIds": ["unknown"]}
        frames = [frame async for frame in reader.execute(request)]
        self.assertEqual(frames[0]["requestId"], request["requestId"])
        self.assertEqual(frames[0]["error"]["code"], "unknown_host")
        self.assertFalse(calls)
    async def test_publication_sequence_is_per_request_and_revision_excludes_encoding_time(self):
        client = CachedClient("tmux", "local")
        async def connect():
            return client
        endpoint = Endpoint("local", True, None, connect)
        reader = Reader("tmux", [endpoint], local_host="local")
        snapshot = await reader.snapshot()
        other = await reader.snapshot()
        self.assertEqual(snapshot["mesh"]["reader"]["sequence"], 1)
        self.assertEqual(other["mesh"]["reader"]["sequence"], 1)
        outcome = (snapshot["mesh"]["hosts"][0], snapshot["sessions"])
        state = PublicationState()
        one = reader.compose([endpoint], {"local": outcome}, "a" * 32, "watch", state=state)
        two = reader.compose([endpoint], {"local": outcome}, "a" * 32, "watch", state=state)
        self.assertEqual(two["mesh"]["reader"]["sequence"], 2)
        self.assertEqual(two["mesh"]["reader"]["revision"], one["mesh"]["reader"]["revision"])
    async def test_catalog_replacement_terminates_watch_without_late_publication(self):
        cancelled = asyncio.Event()
        async def blocked():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        async def replaced():
            return "sha256:" + "c" * 64
        reader = Reader("tmux", [Endpoint("remote", False, "sha256:" + "a" * 64, blocked)],
                        local_host="local", catalog_revision="sha256:" + "b" * 64, catalog_check=replaced)
        watch = reader.watch(request_id="a" * 32)
        try:
            baseline = await anext(watch)
            self.assertEqual(baseline["mesh"]["status"], "pending")
            error = await asyncio.wait_for(anext(watch), .5)
            self.assertEqual(error["requestId"], "a" * 32)
            self.assertEqual(error["error"]["code"], "scope_changed")
            with self.assertRaises(StopAsyncIteration):
                await anext(watch)
            self.assertTrue(cancelled.is_set())
        finally:
            await watch.aclose()

    async def test_fleet_watch_requires_explicit_catalog_monitor(self):
        calls = []
        async def connect():
            calls.append(True)
        reader = Reader("tmux", [Endpoint("local", True, None, connect)],
                        local_host="local", catalog_revision="sha256:" + "b" * 64)
        frames = [frame async for frame in reader.watch()]
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["error"]["code"], "catalog_monitor_required")
        self.assertFalse(calls)

    async def test_snapshot_total_budget_preserves_healthy_sibling_and_correlation(self):
        healthy = CachedClient("tmux", "local")
        cancelled = asyncio.Event()
        async def good():
            return healthy
        async def blocked():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        reader = Reader("tmux", [Endpoint("local", True, None, good),
                                  Endpoint("remote", False, "sha256:" + "a" * 64, blocked)],
                        local_host="local", catalog_revision="sha256:" + "b" * 64)
        response = await asyncio.wait_for(reader.snapshot(timeout_ms=50, request_id="a" * 32), .5)
        self.assertEqual(response["mesh"]["status"], "partial")
        self.assertEqual(response["mesh"]["requestId"], "a" * 32)
        self.assertEqual(response["mesh"]["hosts"][1]["delivery"]["error"]["code"], "timeout")
        self.assertTrue(cancelled.is_set())
        self.assertTrue(healthy.closed)
        self.assertTrue(reader.inspect()["partial"])
        self.assertEqual(reader.inspect()["connectionFailures"], 1)
    async def test_same_local_and_fleet_shape_with_independent_failure(self):
        for domain in ("tmux", "agent"):
            clients = []

            def endpoint(host, local, *, fail=False, wrong_nonce=False):
                async def connect():
                    if fail:
                        raise OSError("offline")
                    client = CachedClient(domain, host, wrong_nonce=wrong_nonce)
                    clients.append(client)
                    return client
                return Endpoint(host, local, None if local else "sha256:" + "a" * 64, connect)

            reader = Reader(domain, [endpoint("local", True), endpoint("remote", False), endpoint("offline", False, fail=True)],
                            local_host="local", catalog_revision="sha256:" + "b" * 64)
            fleet = await reader.snapshot()
            local = await reader.snapshot(mode="local")
            self.assertEqual(set(local), set(fleet))
            self.assertEqual(fleet["mesh"]["status"], "partial")
            self.assertEqual(local["mesh"]["status"], "complete")
            self.assertEqual(len(fleet["mesh"]["hosts"]), 3)
            self.assertTrue(current_sessions(fleet, boottime_ms(), clock_domain()))
            for host in fleet["mesh"]["hosts"][:2]:
                original = next(client.frame for client in clients if client.adapter.host == host["hostId"])
                self.assertEqual(reconstructed(fleet, host), original)
            self.assertTrue(all(client.closed for client in clients))
            self.assertTrue(reader.inspect()["partial"])
            self.assertGreater(reader.inspect()["uninstrumentedConnections"], 0)

    async def test_nonce_mismatch_excludes_one_host(self):
        client = CachedClient("agent", "remote", wrong_nonce=True)
        async def connect():
            return client
        reader = Reader("agent", [Endpoint("remote", False, "sha256:" + "a" * 64, connect)],
                        local_host="local", catalog_revision="sha256:" + "b" * 64)
        response = await reader.snapshot()
        self.assertEqual(response["mesh"]["status"], "unavailable")
        self.assertEqual(response["sessions"], [])
        self.assertTrue(client.closed)

    async def test_invalid_selection_before_dispatch(self):
        calls = []
        async def connect():
            calls.append(True)
        reader = Reader("tmux", [Endpoint("local", True, None, connect)], local_host="local")
        with self.assertRaises(ProtocolError):
            await reader.snapshot(mode="hosts", hosts=["unknown"])
        self.assertFalse(calls)

    async def test_suspend_expires_retained_view_without_new_source(self):
        client = CachedClient("tmux", "local")
        async def connect():
            return client
        endpoint = Endpoint("local", True, None, connect)
        reader = Reader("tmux", [endpoint], local_host="local")
        response = await reader.snapshot()
        self.assertEqual(response["mesh"]["hosts"][0]["viewState"], "current")
        outcome = (response["mesh"]["hosts"][0], response["sessions"])
        expiry = outcome[0]["receipts"][0]["expiresAtMs"]
        with patch("mesh_plus.reader.boottime_ms", return_value=expiry + 1):
            expired = reader.compose([endpoint], {"local": outcome}, "a" * 32)
        self.assertEqual(expired["mesh"]["hosts"][0]["viewState"], "historical")
        self.assertEqual(current_sessions(expired, expiry + 1, clock_domain()), [])
