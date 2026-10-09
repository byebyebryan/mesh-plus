"""Owned bounded line channels, same-user IPC and noninteractive SSH stdio."""

import asyncio
import contextlib
import os
import secrets
import shlex
import socket
import stat
import struct
import time
from pathlib import Path

from .protocol import MAX_CONTROL, MAX_MESSAGE, ProtocolError, check, decode, encode, validate


def boottime_ms():
    """Suspend-aware deadline clock; no wall-clock or remote-origin subtraction."""
    return int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1000)


class LineChannel:
    def __init__(self, reader, writer, incoming, *, process=None, io_timeout=5.0, reached_nonce=None):
        self.reader, self.writer, self.incoming = reader, writer, incoming
        self.outgoing = "server" if incoming == "client" else "client"
        self.process = process
        self.maximum = MAX_MESSAGE
        self.io_timeout = io_timeout
        self.lock = asyncio.Lock()
        self.closed = False
        self.stderr_tail = bytearray()
        self.reached_nonce = reached_nonce
        self.stderr_task = asyncio.create_task(self._stderr()) if process else None

    async def _stderr(self):
        while block := await self.process.stderr.read(4096):
            self.stderr_tail.extend(block)
            del self.stderr_tail[:-65536]

    async def receive(self):
        try:
            first = await self.reader.readexactly(1)
            started = boottime_ms()
            raw = first if first == b"\n" else first + await asyncio.wait_for(self.reader.readuntil(b"\n"), self.io_timeout)
            check(boottime_ms() - started <= int(self.io_timeout * 1000), "frame_deadline")
        except (asyncio.LimitOverrunError, ValueError) as error:
            raise ProtocolError("message_capacity") from error
        except asyncio.IncompleteReadError as error:
            if error.partial:
                raise ProtocolError("truncated_frame") from error
            raise EOFError("channel_closed") from error
        maximum = min(self.maximum, MAX_CONTROL) if self.incoming == "client" else self.maximum
        check(len(raw) <= maximum + 1 and b"\r" not in raw and b"\n" not in raw[:-1], "line_framing")
        return decode(raw[:-1], self.incoming, maximum), len(raw) - 1

    @property
    def reached(self):
        if not self.reached_nonce:
            return False
        return ("\x1eROFI_PLUS_REACHED_V1:" + self.reached_nonce + "\x1f\n").encode() in self.stderr_tail

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
            with contextlib.suppress(ProcessLookupError):
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


async def connect_ipc(path, *, timeout=2, maximum=MAX_MESSAGE):
    path = Path(path)
    check(path.is_absolute() and path.parent.resolve() == path.parent, "ipc_socket_path")
    parent = path.parent.lstat()
    check(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
          parent.st_mode & 0o077 == 0, "ipc_directory_policy")
    before = path.lstat()
    check(stat.S_ISSOCK(before.st_mode) and before.st_uid == os.getuid() and
          before.st_mode & 0o077 == 0, "ipc_socket_policy")
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(path, limit=maximum + 1), timeout)
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


async def subprocess_channel(argv, *, reached_nonce=None):
    """Local trusted argv only; never accept executable paths from wire metadata."""
    process = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE,
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                 limit=MAX_MESSAGE + 1)
    return LineChannel(process.stdout, process.stdin, "server", process=process, reached_nonce=reached_nonce)


def ssh_argv(destination, source_id, *, bridge="mesh-plus", executable="ssh", nonce=None,
             timeout_seconds=2, attempts=1):
    check(isinstance(destination, str) and bool(destination) and not destination.startswith("-") and
          not any(c.isspace() or ord(c) < 32 for c in destination), "ssh_destination")
    check(isinstance(source_id, str) and bool(source_id) and len(source_id) <= 128 and
          all(c.isascii() and (c.isalnum() or c in "_.-") for c in source_id), "source_id")
    check(bridge == "mesh-plus", "bridge_command")
    check(type(timeout_seconds) is int and 1 <= timeout_seconds <= 60 and type(attempts) is int and
          1 <= attempts <= 10, "ssh_policy")
    domain = [bridge, "bridge", "--source", source_id, "--stdio"]
    if nonce is None:
        command = shlex.join(domain)
    else:
        check(len(nonce) == 32 and all(c in "0123456789abcdef" for c in nonce), "reached_nonce")
        script = 'printf \'\\036ROFI_PLUS_REACHED_V1:%s\\037\\n\' "$1" >&2\nshift\nexec "$@"'
        command = shlex.join(["sh", "-c", script, "mesh-plus-reached", nonce, *domain])
    return [executable, "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "ClearAllForwardings=yes", "-o", "ForwardAgent=no", "-o", "RequestTTY=no",
            "-o", f"ConnectTimeout={timeout_seconds}", "-o", f"ConnectionAttempts={attempts}",
            "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
            "-o", "ControlMaster=no", "-o", "ControlPath=none", "--", destination, command]


async def connect_ssh(destination, source_id, *, executable="ssh", timeout_seconds=2, attempts=1):
    nonce = secrets.token_hex(16)
    return await subprocess_channel(ssh_argv(destination, source_id, executable=executable, nonce=nonce,
                                             timeout_seconds=timeout_seconds, attempts=attempts), reached_nonce=nonce)


class IPCServer:
    """Private same-user listener; refuses replacement of any existing pathname."""

    def __init__(self, path, handler, *, max_clients=32):
        self.path = Path(path)
        self.handler = handler
        self.max_clients = max_clients
        self.tasks = set()
        self.server = None
        self.inode = None
        self.closing = False

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
            self.server = await asyncio.start_unix_server(self._accept, sock=sock, limit=MAX_CONTROL + 1)
        except BaseException:
            sock.close()
            raise
        return self

    async def _accept(self, reader, writer):
        task = asyncio.current_task()
        channel = LineChannel(reader, writer, "client")
        if self.closing or len(self.tasks) >= self.max_clients or peer_uid(writer) != os.getuid():
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
        self.closing = True
        if self.server:
            self.server.close()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.server:
            await self.server.wait_closed()
        with contextlib.suppress(FileNotFoundError):
            if self.path.lstat().st_ino == self.inode:
                self.path.unlink()
