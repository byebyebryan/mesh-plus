"""Preparse refusal, parsed/queued transfer and held-error ownership."""

import gc
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mesh_plus.protocol import MAX_MESSAGE, ProtocolError, encode
from mesh_plus.transport import ssh_argv
from mesh_plus.view_feed import FeedBudget, FeedLimits
from mesh_plus.view_feed.wire import FeedWireCodec, _nodes


class ViewFeedWireTests(unittest.TestCase):
    def setUp(self):
        was_enabled = gc.isenabled()
        gc.disable()
        self.addCleanup(lambda: gc.enable() if was_enabled else None)

    def test_nodes_preflight_bounds_nested_keys_and_escaped_strings(self):
        value = {"雪": [None, {}, [False, 0, "a\\\"b,:{}[]"]], "": {"x": 1}}
        raw = encode(value)

        def nodes(v):
            if isinstance(v, dict):
                return 1 + sum(1 + nodes(c) for c in v.values())
            if isinstance(v, list):
                return 1 + sum(nodes(c) for c in v)
            return 1

        self.assertGreaterEqual(_nodes(raw), nodes(value))
        self.assertEqual(json.loads(raw), value)

    def test_carrier_capacity_refuses_before_io_or_json_parse(self):
        budget = FeedBudget(FeedLimits(encoded_bytes=MAX_MESSAGE))
        with self.assertRaisesRegex(ProtocolError, "view_feed_capacity"):
            FeedWireCodec(budget)
        self.assertEqual(budget.inspect()["heapBytes"], 0)
        self.assertEqual(budget.inspect()["encodedBytes"], 0)

    def test_node_capacity_refuses_before_parser(self):
        budget = FeedBudget()
        wire = FeedWireCodec(budget)
        base = budget.inspect()
        # A tiny encoded graph can still exhaust heap node capacity.
        raw = b"[" + b"{}," * 180_000 + b"{}]"
        with patch("mesh_plus.view_feed.wire.decode", side_effect=AssertionError("parse ran")):
            with self.assertRaisesRegex(ProtocolError, "view_feed_capacity"):
                wire.decode(raw, "server")
        self.assertEqual(budget.inspect()["heapBytes"], base["heapBytes"])
        wire.close()
        self.assertEqual(budget.inspect()["encodedBytes"], 0)

    def test_retained_real_parse_error_keeps_credit_until_dropped(self):
        budget = FeedBudget()
        wire = FeedWireCodec(budget)
        base = budget.inspect()["heapBytes"]
        saved = []
        try:
            wire.decode(b'{"kind":', "server")
        except ProtocolError as error:
            saved.append(error)
        self.assertEqual(len(saved), 1)
        self.assertGreater(budget.inspect()["heapBytes"], base)
        wire.close()
        self.assertGreater(budget.inspect()["heapBytes"], 0)
        saved.clear()
        self.assertEqual(budget.inspect()["heapBytes"], 0)
        self.assertEqual(budget.inspect()["encodedBytes"], 0)

    def test_encoded_bytes_keep_lease_after_wire_close_until_actual_drop(self):
        budget = FeedBudget()
        wire = FeedWireCodec(budget)
        raw = wire.encode({"x": ["雪", 1, None]})
        self.assertEqual(json.loads(raw), {"x": ["雪", 1, None]})
        wire.close()
        self.assertGreater(budget.inspect()["encodedBytes"], 0)
        del raw
        self.assertEqual(budget.inspect()["heapBytes"], 0)
        self.assertEqual(budget.inspect()["encodedBytes"], 0)

    def test_shared_ledger_narrow_does_not_refund_live_carrier(self):
        budget = FeedBudget()
        wire = FeedWireCodec(budget)
        before = budget.inspect()
        with self.assertRaisesRegex(ProtocolError, "view_feed_capacity"):
            budget.narrow(FeedLimits(encoded_bytes=1))
        self.assertEqual(budget.inspect(), before)
        wire.close()
        wire.close()
        self.assertEqual(budget.inspect()["heapBytes"], 0)

    def test_fixed_remote_command_preserves_policy_and_reached_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            command = Path(directory) / "mesh-plus"
            command.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\n')
            command.chmod(0o700)
            nonce = "a" * 32
            old = ssh_argv("host", "working", nonce=nonce)
            feed = ssh_argv("host", "working", nonce=nonce, view_feed=True)
            self.assertEqual(old[:-1], feed[:-1])
            result = subprocess.run(["/bin/sh", "-c", feed[-1]],
                                    env={**os.environ, "PATH": directory + ":/usr/bin:/bin"},
                                    capture_output=True, check=True)
            self.assertEqual(result.stdout, b"view-feed-bridge\n--source\nworking\n--stdio\n")
            self.assertEqual(result.stderr, ("\x1eROFI_PLUS_REACHED_V1:" + nonce + "\x1f\n").encode())
        with self.assertRaisesRegex(ProtocolError, "bridge_command"):
            ssh_argv("host", "working", sync=True, view_feed=True)
