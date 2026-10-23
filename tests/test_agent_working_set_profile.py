"""Explicit working-set registration preserves existing SDK1 defaults."""

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft202012Validator, ValidationError

from mesh_plus.api import descriptor
from mesh_plus.cli import configured_adapter
from mesh_plus.protocol import ProtocolError
from mesh_plus.state import resolve_profile

PROFILE = "agent-observer.mesh-working-set.v1"


class WorkingSetRegistrationTests(unittest.TestCase):
    def test_packaged_schema_rejects_duplicate_support_maps_without_owner_callback(self):
        profile = json.loads(files("mesh_plus").joinpath(
            "schemas/read-agent-working-set.profile.schema.json").read_text())
        owner = profile["properties"]["mesh"]["allOf"][1]["properties"]["hosts"]["items"]["properties"]["owner"]["anyOf"][0]
        metadata = owner["properties"]["metadata"]["anyOf"][0]
        support = {"serviceId": "00000000-0000-4000-8000-000000000001",
                   "provider": "codex", "namespace": "sha256:" + "a" * 64,
                   "contextGeneration": 1, "component": "runtime", "accepted": 1,
                   "sampledBoottimeMs": 1, "expiresBoottimeMs": 100000}
        scope = {"provider": "codex", "namespace": support["namespace"],
                 "contextGeneration": 1, "continuity": 1, "supportTable": [support],
                 "clocks": [], "coverage": {"status": "unsupported", "reason": "fixture", "supports": []},
                 "members": [], "uncertain": [], "nonmembers": []}
        validator = Draft202012Validator(metadata)
        validator.validate({"scopes": [scope]})
        scope["supportTable"].append(dict(support))
        with self.assertRaises(ValidationError) as rejected:
            validator.validate({"scopes": [scope]})
        self.assertEqual(rejected.exception.validator, "uniqueItems")

    def test_explicit_descriptor_binds_packaged_profile_without_changing_defaults(self):
        working = descriptor("agent", profile_id=PROFILE)
        raw = files("mesh_plus").joinpath("schemas/read-agent-working-set.profile.schema.json").read_bytes()
        self.assertEqual((working.sdk_version, working.native_protocol, working.native_version),
                         (1, "agent-observer.working-set", 1))
        self.assertEqual(working.contract_digest, "sha256:" + hashlib.sha256(raw).hexdigest())
        self.assertEqual(working.frame_bytes, 8_404_992)
        self.assertEqual(descriptor("agent").profile_id, "agent-observer.mesh-candidate.v1")
        self.assertEqual(descriptor("tmux").profile_id, "tmux-observer.mesh-candidate.v1")
        for old in ("agent-observer.mesh-candidate.v2", "agent-observer.mesh-candidate.v3"):
            self.assertNotEqual(working.contract_digest, descriptor("agent", profile_id=old).contract_digest)
        for domain, profile_id in (("tmux", PROFILE), ("agent", PROFILE + ".unknown")):
            with self.subTest(domain=domain, profile=profile_id), self.assertRaises(ProtocolError):
                descriptor(domain, profile_id=profile_id)
        profile = SimpleNamespace(descriptor=replace(working, native_protocol="agent-observer.active-feed"))
        with self.assertRaisesRegex(ProtocolError, "profile_descriptor"):
            resolve_profile("agent", profile)

    def test_only_trusted_factory_can_return_new_profile_with_exact_binding(self):
        calls = []

        def factory(host, source, socket):
            calls.append((host, source, socket))
            return SimpleNamespace(host=host, source=source, profile=PROFILE,
                                   capabilities=("snapshot", "proof", "subscribe"),
                                   validate=lambda *a: None, snapshot=lambda *a: None,
                                   proof=lambda *a: None, watch=lambda *a: None)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.toml"
            path.write_text('version=1\nhost="fixture"\n[sources.working]\ndomain="agent"\nsocket="/owned.sock"\n')
            path.chmod(0o600)
            adapter = configured_adapter(path, "working", publisher_factories={"agent": factory})
            self.assertEqual(calls, [("fixture", "working", "/owned.sock")])
            self.assertEqual(adapter.profile, PROFILE)
            for field, bad in (("host", "foreign"), ("source", "other"),
                               ("profile", PROFILE + ".unregistered"),
                               ("capabilities", ("snapshot", "action")),
                               ("capabilities", ("snapshot", "snapshot"))):
                prior = getattr(adapter, field)
                setattr(adapter, field, bad)
                with self.subTest(field=field, value=bad), self.assertRaises(ProtocolError):
                    configured_adapter(path, "working", publisher_factories={"agent": lambda *a: adapter})
                setattr(adapter, field, prior)
