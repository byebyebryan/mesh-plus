"""Explicit Mesh integration gate; uses real IPC with owned synthetic publishers."""

import asyncio
import copy
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import test_owner
from mesh_plus.catalog import Catalog
from test_fleet import Scanner

from tmux_observer._clock import boottime_ms
from tmux_observer._ipc import IPCError
from tmux_observer._tickets import TERMINAL
from tmux_observer_client.contract import validate_fleet_frame
from tmux_observer_client.mesh_fleet import MeshFleetPublisher
from tmux_observer_client.public import read_cached


class Authority:
    def __init__(self):
        self.calls = 0
        self.failed = False
        self.payload = {
            "schemaVersion": 1,
            "generatedAt": 1,
            "meshRevision": "sha256:" + "a" * 64,
            "localHostId": "fixture-local",
            "sshPolicy": {
                "executable": "ssh",
                "connectTimeoutSeconds": 2,
                "connectionAttempts": 1,
                "routeHealthTtlSeconds": 300,
            },
            "hosts": [
                {
                    "id": "fixture-local",
                    "display": "fixture",
                    "local": True,
                    "aliases": [],
                    "routes": [],
                }
            ],
        }

    async def load(self):
        self.calls += 1
        if self.failed:
            raise ValueError("fixture authority unavailable")
        return Catalog(copy.deepcopy(self.payload))


