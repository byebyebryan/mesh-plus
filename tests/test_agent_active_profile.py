"""Opt-in active delivery, public context expiry and independent Mesh proofs."""

import asyncio
import copy
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from active_fixture import PROFILE, ActiveProfile, ActiveSource
from jsonschema.exceptions import ValidationError
from prepared_fixture import StaticPreparation

from mesh_plus.api import Bridge, CachedPublisher, Client, Endpoint, PreparedReadGuard, Reader, descriptor
from mesh_plus.cli import configured_adapter
from mesh_plus.protocol import ProtocolError
from mesh_plus.state import resolve_profile, validate_bridge
from mesh_plus.transport import IPCServer, connect_ipc
from mesh_plus.view import profile_validator, reconstructed, validate_response


class ActiveDescriptorTests(unittest.TestCase):
    def test_explicit_active_descriptor_is_distinct_and_sdk_limits_unchanged(self):
        active = descriptor("agent", profile_id=PROFILE)
        full = descriptor("agent", profile_id="agent-observer.mesh-candidate.v3")
        self.assertEqual((active.sdk_version, active.native_protocol, active.native_version),
                         (1, "agent-observer.active-feed", 1))
        self.assertEqual(active.frame_bytes, full.frame_bytes)
        self.assertNotEqual(active.contract_digest, full.contract_digest)
        self.assertEqual(descriptor("agent").native_version, 4)
        self.assertEqual(descriptor("tmux").native_version, 1)
        for domain, name in (("tmux", PROFILE), ("agent", PROFILE + ".unsupported")):
            with self.assertRaises(ProtocolError):
                descriptor(domain, profile_id=name)
        bad = ActiveProfile()
        bad.descriptor = replace(active, native_protocol="agent-observer.snapshot")
        with self.assertRaises(ProtocolError):
            resolve_profile("agent", bad)

    def test_installed_factory_admits_only_exact_binding_and_existing_capabilities(self):
        profile = ActiveProfile()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text('version=1\nhost="fixture"\n[sources.active]\ndomain="agent"\nsocket="/owned.sock"\n')
            path.chmod(0o600)
            def factory(host, source, socket):
                self.assertEqual(socket, "/owned.sock")
                return CachedPublisher("agent", host, source, ActiveSource(host), profile=profile)
            result = configured_adapter(path, "active", publisher_factories={"agent": factory})
            self.assertEqual(result.profile, PROFILE)
            result.capabilities += ("digest-proof",)
            with self.assertRaisesRegex(ProtocolError, "publisher_factory_interface"):
                configured_adapter(path, "active", publisher_factories={"agent": lambda *a: result})
            result.capabilities = ("snapshot", "proof", "subscribe")
            result.source = "other"
            with self.assertRaisesRegex(ProtocolError, "publisher_factory_binding"):
                configured_adapter(path, "active", publisher_factories={"agent": lambda *a: result})

    def test_combined_owner_admission_does_not_bypass_mesh_envelope_receipts_or_digest(self):
        profile = ActiveProfile()
        source = ActiveSource()
        publisher = CachedPublisher("agent", "fixture", "active", source, profile=profile)
        proof = publisher.wrap(source.frame, "a" * 32)
        codec = profile.bind("fixture", "active")
        validate_bridge(profile, codec, proof)
        for mutation in (
            lambda value: value.update(ownerDigest="sha256:" + "0" * 64),
            lambda value: value.update(sourceId="other"),
            lambda value: value["remaining"][0].update(remainingMs=value["remaining"][0]["remainingMs"] + 1),
            lambda value: value.update(remaining=value["remaining"] * 17),
            lambda value: value["ownerFrame"]["selector"].update(providers=["claude"]),
        ):
            bad = copy.deepcopy(proof)
            mutation(bad)
            with self.subTest(bad=bad), self.assertRaises((ProtocolError, ValidationError)):
                validate_bridge(profile, codec, bad)
        self.assertNotIn("digest-proof", publisher.capabilities)


class ActiveDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def pipeline(self, *, empty, remote):
        profile, source = ActiveProfile(), ActiveSource("fixture", empty=empty)
        publisher = CachedPublisher("agent", "fixture", "active", source, profile=profile)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            codec = profile.bind("fixture", "active")
            async def connect():
                return await Client.connect(await connect_ipc(path), host="fixture", source="active",
                                            profile=PROFILE, codec=codec.validate_bridge)
            revision = "sha256:" + "a" * 64
            async def catalog_check():
                return revision
            reader = Reader("agent", [Endpoint("fixture", not remote, revision if remote else None, connect, codec)],
                            local_host="reader" if remote else "fixture", profile=profile,
                            catalog_revision=revision if remote else None,
                            catalog_check=catalog_check if remote else None)
            watch = reader.watch_admitted(request_id="a" * 32, proof_interval=.1)
            guard = PreparedReadGuard("agent", "a" * 32, profile=profile, preparation=StaticPreparation(profile))
            try:
                for _ in range(10):
                    guard.accept(await asyncio.wait_for(anext(watch), 2))
                    context = guard.context()
                    if context and context["mesh"]["status"] == "complete":
                        break
                self.assertEqual(context["mesh"]["status"], "complete")
                owned = guard.snapshot()
                self.assertEqual(len(owned["sessions"]), 0 if empty else 1)
                self.assertEqual(reconstructed(owned, owned["mesh"]["hosts"][0], profile=profile), source.frame)
                validate_response(owned, profile=profile)
                with self.assertRaises(ValidationError):
                    profile_validator("agent", "agent-observer.mesh-candidate.v3").validate(owned)
                now, clock = owned["mesh"]["reader"]["encodedAtMs"], owned["mesh"]["reader"]["clock"]
                guard.current(now, clock)  # Required public clock check, including empty views.
                context = guard.context()
                host = context["mesh"]["hosts"][0]
                self.assertEqual(host["owner"]["metadata"]["scopes"][0]["coverage"]["status"], "complete")
                runtime = next(r for r in host["receipts"] if r["component"] == "runtime")
                self.assertGreater(runtime["expiresAtMs"], now)
                self.assertEqual(bool(host["delivery"]["proof"]), remote)
                if remote:
                    self.assertGreaterEqual(source.reads, 1)  # Fresh post-nonce cached read.
                owned["mesh"]["hosts"][0]["owner"]["metadata"]["scopes"].clear()
                self.assertTrue(guard.context()["mesh"]["hosts"][0]["owner"]["metadata"]["scopes"])
                self.assertEqual(guard.current(runtime["expiresAtMs"], clock), [])
                # Retained complete metadata is informational: its translated deadline fails.
                retained = guard.context()["mesh"]["hosts"][0]
                self.assertLessEqual(next(r for r in retained["receipts"] if r["component"] == "runtime")["expiresAtMs"],
                                     runtime["expiresAtMs"])
                self.assertEqual(len(guard.snapshot()["sessions"]), 0 if empty else 1)
                with self.assertRaisesRegex(ProtocolError, "reader_clock_scope"):
                    guard.current(runtime["expiresAtMs"], {**clock, "bootId": "different"})
                self.assertIsNone(guard.context())
            finally:
                guard.disconnect()
                await watch.aclose()
                await server.close()
            self.assertEqual(reader.inspect()["activeConnections"], 0)
            self.assertEqual(source.watchers, 0)

    async def test_local_member_owned_context_and_expiry(self):
        await self.pipeline(empty=False, remote=False)

    async def test_local_complete_empty_metadata_expires_without_a_row(self):
        await self.pipeline(empty=True, remote=False)

    async def test_remote_full_nonce_proof_member_and_empty_scope(self):
        await self.pipeline(empty=False, remote=True)
        await self.pipeline(empty=True, remote=True)
