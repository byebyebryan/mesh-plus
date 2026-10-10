"""Extracted Host Mesh configuration/health regression cases."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mesh_plus.authority import (
    MeshError,
    MeshPersistenceError,
    RouteHealthStore,
    current_time_ms,
    load_config,
    report_route,
)
from mesh_plus.authority_cli import main as authority_main

FIXTURES = Path(__file__).resolve().parents[1] / "reference/rofi-ssh-plus/contracts/host-mesh-v1/fixtures"


def write_config(root: Path, *, text: str | None = None) -> Path:
    path = root / "config" / "rofi-ssh-plus" / "config.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        text
        or """schema_version = 1
local_id = "alpha"
local_display = "Alpha"
local_aliases = ["alpha-native"]
[ssh]
executable = "ssh"
connect_timeout_seconds = 2
connection_attempts = 1
route_health_ttl_seconds = 300
[[hosts]]
id = "beta"
display = "Beta"
routes = ["beta-vpn.test", "beta-lan.test"]
aliases = ["beta-native"]
""",
        encoding="utf-8",
    )
    return path


class MeshConfigTests(unittest.TestCase):
    def test_public_catalog_cli_does_not_import_delivery_or_native_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_config(root)
            program = """
import importlib.abc, json, sys
class AuthorityOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'jsonschema', 'tmux_observer', 'agent_observer'}:
            raise ImportError('catalog command imported state dependency: ' + fullname)
sys.meta_path.insert(0, AuthorityOnly())
from mesh_plus.cli import main
sys.argv = ['mesh-plus', 'mesh', 'list', '--json']
raise SystemExit(main())
"""
            result = subprocess.run(
                [sys.executable, "-c", program], capture_output=True,
                env={**os.environ, "XDG_CONFIG_HOME": str(root / "config"),
                     "XDG_STATE_HOME": str(root / "state")}, check=True,
            )
            catalog = json.loads(result.stdout)
            self.assertEqual(catalog["localHostId"], "alpha")
            self.assertEqual([host["id"] for host in catalog["hosts"]], ["alpha", "beta"])

    def test_missing_config_synthesizes_local_only_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mesh = load_config(Path(directory) / "missing.toml", hostname=("alpha.example", "alpha"))
        self.assertEqual(mesh.local_host_id, "alpha")
        self.assertEqual(mesh.local_display, "alpha")
        self.assertEqual(len(mesh.hosts), 1)
        self.assertEqual(mesh.hosts[0].aliases, ("alpha.example", "alpha"))
        self.assertEqual(mesh.hosts[0].routes, ())

    def test_missing_config_sanitizes_unusable_inferred_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mesh = load_config(Path(directory) / "missing.toml", hostname=("bad name\n", "bad name\n"))
        self.assertEqual(mesh.local_host_id, "localhost")
        self.assertEqual(mesh.local_display, "localhost")
        self.assertEqual(mesh.local_host.aliases, ("localhost",))

    def test_local_only_fixture_is_a_valid_local_mesh(self) -> None:
        mesh = load_config(
            FIXTURES / "config-local-only.toml",
            hostname=("alpha.example", "alpha"),
        )
        self.assertEqual(mesh.local_host_id, "alpha")
        self.assertEqual(len(mesh.hosts), 1)
        self.assertEqual(mesh.remote_hosts, ())
        self.assertEqual(mesh.ssh_policy.route_health_ttl_seconds, 300)

    def test_config_normalizes_identity_but_preserves_route_spelling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(
                Path(directory),
                text="""schema_version = 1
local_id = "ALPHA"
local_display = "Alpha"
local_aliases = ["alpha-native"]
[[hosts]]
id = "BETA"
display = "Beta"
routes = ["User@Beta.TEST", "beta-lan.test"]
aliases = ["beta-native"]
""",
            )
            mesh = load_config(path, hostname=("alpha.example", "alpha"))
        self.assertEqual(mesh.local_host_id, "alpha")
        self.assertEqual(mesh.remote_hosts[0].id, "beta")
        self.assertEqual(mesh.remote_hosts[0].routes[0].destination, "User@Beta.TEST")
        self.assertTrue(mesh.mesh_revision.startswith("sha256:"))

    def test_configured_mesh_filters_inferred_hostname_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_config(
                Path(directory),
                text="""schema_version = 1
