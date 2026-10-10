import copy
import json
import unittest
from pathlib import Path

from mesh_plus.protocol import Lifecycle, ProtocolError, decode, encode, tree, validate
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
                    b'{"v":"\\ud800"}', b'{"v":"\\u0000"}', b'{"v":1e999}', b'{',
                    b'{"v":' + b'9' * 5000 + b'}']:
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                decode(raw, "client")

    def test_tree_safety_covers_ascii_unicode_subclasses_and_depth(self):
        class Text(str):
            def isascii(self):
                return True

        class Mapping(dict):
            pass

        class Array(list):
            pass

        for value in ("a\x00b", "snowman \u2603\x00", "\ud800", Text("\udfff"), float("nan"), float("inf")):
            for body in ({"nested": [value]}, Mapping(nested=Array([value]))):
                with self.subTest(body=repr(body)), self.assertRaises(ProtocolError):
                    tree(body)
        tree({"ascii": [0, True, None, 1.25], "unicode": "snowman \u2603"})
        value = "safe"
        for _ in range(64):
            value = [value]
        tree(value)
        with self.assertRaisesRegex(ProtocolError, "tree_depth"):
            tree([value])
        frame = example("client-request")
        validate(frame, "client")
        frame["requestId"] = "bad\x00"
        with self.assertRaises(ProtocolError):
            validate(frame, "client")

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

    def test_packaged_schemas_match_reviewed_contract(self):
        from importlib.resources import files
        for source in (ROOT / "contracts/mesh-delivery-v1").glob("*.schema.json"):
            self.assertEqual(files("mesh_plus").joinpath("schemas", source.name).read_bytes(), source.read_bytes())
        for source in (ROOT / "contracts/mesh-read-v1").glob("*.json"):
            self.assertEqual(files("mesh_plus").joinpath("schemas", "read-" + source.name).read_bytes(), source.read_bytes())
        for source in (ROOT / "reference/rofi-ssh-plus/contracts/host-mesh-v1/schemas").glob("*.json"):
            self.assertEqual(files("mesh_plus").joinpath("schemas", "host-" + source.name).read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
