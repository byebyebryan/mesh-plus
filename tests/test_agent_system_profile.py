"""Explicit successor selection over the unchanged SDK; no native packages."""

import asyncio
import copy
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jsonschema import ValidationError
from sdk_fixture import Profile, Publisher

from mesh_plus.api import (
    Bridge,
    Client,
    Endpoint,
    Reader,
    ReadGuard,
    descriptor,
    reconstructed,
    validate_response,
)
from mesh_plus.protocol import ProtocolError
from mesh_plus.state import resolve_profile
from mesh_plus.transport import IPCServer, boottime_ms, connect_ipc
from mesh_plus.view import profile_validator

PROFILE = "agent-observer.mesh-candidate.v3"


class SystemProfile(Profile):
    def __init__(self):
        self.domain = "agent"
        self.descriptor = descriptor("agent", profile_id=PROFILE)


class SystemPublisher(Publisher):
    def __init__(self):
        super().__init__("agent", "local")
        self.state_profile = SystemProfile()
        self.profile = PROFILE
        self.codec = self.state_profile.bind("local", "default")
        self.validate = self.codec.validate_bridge
        self.frame["serviceProtocol"] = 4
        snapshot = self.frame["snapshot"]
        snapshot["schemaVersion"] = 6
        for source in snapshot["sources"]:
            source["capabilities"]["timing"] = {"lastUpdated": False, "latestTurn": False}
        for row in snapshot["sessions"]:
            row["kind"] = "system"
            row["lastUpdated"] = {"at": None, "timestampPrecisionMs": None, "observedAt": None,
                                  "source": None, "health": "unsupported", "reason": "fixture_unproved", "receipt": None}
            row["latestTurn"] = {"value": None, "observedAt": None, "source": None,
                                 "health": "unsupported", "reason": "fixture_unproved", "receipt": None}


class SystemDescriptorTests(unittest.TestCase):
    def test_defaults_and_explicit_successor_are_distinct(self):
        self.assertEqual(descriptor("agent").native_version, 4)
        self.assertEqual(descriptor("tmux").native_version, 1)
        new = descriptor("agent", profile_id=PROFILE)
        self.assertEqual((new.sdk_version, new.native_version), (1, 6))
        self.assertNotEqual(new.contract_digest, descriptor("agent").contract_digest)
        self.assertEqual(new.frame_bytes, descriptor("agent").frame_bytes)

    def test_unregistered_and_wrong_domain_or_version_reject(self):
        for domain, name in (("tmux", PROFILE), ("agent", "agent-observer.mesh-candidate.v99")):
            with self.assertRaises(ProtocolError):
                descriptor(domain, profile_id=name)
        profile = SystemProfile()
        profile.descriptor = replace(profile.descriptor, native_version=4)
        with self.assertRaises(ProtocolError):
            resolve_profile("agent", profile)

    def test_packaged_strict_validators_do_not_share_profile_admission(self):
        publisher = SystemPublisher()
        profile = publisher.state_profile
        state = publisher.codec.inspect_native(publisher.frame)
        # The complete SDK path below validates full envelopes; here test the
        # strict row schema directly, including version negotiation boundaries.
        item = {"protocol": PROFILE, "schemaVersion": 1, "sessions": list(state.records)}
        # Reuse a frozen complete v1 aggregate's generic Mesh metadata.
        import json

        from sdk_fixture import ROOT
        old = json.loads((ROOT / "contracts/mesh-read-v1/examples/agent-local.json").read_text())
        item["mesh"] = old["mesh"]
        profile_validator("agent", PROFILE).validate(item)
        profile_validator("agent").validate(old)
        with self.assertRaises(ValidationError):
            profile_validator("agent").validate(item)
        with self.assertRaises(ValidationError):
            profile_validator("agent", PROFILE).validate(old)
        bad = copy.deepcopy(item)
        bad["sessions"][0]["latestTurn"]["payload"] = "rejected"
        with self.assertRaises(ValidationError):
            profile_validator("agent", PROFILE).validate(bad)
        self.assertEqual(profile.descriptor.profile_id, PROFILE)


class SystemDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_reader_and_watch_guard_preserve_native_frame(self):
        publisher = SystemPublisher()
        profile = publisher.state_profile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            async def connect():
                return await Client.connect(await connect_ipc(path), host="local", source="default",
                                            profile=PROFILE, codec=publisher.codec.validate_bridge)
            reader = Reader("agent", [Endpoint("local", True, None, connect, publisher.codec)],
                            local_host="local", profile=profile)
            watch = reader.watch(request_id="a" * 32, proof_interval=.1)
            try:
                response = await reader.snapshot()
                self.assertEqual(response["protocol"], PROFILE)
                validate_response(response, profile=profile)
                self.assertEqual(reconstructed(response, response["mesh"]["hosts"][0], profile=profile), publisher.frame)
                request = {"meshProtocol": 1, "requestId": "b" * 32, "profile": PROFILE,
                           "operation": "snapshot", "access": "cached", "selection": {"mode": "local", "hostIds": []}, "extensions": {}}
                messages = [message async for message in reader.execute(request)]
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0]["protocol"], PROFILE)
                self.assertEqual(messages[0]["mesh"]["status"], "complete")
                # Cache success for v2 cannot admit this body under v1.
                with self.assertRaises(ValidationError):
                    validate_response(response)
                guard = ReadGuard("agent", "a" * 32, profile=profile)
                for _ in range(10):
                    frame = await asyncio.wait_for(anext(watch), 2)
                    guard.accept(frame)
                    if frame["mesh"]["status"] == "complete":
                        break
                self.assertTrue(guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]))
                self.assertEqual(guard.profile, PROFILE)
                guard.disconnect()
                self.assertEqual(guard.current(boottime_ms(), frame["mesh"]["reader"]["clock"]), [])
            finally:
                await watch.aclose()
                await server.close()
            self.assertEqual(publisher.watchers, 0)
            self.assertEqual(reader.inspect()["activeConnections"], 0)