class MeshFleetTests(unittest.TestCase):
    def wait(self, check, budget=5):
        until = time.monotonic() + budget
        while time.monotonic() < until:
            try:
                value = check()
            except IPCError:
                value = None
            if value:
                return value
            time.sleep(0.01)
        self.fail("owned Mesh fleet condition did not complete")

    def start(self, root):
        owner, owner_thread, collector = test_owner.OwnerTests().start(root / "owner.sock")
        authority, scanner = Authority(), Scanner()
        fleet = MeshFleetPublisher(
            "fixture-local",
            path=root / "fleet.sock",
            owner_path=root / "owner.sock",
            scanner=scanner,
            authority=authority,
        )
        errors = []

        def run():
            try:
                fleet.run()
            except Exception as error:  # noqa: BLE001 - surface owned thread failures
                errors.append(error)

        thread = threading.Thread(target=run)
        thread.start()

        def cleanup():
            fleet.stop()
            thread.join(10)
            owner.stop()
            owner_thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertFalse(errors, errors)

        self.addCleanup(cleanup)

        def ready():
            frame = self.read(fleet)
            view = frame["snapshot"]
            return (
                frame
                if (
                    view["mesh"]["state"] == "ready"
                    and view["desktop"]["state"] == "ready"
                    and view["hosts"][0]["owner"]["localExpiry"] > boottime_ms()
                )
                else None
            )

        self.wait(ready)
        return fleet, owner, collector, scanner, authority

    def read(self, fleet, **kwargs):
        return validate_fleet_frame(
            read_cached(
                fleet.state.context_id, path=fleet.path, expected_host="fixture-local", **kwargs
            )
        )

    def test_cached_reads_share_one_mesh_reader_and_never_schedule_collection(self):
        with tempfile.TemporaryDirectory(prefix="tmux-mesh-test-") as temporary:
            fleet, _owner, collector, scanner, authority = self.start(Path(temporary))
            before = collector.calls, len(scanner.calls), authority.calls
            for operation in ("snapshot", "status", "probe") * 5:
                self.read(fleet, operation=operation)
            self.assertEqual((collector.calls, len(scanner.calls), authority.calls), before)
            self.assertTrue(all(c.future is None for c in fleet.connections.values()))

    def test_rotation_reaches_projection_without_restarting_reader(self):
        from mesh_plus.reader import Reader

        original_watch = Reader.watch
        delivered = []
        from tmux_observer_client._mesh_worker import MeshWorker

        original_put = MeshWorker.put

        def fast_watch(reader, **kwargs):
            return original_watch(reader, proof_interval=0.1, **kwargs)

        def capture(worker, event):
            if event[0] == "view":
                host = event[1]["mesh"]["hosts"][0]
                delivered.append((event[1]["mesh"]["reader"]["id"], host["delivery"]))
            return original_put(worker, event)

        with (
            tempfile.TemporaryDirectory(prefix="tmux-mesh-rotation-") as temporary,
            patch("mesh_plus.client.ROTATION_HANDLES", 4),
            patch.object(Reader, "watch", fast_watch),
            patch.object(MeshWorker, "put", capture),
        ):
            fleet, _owner, _collector, _scanner, _authority = self.start(Path(temporary))
            self.wait(lambda: any(d["epoch"] >= 3 and d["status"] == "ready" for _, d in delivered))
            revoked = [
                d
                for _, d in delivered
                if d["error"] and d["error"]["code"] == "channel_rotation_required"
            ]
            self.assertGreaterEqual(len(revoked), 2)
            self.assertTrue(all(d["error"]["code"] == "channel_rotation_required" for d in revoked))
            self.assertEqual(len({reader for reader, _ in delivered}), 1)
            # The compatibility projection can regain current owner facts after rotation.
            self.wait(
                lambda: (
                    self.read(fleet)["snapshot"]["hosts"][0]["owner"]["localExpiry"] > boottime_ms()
                )
            )

    def test_grouped_refresh_requires_mesh_confirmed_native_attempt(self):
        with tempfile.TemporaryDirectory(prefix="tmux-mesh-refresh-") as temporary:
            fleet, _owner, collector, _scanner, _authority = self.start(Path(temporary))
            entered, release = threading.Event(), threading.Event()
            original_collect = collector.collect

            def held_sample(*, budget_ms):
                entered.set()
                if not release.wait(0.8):
                    raise TimeoutError("owned refresh successor was not released")
                return original_collect(budget_ms=budget_ms)

            collector.collect = held_sample
            self.addCleanup(release.set)
            ticket = self.read(
                fleet,
                operation="refresh",
                sources=[
                    {"hostId": "fixture-local", "source": source} for source in ("owner", "desktop")
                ],
            )["ticket"]
            self.assertTrue(entered.wait(0.5))
            # This success case observes the in-flight replacement before its
            # successor completes. Coalescing/gap rejection has a separate case.
            self.wait(
                lambda: self.read(fleet)["snapshot"]["hosts"][0]["owner"]["receipt"]["inFlight"],
                budget=0.5,
            )
            release.set()

            def terminal():
                frame = self.read(
                    fleet,
                    operation="refresh_status",
                    publisher_id=ticket["publisherId"],
                    ticket_id=ticket["id"],
                )
                return frame if frame["ticket"]["state"] in TERMINAL else None

            frame = self.wait(terminal)
            self.assertEqual(frame["ticket"]["state"], "complete", frame["ticket"])
            source = frame["snapshot"]["hosts"][0]["owner"]["receipt"]
            self.assertGreaterEqual(source["startedAt"], ticket["requestedAt"])
            self.assertGreaterEqual(frame["snapshot"]["desktop"]["startedAt"], source["acceptedAt"])

    def test_grouped_refresh_gap_is_a_terminal_scope_revocation(self):
        from mesh_plus.bridge import _Connection

        armed = threading.Event()
        original_emit = _Connection.emit

        async def gap_before_replacement(bridge, kind, **fields):
            if (
                kind == "data"
                and armed.is_set()
                and fields["payload"]["ownerFrame"]["receipt"]["inFlight"]
            ):
                armed.clear()
                key = fields["subscriptionId"]
                await original_emit(
                    bridge,
                    "control",
                    subscriptionId=key,
                    streamSequence=bridge.guard.handles[key]["stream"] + 1,
                    control="gap",
                    payload={"gapKind": "delivery", "reason": "state_coalesced"},
                )
                fields["streamSequence"] = bridge.guard.handles[key]["stream"] + 1
                fields["deliveryKind"] = "resync"
            return await original_emit(bridge, kind, **fields)

        with (
            tempfile.TemporaryDirectory(prefix="tmux-mesh-refresh-gap-") as temporary,
            patch.object(_Connection, "emit", gap_before_replacement),
        ):
            fleet, _owner, collector, _scanner, _authority = self.start(Path(temporary))
            release = threading.Event()
            original_collect = collector.collect

            def held_sample(*, budget_ms):
                if not release.wait(0.8):
                    raise TimeoutError("owned gap fixture successor was not released")
                return original_collect(budget_ms=budget_ms)

            collector.collect = held_sample
            self.addCleanup(release.set)
            armed.set()
            ticket = self.read(
                fleet,
                operation="refresh",
                sources=[
                    {"hostId": "fixture-local", "source": source} for source in ("owner", "desktop")
                ],
            )["ticket"]

            def terminal():
                frame = self.read(
                    fleet,
                    operation="refresh_status",
                    publisher_id=ticket["publisherId"],
                    ticket_id=ticket["id"],
                )
                return frame if frame["ticket"]["state"] in TERMINAL else None

            frame = self.wait(terminal)
            release.set()
            self.assertFalse(armed.is_set(), "the owned delivery gap must have been emitted")
            self.assertIn(frame["ticket"]["state"], {"failed", "stale_scope"})
            owner = next(row for row in frame["ticket"]["sources"] if row["source"] == "owner")
            self.assertEqual(owner["error"]["code"], "stale_scope")

    def test_rotation_can_overlap_retiring_local_bridge_handler(self):
        from mesh_plus.bridge import Bridge
        from mesh_plus.reader import Reader

        from tmux_observer_client import _mesh_worker

        original_serve = Bridge.serve
        original_reader = _mesh_worker.configured_reader
        original_watch = Reader.watch
        readers = []
        metrics = []
        original_put = _mesh_worker.MeshWorker.put

        async def retiring_serve(bridge, channel):
            try:
                await original_serve(bridge, channel)
            finally:
                # Client socket closure precedes bounded publisher retirement.
                await asyncio.sleep(0.1)

        async def capture_reader(*args, **kwargs):
            reader = await original_reader(*args, **kwargs)
            readers.append(reader)
            return reader

        def fast_watch(reader, **kwargs):
            return original_watch(reader, proof_interval=0.1, **kwargs)

        def capture_metrics(worker, event):
            if event[0] == "view" and readers:
                # Inspect on the owning event-loop thread, not this test thread.
                metrics.append(readers[0].inspect())
            return original_put(worker, event)

        with (
            tempfile.TemporaryDirectory(prefix="tmux-mesh-retirement-") as temporary,
            patch("mesh_plus.client.ROTATION_HANDLES", 4),
            patch.object(Bridge, "serve", retiring_serve),
            patch.object(_mesh_worker, "configured_reader", capture_reader),
            patch.object(_mesh_worker.MeshWorker, "put", capture_metrics),
            patch.object(Reader, "watch", fast_watch),
        ):
            fleet, _owner, _collector, _scanner, _authority = self.start(Path(temporary))
            self.wait(lambda: metrics and metrics[-1]["rotations"] >= 3)
            self.wait(
                lambda: (
                    self.read(fleet)["snapshot"]["hosts"][0]["owner"]["localExpiry"] > boottime_ms()
                )
            )
            self.assertEqual(metrics[-1]["connectionFailures"], 0)

    def test_authority_loss_retains_metadata_with_no_current_viewer(self):
        with tempfile.TemporaryDirectory(prefix="tmux-mesh-catalog-") as temporary:
            fleet, _owner, _collector, _scanner, authority = self.start(Path(temporary))
            authority.failed = True

            def failed():
                frame = self.read(fleet)
                return frame if frame["snapshot"]["mesh"]["state"] == "unavailable" else None

            frame = self.wait(failed, budget=7)
            host = frame["snapshot"]["hosts"][0]
            self.assertEqual(host["owner"]["localExpiry"], 0)
            self.assertTrue(host["sessions"])
            self.assertEqual(host["sessions"][0]["localViewer"]["state"], "unknown")

    def test_seventeenth_owner_reports_capacity_retains_history_and_recovers(self):
        with tempfile.TemporaryDirectory(prefix="tmux-mesh-capacity-") as temporary:
            fleet, _owner, _collector, _scanner, authority = self.start(Path(temporary))
            original = copy.deepcopy(authority.payload)
            authority.payload["hosts"].extend(
                {
                    "id": f"fixture-{index:02d}",
                    "display": f"Fixture {index}",
                    "local": False,
                    "aliases": [],
                    "routes": [
                        {
                            "destination": f"fixture-{index:02d}",
                            "configuredIndex": 0,
                            "lastReachableAt": None,
                            "lastUnreachableAt": None,
                        }
                    ],
                }
                for index in range(16)
            )
            authority.payload["meshRevision"] = "sha256:" + "b" * 64

            def capacity():
                frame = self.read(fleet)
                return frame if frame["snapshot"]["mesh"]["state"] == "capacity" else None

            frame = self.wait(capacity, budget=9)
            self.assertEqual(frame["snapshot"]["error"]["code"], "capacity")
            self.assertEqual(len(frame["snapshot"]["hosts"]), 1)
            self.assertTrue(frame["snapshot"]["hosts"][0]["sessions"])
            self.assertEqual(frame["snapshot"]["hosts"][0]["owner"]["localExpiry"], 0)
            authority.payload = original

            def recovered():
                frame = self.read(fleet)
                return (
                    frame
                    if frame["snapshot"]["mesh"]["state"] == "ready"
                    and frame["snapshot"]["hosts"][0]["owner"]["localExpiry"] > boottime_ms()
                    else None
                )

            self.wait(recovered, budget=9)


if __name__ == "__main__":
    unittest.main()
