"""Owned bounded line channels, same-user IPC and noninteractive SSH stdio."""

import asyncio
import contextlib
import os
import shlex
import socket
import stat
import struct
import time
from pathlib import Path

from .protocol import MAX_MESSAGE, ProtocolError, check, decode, encode, validate


def boottime_ms():
    """Suspend-aware deadline clock; no wall-clock or remote-origin subtraction."""
    return int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000)


class LineChannel:
    def __init__(self, reader, writer, incoming, *, process=None, io_timeout=5.0):
        self.reader, self.writer, self.incoming = reader, writer, incoming
        self.outgoing = "server" if incoming == "client" else "client"
        self.process = process
        self.maximum = MAX_MESSAGE
        self.io_timeout = io_timeout
        self.lock = asyncio.Lock()
        self.closed = False
        self.stderr_tail = bytearray()
        self.stderr_task = asyncio.create_task(self._stderr()) if process else None

    async def _stderr(self):
        while block := await self.process.stderr.read(4096):
            self.stderr_tail.extend(block)
            del self.stderr_tail[:-65536]

    async def receive(self):
        try:
            raw = await self.reader.readuntil(b"\n")
        except (asyncio.LimitOverrunError, ValueError) as error:
            raise ProtocolError("message_capacity") from error
        except asyncio.IncompleteReadError as error:
            if error.partial:
                raise ProtocolError("truncated_frame") from error
            raise EOFError("channel_closed") from error
        check(len(raw) <= self.maximum + 1 and b"\r" not in raw and b"\n" not in raw[:-1], "line_framing")
        return decode(raw[:-1], self.incoming, self.maximum), len(raw) - 1

    async def send(self, value):
        raw = encode(value)
        validate(value, self.outgoing, len(raw), self.maximum)
        async with self.lock:
            check(not self.closed, "channel_closed")
            self.writer.write(raw + b"\n")
            await asyncio.wait_for(self.writer.drain(), self.io_timeout)
        return len(raw)

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.writer.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.writer.wait_closed(), 1)
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 1)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self.stderr_task:
            self.stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.stderr_task


def peer_uid(writer):
    peer = writer.get_extra_info("socket")
    check(peer is not None, "ipc_peer_credentials")
    return struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]


async def connect_ipc(path, *, timeout=2):
    path = Path(path)
    before = path.lstat()
    check(stat.S_ISSOCK(before.st_mode) and before.st_uid == os.getuid() and
          before.st_mode & 0o077 == 0, "ipc_socket_policy")
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(path, limit=MAX_MESSAGE + 1), timeout)
    try:
        after = path.lstat()
        check((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), "ipc_socket_changed")
        check(peer_uid(writer) == os.getuid(), "ipc_peer_credentials")
    except BaseException:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        raise
    return LineChannel(reader, writer, "server")


async def subprocess_channel(argv):
    """Local trusted argv only; never accept executable paths from wire metadata."""
    process = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE,
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                 limit=MAX_MESSAGE + 1)
    return LineChannel(process.stdout, process.stdin, "server", process=process)


def ssh_argv(destination, source_id, *, bridge="mesh-plus", executable="ssh"):
    check(isinstance(destination, str) and bool(destination) and not destination.startswith("-") and
          not any(c.isspace() or ord(c) < 32 for c in destination), "ssh_destination")
    check(isinstance(source_id, str) and bool(source_id) and len(source_id) <= 128 and
          all(c.isascii() and (c.isalnum() or c in "_.-") for c in source_id), "source_id")
    check(bridge == "mesh-plus", "bridge_command")
    command = shlex.join([bridge, "bridge", "--source", source_id, "--stdio"])
    return [executable, "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ClearAllForwardings=yes", "-o", "ForwardAgent=no", "-o", "RequestTTY=no",
            "-o", "ConnectTimeout=2", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
            "-o", "ControlMaster=no", "-o", "ControlPath=none", "--", destination, command]


async def connect_ssh(destination, source_id):
    return await subprocess_channel(ssh_argv(destination, source_id))


class IPCServer:
    """Private same-user listener; refuses replacement of any existing pathname."""

    def __init__(self, path, handler, *, max_clients=32):
        self.path = Path(path)
        self.handler = handler
        self.max_clients = max_clients
        self.tasks = set()
        self.server = None
        self.inode = None

    async def start(self):
        parent = self.path.parent.lstat()
        check(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
              parent.st_mode & 0o077 == 0, "ipc_directory_policy")
        check(not self.path.exists() and not self.path.is_symlink(), "ipc_path_exists")
        # Bind synchronously with mode restricted before the event loop admits peers.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self.path))
            os.chmod(self.path, 0o600)
            sock.listen(self.max_clients)
            sock.setblocking(False)
            self.inode = self.path.lstat().st_ino
            self.server = await asyncio.start_unix_server(self._accept, sock=sock, limit=MAX_MESSAGE + 1)
        except BaseException:
            sock.close()
            raise
        return self

    async def _accept(self, reader, writer):
        task = asyncio.current_task()
        channel = LineChannel(reader, writer, "client")
        if len(self.tasks) >= self.max_clients or peer_uid(writer) != os.getuid():
            await channel.close()
            return
        self.tasks.add(task)
        try:
            await self.handler(channel)
        except (EOFError, ConnectionError, ProtocolError, TimeoutError):
            pass
        finally:
            await channel.close()
            self.tasks.discard(task)

    async def close(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        with contextlib.suppress(FileNotFoundError):
            if self.path.lstat().st_ino == self.inode:
                self.path.unlink()
