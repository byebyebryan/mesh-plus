import copy
import json
import unittest
from pathlib import Path

from mesh_plus.protocol import Lifecycle, ProtocolError, decode, encode
from mesh_plus.transport import ssh_argv

ROOT = Path(__file__).resolve().parents[1]


def example(name):
    return json.loads((ROOT / "contracts/mesh-delivery-v1/examples" / (name + ".json")).read_text())


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.guard = Lifecycle(example("client-hello"), "fixture-host")
        hello = example("server-hello")
        self.guard.received(hello, len(encode(hello)))

    def test_transaction_preserves_state_on_bad_binding(self):
        before = copy.deepcopy(self.guard.__dict__)
        frame = example("client-request")
        frame["channelId"] = "22222222-2222-4222-8222-222222222222"
        with self.assertRaises(ProtocolError):
            self.guard.sent(frame, 100)
        self.assertEqual(before, self.guard.__dict__)

    def test_duplicate_keys_nonfinite_unicode_and_truncation(self):
        for raw in [b'{"kind":"hello","kind":"hello"}', b'{"v":NaN}',
                    b'{"v":"\\ud800"}', b'{"v":"\\u0000"}', b'{"v":1e999}', b'{']:
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                decode(raw, "client")

    def test_late_result_quarantined_and_terminal_enforced(self):
        request = example("client-request")
        self.guard.sent(request, 0)
        self.guard.expire(request["timeoutMs"])
        result = example("server-result")
        self.assertEqual(self.guard.received(result, len(encode(result))), "quarantined")
        result["sequence"] += 1
        with self.assertRaisesRegex(ProtocolError, "terminal_barrier"):
            self.guard.received(result, len(encode(result)))

    def test_ssh_fixed_command_and_policy(self):
        argv = ssh_argv("host-alias", "agent")
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("ControlPath=none", argv)
        self.assertEqual(argv[-1], "mesh-plus bridge --source agent --stdio")
        for destination in ["-evil", "host name", "host\nname"]:
            with self.assertRaises(ProtocolError):
                ssh_argv(destination, "agent")
        with self.assertRaises(ProtocolError):
            ssh_argv("host", "x;touch /tmp/no")

    def test_events_require_native_codec(self):
        hello = example("client-events-hello")
        with self.assertRaisesRegex(ProtocolError, "unsupported_product"):
            Lifecycle(hello, "fixture-host")


if __name__ == "__main__":
    unittest.main()
