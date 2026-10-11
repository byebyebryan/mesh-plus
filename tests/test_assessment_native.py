import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from mesh_plus.api import Bridge
from mesh_plus.testing.sample import Publisher
from mesh_plus.transport import IPCServer


class NativeAssessmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_assess_cli_preserves_separate_v2_stdout(self):
        import sys
        publisher = Publisher("tmux", "local")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            try:
                child = await asyncio.create_subprocess_exec(sys.executable, "-m", "mesh_plus.cli", "assess",
                    "--domain", "tmux", "--source", "default", "--socket", str(path), "--local-host", "local",
                    "--mode", "subscribe", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await asyncio.wait_for(child.communicate(), 5)
                self.assertEqual(child.returncode, 0, stderr)
                report = json.loads(stdout)
                self.assertEqual(report["format"], "mesh-plus.diagnostics.v2")
                self.assertTrue(report["acquired"])
            finally:
                await server.close()
