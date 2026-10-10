"""Actual delivery channels exercise rotation, revocation and cumulative IO."""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ssh_fixture import ssh_server
from test_reader import CachedClient

from mesh_plus.bridge import Bridge, Publication
from mesh_plus.client import Client
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.transport import IPCServer, connect_ipc
from mesh_plus.view import ReadGuard, current_sessions, row_host


class CachedPublisher:
    capabilities = ("snapshot", "proof", "subscribe")
    source = "default"

    def __init__(self, domain, host):
        self.cached = CachedClient(domain, host)
        self.host = host
        self.profile = domain + "-observer.mesh-candidate.v1"
        self.validate = self.cached.codec
        self.watchers = 0

    async def snapshot(self, parameters):
        return await self.cached.request()

    async def proof(self, parameters):
        return await self.cached.request("proof", parameters)

    async def watch(self):
        self.watchers += 1
        try:
            yield Publication(await self.snapshot({}), "epoch_1", {"revision": 1})
            await asyncio.Event().wait()
        finally:
            self.watchers -= 1


class ReaderRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.getuid() != 0 and all(shutil.which(tool) for tool in ("ssh", "sshd", "ssh-keygen")),
                         "disposable SSH requires non-root user and OpenSSH tools")
    async def test_owned_ssh_rotates_with_new_channels_and_reaps_children(self):
        with tempfile.TemporaryDirectory(prefix=".mesh-rotation-", dir=Path.home()) as name:
            root = Path(name)
            publisher = CachedPublisher("agent", "remote")
            async def native(channel):
                request = json.loads(await channel.reader.readuntil(b"\n"))
                frame = publisher.cached.frame.copy()
                channel.writer.write(json.dumps(frame).encode() + b"\n")
                await channel.writer.drain()
                if request["operation"] == "watch":
                    await asyncio.Event().wait()
            owner = await IPCServer(root / "owner.sock", native).start()
            config = root / "sources.toml"
            config.write_text(f'version = 1\nhost = "remote"\n[sources.default]\ndomain = "agent"\nsocket = "{root / "owner.sock"}"\n')
            config.chmod(0o600)
            clients = []
            command = [sys.executable, "-m", "mesh_plus.cli", "bridge", "--source", "default",
                       "--stdio", "--config", str(config)]
            try:
                async with ssh_server(root, command, "default") as channel:
                    async def connect():
                        client = await Client.connect(await channel(), host="remote", source="default",
                                                      profile=publisher.profile, codec=publisher.validate)
                        clients.append(client)
                        return client
                    async def catalog():
                        return "sha256:" + "b" * 64
                    reader = Reader("agent", [Endpoint("remote", False, "sha256:" + "a" * 64, connect)],
                                    local_host="local", catalog_revision=await catalog(), catalog_check=catalog)
                    watch = reader.watch(proof_interval=.1)
                    revoked = False
                    try:
                        with patch("mesh_plus.client.ROTATION_HANDLES", 4):
                            for _ in range(30):
                                view = await asyncio.wait_for(anext(watch), 5)
                                host = view["mesh"]["hosts"][0]
                                if host["delivery"]["error"]:
                                    self.assertEqual(host["delivery"]["error"]["code"], "channel_rotation_required")
                                    revoked = True
                                if host["delivery"]["status"] == "ready" and host["delivery"]["epoch"] >= 3:
                                    break
                            self.assertTrue(revoked)
                            self.assertGreaterEqual(host["delivery"]["epoch"], 3)
                    finally:
                        await watch.aclose()
                    self.assertGreaterEqual(reader.inspect()["rotations"], 2)
                    self.assertEqual(reader.inspect()["activeConnections"], 0)
                    self.assertTrue(all(client.channel.process.returncode is not None for client in clients))
            finally:
                await owner.close()

    async def test_rotations_revoke_before_reproof_and_preserve_healthy_sibling(self):
        for domain in ("tmux", "agent"):
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                publishers, servers, clients = [], [], []
                endpoints = []
                for host in ("local", "remote"):
                    publisher = CachedPublisher(domain, host)
                    publishers.append(publisher)
                    path = root / (host + ".sock")
                    servers.append(await IPCServer(path, Bridge(publisher).serve).start())

                    async def connect(source=publisher, socket=path):
                        client = await Client.connect(await connect_ipc(socket), host=source.host,
                                                      source=source.source, profile=source.profile,
                                                      codec=source.validate)
                        clients.append(client)
                        # Exercise rotation of only one endpoint.
                        if source.host == "local":
                            client.rotation_due = lambda: False
                        return client

                    endpoints.append(Endpoint(host, host == "local",
                                              None if host == "local" else "sha256:" + "a" * 64, connect))

                async def catalog():
                    return "sha256:" + "b" * 64

                reader = Reader(domain, endpoints, local_host="local",
                                catalog_revision=await catalog(), catalog_check=catalog)
                watch = reader.watch(proof_interval=.1)
                guard = None
                revocations, baselines = set(), set()
                local_epoch = None
                try:
                    # Low threshold forces several real connection incarnations
                    # without spending hours at the production threshold.
                    with patch("mesh_plus.client.ROTATION_HANDLES", 5):
                        # Local bypass above applies to both Reader and admission.
                        for _ in range(80):
                            view = await asyncio.wait_for(anext(watch), 3)
                            if guard is None:
                                guard = ReadGuard(domain, view["mesh"]["requestId"])
                            guard.accept(view)
                            local, remote = view["mesh"]["hosts"]
                            if local["delivery"]["status"] == "ready":
                                if local_epoch is None:
                                    local_epoch = local["delivery"]["epoch"]
                                self.assertEqual(local["delivery"]["epoch"], local_epoch)
                            if remote["delivery"]["error"] is not None:
                                self.assertEqual(remote["delivery"]["error"]["code"], "channel_rotation_required")
                                epoch = remote["delivery"]["epoch"]
                                if epoch not in revocations:
                                    self.assertEqual(view["mesh"]["kind"], "resync")
                                    revocations.add(epoch)
                                self.assertFalse(any(row_host(domain, row) == "remote" for row in
                                                     current_sessions(view, view["mesh"]["reader"]["encodedAtMs"],
                                                                      view["mesh"]["reader"]["clock"])))
                                # Paused downstream cannot miss the revocation
                                # because a replacement overwrote its outcome.
                                await asyncio.sleep(.02)
                            if remote["delivery"]["status"] == "ready" and remote["delivery"]["epoch"] > 1:
                                epoch = remote["delivery"]["epoch"]
                                if epoch not in baselines:
                                    self.assertIn(epoch - 1, revocations)
                                    self.assertEqual(view["mesh"]["kind"], "resync")
                                    baselines.add(epoch)
                            if len(baselines) >= 3:
                                break
                        self.assertGreaterEqual(len(baselines), 3)
                finally:
                    await watch.aclose()
                    for server in servers:
                        await server.close()
                self.assertTrue(all(client.channel.closed for client in clients))
                self.assertTrue(all(client.reader_task.done() for client in clients))
                self.assertTrue(all(publisher.watchers == 0 for publisher in publishers))
                metrics = reader.inspect()
                self.assertEqual(metrics["activeConnections"], 0)
                self.assertEqual(metrics["connectionsOpened"], metrics["connectionsClosed"])
                self.assertGreaterEqual(metrics["rotations"], 3)
                self.assertEqual(metrics["cleanupFailures"], 0)
                self.assertFalse(metrics["partial"])
                self.assertGreater(metrics["operations"]["proofRequests"], 0)
                self.assertGreater(metrics["operations"]["snapshotRequests"], 0)
                self.assertGreater(metrics["receivedBytes"], 0)

    async def test_cancellation_while_rotation_revocation_is_pending_retires_channel(self):
        with tempfile.TemporaryDirectory() as name:
            publisher = CachedPublisher("tmux", "local")
            path = Path(name) / "mesh.sock"
            server = await IPCServer(path, Bridge(publisher).serve).start()
            async def connect():
                return await Client.connect(await connect_ipc(path), host="local", source="default",
                                            profile=publisher.profile, codec=publisher.validate)
            reader = Reader("tmux", [Endpoint("local", True, None, connect)], local_host="local")
            watch = reader.watch(proof_interval=.1)
            try:
                with patch("mesh_plus.client.ROTATION_HANDLES", 3):
                    await anext(watch)
                    await asyncio.wait_for(anext(watch), 2)
                    # Host reaches threshold while outer generator is suspended.
                    for _ in range(200):
                        if reader.inspect()["rotations"]:
                            break
                        await asyncio.sleep(.005)
                    self.assertEqual(reader.inspect()["rotations"], 1)
                    await watch.aclose()
                    self.assertEqual(reader.inspect()["connectionsOpened"], 1)
                    self.assertEqual(reader.inspect()["activeConnections"], 0)
            finally:
                await watch.aclose()
                await server.close()
            self.assertEqual(publisher.watchers, 0)
