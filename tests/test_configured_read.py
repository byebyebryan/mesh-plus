import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mesh_plus.catalog import Catalog
from mesh_plus.configured_read import configured_reader
from mesh_plus.protocol import ProtocolError

ROOT = Path(__file__).resolve().parents[1]


class ConfiguredReadTests(unittest.IsolatedAsyncioTestCase):
    def catalog(self):
        return Catalog(json.loads((ROOT / "reference/rofi-ssh-plus/contracts/host-mesh-v1/fixtures/valid/list-multi-route.json").read_text()))

    async def test_standalone_local_never_loads_authority_or_connects(self):
        authority = AsyncMock()
        with patch("mesh_plus.configured_read.connect_ipc", new_callable=AsyncMock) as connect:
            reader = await configured_reader("agent", source="agent", socket="/owned/read.sock",
                                             scope="local", local_host="snap", authority=authority)
        self.assertEqual([e.host for e in reader.endpoints], ["snap"])
        authority.load.assert_not_awaited()
        connect.assert_not_awaited()

    async def test_remote_binding_is_read_only_and_keeps_revision_monitor(self):
        catalog = self.catalog()
        authority = AsyncMock()
        authority.load.return_value = catalog
        with patch("mesh_plus.configured_read.connect_catalog_host", new_callable=AsyncMock) as connect:
            reader = await configured_reader("agent", source="agent", socket="/owned/read.sock",
                                             scope="hosts", hosts=["gamma", "beta"], authority=authority)
            self.assertEqual([e.host for e in reader.endpoints], ["gamma", "beta"])
            await reader.endpoints[0].connect()
            self.assertIsNone(connect.call_args.kwargs["authority"])
            self.assertEqual(await reader.catalog_check(), catalog.revision)
            self.assertEqual(reader.catalog_revision, catalog.revision)
        authority.report_route.assert_not_awaited()

    async def test_transport_route_reporting_requires_explicit_policy(self):
        authority = AsyncMock()
        authority.load.return_value = self.catalog()
        with patch("mesh_plus.configured_read.connect_catalog_host", new_callable=AsyncMock) as connect:
            reader = await configured_reader("agent", source="agent", socket="/owned/read.sock",
                                             scope="hosts", hosts=["beta"], authority=authority, report_routes=True)
            await reader.endpoints[0].connect()
            self.assertIs(connect.call_args.kwargs["authority"], authority)

    async def test_invalid_scope_never_dispatches(self):
        authority = AsyncMock()
        with self.assertRaisesRegex(ProtocolError, "selection_shape"):
            await configured_reader("agent", source="agent", socket="/owned/read.sock",
                                    scope="local", hosts=["beta"], authority=authority)
        authority.load.assert_not_awaited()
