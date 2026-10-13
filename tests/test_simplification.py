"""Fleet grouping retains independent admission, callback and mutation boundaries."""

import copy
import unittest
import uuid
from unittest.mock import patch

from sdk_fixture import Profile, Publisher
from test_agent_timing_profile import TimingPublisher

from mesh_plus.api import Endpoint, Reader, ReadGuard, current_sessions, validate_response
from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import boottime_ms
from mesh_plus.view import _control_validator


async def fleet(domain="tmux", hosts=4, rows=8, *, timing=False):
    profile = TimingPublisher().state_profile if timing else Profile(domain)
    endpoints = [Endpoint("host" + str(i), i == 0, None if i == 0 else "sha256:" + "b" * 64,
                          None, profile.bind("host" + str(i), "default")) for i in range(hosts)]
    outcomes = {}
    reader = Reader(domain, endpoints, local_host="host0", catalog_revision="sha256:" + "a" * 64, profile=profile)
    for index in range(hosts):
        host = "host" + str(index)
        publisher = TimingPublisher() if timing else Publisher(domain, host)
        if timing:
            def rebind(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key in {"hostScope", "hostId", "authority"}:
                            value[key] = host
                        else:
                            rebind(child)
                elif isinstance(value, list):
                    for child in value:
                        rebind(child)
            rebind(publisher.frame)
            publisher.host = host
            publisher.codec = profile.bind(host, "default")
        seed = publisher.frame["snapshot"]["sessions"][0]
        records = []
        for number in range(rows):
            row = copy.deepcopy(seed)
            if domain == "tmux":
                row["sessionId"] = "$" + str(number + 100)
            else:
                row["identity"]["nativeId"] = str(uuid.UUID(int=number + 100))
            records.append(row)
        publisher.frame["snapshot"]["sessions"] = records

        class Reply:
            codec = publisher.codec.validate_bridge

            async def request(self, operation="snapshot", parameters=None, **kwargs):
                return publisher.wrap(None if parameters is None else parameters["nonce"])

        endpoint = endpoints[index]
        outcomes[host] = await reader.read_host(Reply(), endpoint)
    return profile, reader, reader.compose(endpoints, outcomes, "a" * 32, "watch")


class SimplificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_fleet_projection_and_linear_host_classification(self):
        for domain, timing in (("tmux", False), ("agent", False), ("agent", True)):
            profile, _, response = await fleet(domain, hosts=16, rows=4, timing=timing)
            original = copy.deepcopy(response)
            with patch.object(profile, "record_host", wraps=profile.record_host) as classify:
                validate_response(response, profile=profile)
                # Classification scales with rows, not rows multiplied by hosts.
                self.assertLessEqual(classify.call_count, 3 * len(response["sessions"]))
            self.assertEqual(response, original)
            result = current_sessions(response, boottime_ms(), response["mesh"]["reader"]["clock"], profile=profile)
            self.assertEqual(result, response["sessions"])

    async def test_reconstruction_list_mutation_cannot_hide_lost_rows(self):
        profile, _, response = await fleet()
        original = copy.deepcopy(response)
        restore = profile.restore_native

        def destructive(owner, records):
            records.clear()
            return restore(owner, records)

        with patch.object(profile, "restore_native", side_effect=destructive):
            with self.assertRaisesRegex(ProtocolError, "owner_projection"):
                validate_response(response, profile=profile)
        self.assertEqual(response, original)

    async def test_owned_guard_still_revalidates_exposed_view_and_expiry(self):
        profile, _, response = await fleet()
        guard = ReadGuard("tmux", "a" * 32, profile=profile)
        guard.accept(response)
        clock = response["mesh"]["reader"]["clock"]
        original = copy.deepcopy(guard.view)
        response["sessions"].clear()
        current = guard.current(boottime_ms(), clock)
        self.assertEqual(len(current), 32)
        current[0]["name"] = "caller mutation"
        self.assertEqual(guard.view, original)
        self.assertEqual(guard.current(max(r["expiresAtMs"] for h in guard.view["mesh"]["hosts"] for r in h["receipts"]) + 1, clock), [])
        guard.view["sessions"][0]["sessionId"] = "$forged"
        with self.assertRaises(Exception):
            guard.current(boottime_ms(), clock)
        guard.disconnect()
        self.assertEqual(guard.current(boottime_ms(), clock), [])

    async def test_scope_order_and_ownerless_rows_still_reject(self):
        profile, _, response = await fleet()
        for label in ("order", "scope", "owner"):
            altered = copy.deepcopy(response)
            if label == "order":
                altered["sessions"].reverse()
            elif label == "scope":
                altered["sessions"][0]["hostId"] = "foreign"
            else:
                altered["mesh"]["hosts"][0]["owner"] = None
                altered["mesh"]["hosts"][0]["receipts"] = []
                altered["mesh"]["hosts"][0]["viewState"] = "unavailable"
            with self.subTest(label=label), self.assertRaises(Exception):
                validate_response(altered, profile=profile)

    def test_fixed_schema_reuse_does_not_cache_input_success(self):
        for kind in ("error", "control"):
            validator = _control_validator(kind)
            self.assertIs(validator, _control_validator(kind))
            with self.assertRaises(Exception):
                validator.validate({})