local_aliases = ["configured-native"]
[[hosts]]
id = "beta"
routes = ["beta.test"]
""",
            )
            mesh = load_config(path, hostname=("bad full\n", "bad name"))
        self.assertEqual(mesh.local_host_id, "localhost")
        self.assertEqual(mesh.local_aliases, ("configured-native",))
        self.assertTrue(all("\n" not in alias and " " not in alias for alias in mesh.local_aliases))

    def test_invalid_and_ambiguous_configuration_is_visible(self) -> None:
        invalids = (
            "schema_version = 1\nunknown = true\n",
            'schema_version = 1\nlocal_id = "alpha"\n[[hosts]]\nid = "beta"\ndisplay = "Beta"\nroutes = []\n',
            'schema_version = 1\nlocal_id = "alpha"\n[[hosts]]\nid = "beta"\ndisplay = "Beta"\nroutes = ["shared.test"]\n[[hosts]]\nid = "gamma"\ndisplay = "Gamma"\nroutes = ["SHARED.TEST"]\n',
            'schema_version = 1\nlocal_id = "alpha"\n[[hosts]]\nid = "beta"\nroutes = ["beta.test"]\n[[hosts]]\nid = "BETA"\nroutes = ["other.test"]\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, text in enumerate(invalids):
                path = write_config(root / str(index), text=text)
                with self.subTest(index=index), self.assertRaises(MeshError):
                    load_config(path, hostname=("alpha.example", "alpha"))

        for name in (
            "config-invalid-duplicate.toml",
            "config-invalid-ambiguous.toml",
        ):
            with self.subTest(fixture=name), self.assertRaises(MeshError):
                load_config(
                    FIXTURES / name,
                    hostname=("alpha.example", "alpha"),
                )

    def test_revision_excludes_health_updates_and_route_order_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_config(root)
            config = load_config(path, hostname=("alpha.example", "alpha"))
            health = RouteHealthStore(root / "health.json")
            now = 1_000_000
            with patch("mesh_plus.authority.current_time_ms", return_value=now):
                self.assertTrue(health.record("beta", "beta-vpn.test", "unreachable", now - 10))
                with_health = config.with_health(health.load())
                self.assertEqual(
                    [route.destination for route in with_health.routes_for(with_health.remote_hosts[0])],
                    ["beta-lan.test", "beta-vpn.test"],
                )
            self.assertEqual(
                config.mesh_revision,
                load_config(path, hostname=("alpha.example", "alpha")).mesh_revision,
            )
            self.assertFalse(health.record("beta", "beta-vpn.test", "reachable", now - 11))
            self.assertTrue(health.record("beta", "beta-vpn.test", "reachable", now + 1))

    def test_route_health_rejects_malformed_identity_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health.json"
            path.write_text(json.dumps({"version": True, "routes": {}}), encoding="utf-8")
            with self.assertRaises(MeshPersistenceError):
                RouteHealthStore(path).load()
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "routes": {"beta\x00bad route": {"lastReachableAt": 1}},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(MeshPersistenceError):
                RouteHealthStore(path).load()

    def test_report_rejects_malformed_revision_as_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mesh = load_config(
                write_config(Path(directory)),
                hostname=("alpha.example", "alpha"),
            )
            with self.assertRaises(MeshError) as caught:
                report_route(
                    mesh,
                    host_id="beta",
                    route="beta-vpn.test",
                    status="reachable",
                    source="fixture",
                    mesh_revision=123,
                    observed_at=1,
                    health_store=RouteHealthStore(Path(directory) / "health.json"),
                )
            self.assertEqual(caught.exception.code, "invalid_input")


class MeshCliTests(unittest.TestCase):
    def test_native_process_profile_and_unbounded_argument_error(self):
        environment = {**os.environ, **self.environment}
        command = [sys.executable, "-m", "mesh_plus.cli", "mesh", "list", "--json"]
        good = subprocess.run(command, env=environment, capture_output=True, timeout=3)
        self.assertEqual(good.returncode, 0, good.stderr.decode())
        result, expected = self.invoke(["mesh", "list", "--json"])
        self.assertEqual(result, 0)
        actual = json.loads(good.stdout)
        self.assertLessEqual(actual.pop("generatedAt"), expected.pop("generatedAt"))
        self.assertEqual(actual, expected)
        self.assertTrue(good.stdout.endswith(b"\n"))
        self.assertLessEqual(len(good.stdout), 512 * 1024)
        self.assertEqual(good.stderr, b"")
        bad = subprocess.run(command + ["--unknown", "x" * 100000], env=environment,
                             capture_output=True, timeout=3)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(json.loads(bad.stdout)["error"]["code"], "invalid_input")
        self.assertLessEqual(len(bad.stdout), 512 * 1024)
        self.assertEqual(bad.stderr, b"")

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        write_config(self.root)
        self.environment = {
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_STATE_HOME": str(self.root / "state"),
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def invoke(self, args: list[str]) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        result = authority_main(args[1:], environ=self.environment, stdout=output)
        return (result, json.loads(output.getvalue()))

    def test_list_schema_and_report_acceptance_errors(self) -> None:
        result, listing = self.invoke(["mesh", "list", "--json"])
        self.assertEqual(result, 0)
        self.assertEqual(listing["schemaVersion"], 1)
        self.assertEqual(listing["localHostId"], "alpha")
        self.assertEqual([item["id"] for item in listing["hosts"]], ["alpha", "beta"])
        self.assertEqual(listing["hosts"][1]["routes"][0]["configuredIndex"], 0)
        revision = listing["meshRevision"]
        observed_at = current_time_ms() - 100
        result, accepted = self.invoke(
            [
                "mesh",
                "report-route",
                "--json",
                "--host",
                "beta",
                "--route",
                "beta-vpn.test",
                "--status",
                "unreachable",
                "--source",
                "fixture",
                "--mesh-revision",
                str(revision),
                "--observed-at",
                str(observed_at),
            ]
        )
        self.assertEqual(result, 0)
        envelopes = json.loads((FIXTURES / "envelopes.json").read_text(encoding="utf-8"))
        self.assertEqual(accepted, envelopes["success"])
        result, duplicate = self.invoke(
            [
                "mesh",
                "report-route",
                "--json",
                "--host",
                "beta",
                "--route",
                "beta-vpn.test",
                "--status",
                "unreachable",
                "--source",
                "fixture",
                "--mesh-revision",
                str(revision),
                "--observed-at",
                str(observed_at),
            ]
        )
        self.assertEqual(result, 0)
        self.assertEqual(duplicate["accepted"], False)

    def test_report_error_envelopes_and_malformed_config(self) -> None:
        _, listing = self.invoke(["mesh", "list", "--json"])
        base = [
            "mesh",
            "report-route",
            "--json",
            "--host",
            "beta",
            "--route",
            "beta-vpn.test",
            "--status",
            "reachable",
            "--source",
            "fixture",
            "--mesh-revision",
            str(listing["meshRevision"]),
        ]
        result, error = self.invoke(base)
        self.assertNotEqual(result, 0)
        self.assertEqual(error["error"]["code"], "invalid_input")
        result, error = self.invoke(base + ["--observed-at", str(current_time_ms() + 600000)])
        self.assertNotEqual(result, 0)
        self.assertEqual(error["error"]["code"], "invalid_input")
        result, error = self.invoke(base[:-1] + ["sha256:stale", "--observed-at", str(current_time_ms())])
        self.assertNotEqual(result, 0)
        self.assertEqual(error["error"]["code"], "stale_mesh")
        config = Path(self.environment["XDG_CONFIG_HOME"]) / "rofi-ssh-plus" / "config.toml"
        config.write_text("schema_version = 1\nunknown = true\n", encoding="utf-8")
        result, error = self.invoke(["mesh", "list", "--json"])
        self.assertNotEqual(result, 0)
        self.assertEqual(error["error"]["code"], "invalid_config")

    def test_route_report_fixture_cases_are_enforced(self) -> None:
        fixture = json.loads((FIXTURES / "route-reports.json").read_text(encoding="utf-8"))
        mesh = load_config(FIXTURES / "config-multi-route.toml", hostname=("alpha.example", "alpha"))
        with tempfile.TemporaryDirectory() as directory:
            store = RouteHealthStore(Path(directory) / "health.json")
            clock = fixture["clock"]["now"]
            for case in fixture["cases"]:
                with self.subTest(name=case["name"]):
                    revision = case.get("meshRevision", mesh.mesh_revision)
                    try:
                        accepted = report_route(
                            mesh,
                            host_id=case["host"],
                            route=case["route"],
                            status=case["status"],
                            source="fixture",
                            mesh_revision=revision,
                            observed_at=case["observedAt"],
                            health_store=store,
                            now_ms=clock,
                        )
                    except MeshError as error:
                        self.assertEqual(error.code, case["expectedError"])
                    else:
                        self.assertNotIn("expectedError", case)
                        self.assertEqual(accepted, case["expectedAccepted"])

    def test_route_order_fixture_restores_configured_preference(self) -> None:
        fixture = json.loads((FIXTURES / "route-order.json").read_text(encoding="utf-8"))
        mesh = load_config(FIXTURES / "config-multi-route.toml", hostname=("alpha.example", "alpha"))
        with tempfile.TemporaryDirectory() as directory:
            store = RouteHealthStore(Path(directory) / "health.json")
            self.assertTrue(
                store.record(
                    "beta", "beta-vpn.test", "unreachable", fixture["routes"][0]["lastUnreachableAt"]
                )
            )
            for observation in fixture["observations"]:
                with self.subTest(now=observation["now"]):
                    current = mesh.with_health(store.load())
                    order = [
                        route.destination
                        for route in current.routes_for(current.host_by_id("beta"), now_ms=observation["now"])
                    ]
                    self.assertEqual(order, observation["expectedOrder"])
