import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from test_observer import native_fixture

from mesh_plus.catalog import Catalog
from mesh_plus.observer import ObserverAdapter, clock_domain
from mesh_plus.protocol import ProtocolError
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.transport import boottime_ms
from mesh_plus.view import current_sessions, reconstructed, validate_response

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
