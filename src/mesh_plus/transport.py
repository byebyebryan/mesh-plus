"""Owned bounded line channels, same-user IPC and noninteractive SSH stdio."""

import asyncio
import contextlib
import fcntl
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


async def finish_owned(task):
    """Retire bounded owned IO despite repeated caller cancellation.

    Waiting does not cancel the task or leave a shield callback that reports an
    already observed IO failure. The operation's own IO budget remains in force.
    """
    cancelled = False
    while not task.done():
        try:
            await asyncio.wait({task})
        except asyncio.CancelledError:
            cancelled = True
    try:
        result = task.result()
    finally:
        # A raised task exception retains this frame in its traceback. Do not
        # make the completed task a back-reference to that same exception.
        task = None
    if cancelled:
        # The cancellation wins, so do not retain a possibly large result
        # graph in the traceback of the CancelledError propagated below.
        del result
        raise asyncio.CancelledError
    return result


def _observe_cancelled_task_errors(tasks):
    """Release tracebacks from owned tasks after their cancellation is observed."""
    for task in tasks:
        if task.done() and task.cancelled():
            with contextlib.suppress(asyncio.CancelledError):
                task.exception()


async def _finish_owned_tasks(tasks):
    """Join an already-cancelled owned task group despite caller cancellation."""
    tasks = tuple(tasks)
    joined = asyncio.gather(*tasks, return_exceptions=True)
    try:
        return await finish_owned(joined)
    except asyncio.CancelledError:
        # The joined result is intentionally discarded when caller
        # cancellation wins; clear it before the traceback captures this frame.
        joined = None
        raise
    finally:
        _observe_cancelled_task_errors(tasks)
        tasks = ()


class _ExpiryChecks:
    """One BOOTTIME recheck timer while this loop has pending operations."""

    def __init__(self, loop):
        self.loop = loop
        self.waiters = {}
        self.timer = None

    def schedule(self):
        delay = min(.1, max(0, (min(deadline for waiter, deadline in self.waiters.items() if not waiter.done()) - boottime_ms()) / 1000))
        self.timer = self.loop.call_later(delay, self.tick)

    def tick(self):
        self.timer = None
        now = boottime_ms()
        for waiter, deadline in tuple(self.waiters.items()):
            if deadline <= now and not waiter.done():
                waiter.set_result(None)
        if any(not waiter.done() for waiter in self.waiters):
            self.schedule()

    def add(self, waiter, deadline):
        earliest = min((value for pending, value in self.waiters.items() if not pending.done()),
                       default=deadline)
        self.waiters[waiter] = deadline
        if self.timer is None or deadline < earliest:
            if self.timer is not None:
                self.timer.cancel()
            self.schedule()

    def remove(self, waiter):
        self.waiters.pop(waiter)
        if not self.waiters:
            if self.timer is not None:
                self.timer.cancel()
            del self.loop._mesh_expiry_checks


async def _wait_until(task, deadline_ms):
    """Wait without cancelling the caller-owned task at an ordinary boundary."""
    if not task.done() and boottime_ms() < deadline_ms:
        loop = asyncio.get_running_loop()
        checks = getattr(loop, "_mesh_expiry_checks", None)
        if checks is None:
            checks = loop._mesh_expiry_checks = _ExpiryChecks(loop)
        expiry = loop.create_future()
        checks.add(expiry, deadline_ms)
        try:
            await asyncio.wait({task, expiry}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            checks.remove(expiry)
            expiry.cancel()
    return task.done() and boottime_ms() < deadline_ms


async def within_deadline(awaitable, deadline_ms):
    """Include queue/write/validation time and notice suspend-aware expiry."""
    task = asyncio.ensure_future(awaitable)
    try:
        if not await _wait_until(task, deadline_ms):
            raise TimeoutError("operation_deadline")
        return task.result()
    finally:
        try:
            if not task.done():
                task.cancel()
            await _finish_owned_tasks((task,))
        finally:
            # The child task may retain the original exception whose traceback
            # points back to this frame.
            task = None


class LineChannel:
    def __init__(self, reader, writer, incoming, *, process=None, io_timeout=2.0, reached_nonce=None, codec=None):
        self.reader, self.writer, self.incoming = reader, writer, incoming
        self.outgoing = "server" if incoming == "client" else "client"
        self.process = process
        self.codec = codec
        self.maximum = MAX_MESSAGE
        self.io_timeout = io_timeout
        self.lock = asyncio.Lock()
        self.closed = False
        self._metrics = {"receivedFrames": 0, "sentFrames": 0, "receivedBytes": 0, "sentBytes": 0}
        self._by_kind = {"received": {}, "sent": {}}
        self.stderr_tail = bytearray()
        self.reached_nonce = reached_nonce
        self._reached = False
        self.reached_count = 0
        self.reached_observed_at = None
        self.marker_pending = bytearray()
        self.read_job = None
        self.stderr_task = asyncio.create_task(self._stderr()) if process else None

    async def _stderr(self):
        while block := await self.process.stderr.read(4096):
            self._stderr_block(block)
        self.stderr_tail.extend(self.marker_pending)
        self.marker_pending.clear()
        del self.stderr_tail[:-65536]

    def _stderr_block(self, block):
        if not self.reached_nonce:
            self.stderr_tail.extend(block)
        else:
            marker = ("\x1eROFI_PLUS_REACHED_V1:" + self.reached_nonce + "\x1f\n").encode()
            self.marker_pending.extend(block)
            while (position := self.marker_pending.find(marker)) >= 0:
                self.stderr_tail.extend(self.marker_pending[:position])
                del self.marker_pending[:position + len(marker)]
                self.reached_count = min(2, self.reached_count + 1)
                if self.reached_observed_at is None:
                    self.reached_observed_at = int(time.time() * 1000)
            # Keep only a possible split marker, separately from diagnostics.
            safe = max(0, len(self.marker_pending) - len(marker) + 1)
            self.stderr_tail.extend(self.marker_pending[:safe])
            del self.marker_pending[:safe]
            self._reached = self.reached_count == 1
        del self.stderr_tail[:-65536]

    async def receive(self):
        check(self.read_job is None, "concurrent_read")
        read_job = self.read_job = asyncio.create_task(self._receive())
        try:
            return await read_job
        except asyncio.CancelledError:
            if self.closed:
                raise EOFError("channel_closed") from None
            raise
        finally:
            self.read_job = None
            try:
                _observe_cancelled_task_errors((read_job,))
            finally:
                # The child error can point back to this coroutine's frame.
                read_job = None

    async def _receive(self):
        try:
            first = await self.reader.readexactly(1)
            started = boottime_ms()
            raw = first if first == b"\n" else first + await asyncio.wait_for(self.reader.readuntil(b"\n"), self.io_timeout)
            check(boottime_ms() - started <= int(self.io_timeout * 1000), "frame_deadline")
        except ProtocolError:
            raise
        except (asyncio.LimitOverrunError, ValueError) as error:
            raise ProtocolError("message_capacity") from error
        except asyncio.IncompleteReadError as error:
            if error.partial:
                raise ProtocolError("truncated_frame") from error
            raise EOFError("channel_closed") from error
        maximum = min(self.maximum, MAX_CONTROL) if self.incoming == "client" else self.maximum
        check(len(raw) <= maximum + 1 and b"\r" not in raw and b"\n" not in raw[:-1], "line_framing")
        value = (decode(raw[:-1], self.incoming, maximum) if self.codec is None else
                 self.codec.decode(raw[:-1], self.incoming, maximum))
        check(self.reached_count <= 1, "duplicate_reached_marker")
        check(boottime_ms() - started <= int(self.io_timeout * 1000), "frame_deadline")
        self._metrics["receivedFrames"] += 1
        self._metrics["receivedBytes"] += len(raw)
        self._count_kind("received", value["kind"], len(raw))
        return value, len(raw) - 1

    def inspect(self):
        """Completed application frames including LF; excludes encryption and failed writes."""
        return {**self._metrics, "closed": self.closed, "byteScope": "completed-json-lines",
                "byKind": {direction: {kind: counts.copy() for kind, counts in kinds.items()}
                           for direction, kinds in self._by_kind.items()}}

    def _count_kind(self, direction, kind, size):
        # Kinds come only from validated protocol frames, never producer keys.
        counts = self._by_kind[direction].setdefault(kind, {"frames": 0, "bytes": 0})
        counts["frames"] += 1
        counts["bytes"] += size

    @property
    def reached(self):
        return self._reached

    async def send(self, value):
        raw = None
        try:
            if self.codec is None:
                raw = encode(value)
                validate(value, self.outgoing, len(raw), self.maximum)
            else:
                raw = self.codec.encode(value)
                self.codec.validate(value, self.outgoing, len(raw), self.maximum)
            async with self.lock:
                check(not self.closed, "channel_closed")
                self.writer.write(raw + b"\n")
                started = boottime_ms()
                await asyncio.wait_for(self.writer.drain(), self.io_timeout)
                check(boottime_ms() - started <= int(self.io_timeout * 1000), "frame_deadline")
                self._metrics["sentFrames"] += 1
                self._metrics["sentBytes"] += len(raw) + 1
                self._count_kind("sent", value["kind"], len(raw) + 1)
            return len(raw)
        finally:
            # A stored stream error can retain the send traceback. These
            # temporary caller/body references are no longer in use on exit.
            value = raw = None

    async def close(self):
        if self.closed:
            return
        self.closed = True
        if self.read_job:
            read_job = self.read_job
            read_job.cancel()
            await _finish_owned_tasks((read_job,))
        drain = None
        if self.process:
            async def discard_stdout():
                while await self.reader.read(65536):
                    pass
            drain = asyncio.create_task(discard_stdout())
        self.writer.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.writer.wait_closed(), 1)
        if self.process and self.process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 1)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    self.process.kill()
                await asyncio.wait_for(self.process.wait(), 1)
        if drain:
            try:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(drain, 1)
            finally:
                _observe_cancelled_task_errors((drain,))
        if self.stderr_task:
            stderr_task = self.stderr_task
            stderr_task.cancel()
            try:
                with contextlib.suppress(asyncio.CancelledError):
                    await stderr_task
            finally:
                _observe_cancelled_task_errors((stderr_task,))


def peer_uid(writer):
    peer = writer.get_extra_info("socket")
    check(peer is not None, "ipc_peer_credentials")
    return struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]


async def connect_ipc(path, *, timeout=2, maximum=MAX_MESSAGE, codec=None):
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
    channel = LineChannel(reader, writer, "server", codec=codec)
    channel.maximum = maximum
    return channel


async def subprocess_channel(argv, *, reached_nonce=None, codec=None):
    """Local trusted argv only; never accept executable paths from wire metadata."""
    process = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.PIPE,
                                                 stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                 limit=MAX_MESSAGE + 1)
    return LineChannel(process.stdout, process.stdin, "server", process=process, reached_nonce=reached_nonce, codec=codec)


def ssh_argv(destination, source_id, *, bridge="mesh-plus", executable="ssh", nonce=None,
             timeout_seconds=2, attempts=1, sync=False):
    check(isinstance(destination, str) and bool(destination) and not destination.startswith("-") and
          not any(c.isspace() or ord(c) < 32 for c in destination), "ssh_destination")
    check(isinstance(source_id, str) and bool(source_id) and len(source_id) <= 128 and
          all(c.isascii() and (c.isalnum() or c in "_.-") for c in source_id), "source_id")
    check(bridge == "mesh-plus", "bridge_command")
    check(type(sync) is bool, "bridge_command")
    check(type(timeout_seconds) is int and 1 <= timeout_seconds <= 60 and type(attempts) is int and
          1 <= attempts <= 10, "ssh_policy")
    domain = [bridge, "sync-bridge" if sync else "bridge", "--source", source_id, "--stdio"]
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
    """Private leased listener; recovers only a proved abandoned owned socket."""

    def __init__(self, path, handler, *, max_clients=32, codec=None):
        self.path = Path(path)
        self.handler = handler
        self.max_clients = max_clients
        self.codec = codec
        self.tasks = set()
        self._accept_tasks = set()
        self.server = None
        self.inode = None
        self.closing = False
        self.lease = None
        self.closed = False

    async def start(self):
        check(self.server is None and self.lease is None and not self.closing, "ipc_server_state")
        check(self.path.is_absolute() and self.path.parent.resolve() == self.path.parent and
              len(os.fsencode(self.path)) < 108, "ipc_socket_path")
        parent = self.path.parent.lstat()
        check(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
              parent.st_mode & 0o077 == 0, "ipc_directory_policy")
        try:
            self.lease = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            node = os.fstat(self.lease)
            check(stat.S_ISREG(node.st_mode) and node.st_uid == os.getuid() and node.st_mode & 0o077 == 0, "ipc_lease_policy")
            try:
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ProtocolError("ipc_publisher_running") from error
            if self.path.exists() or self.path.is_symlink():
                node = self.path.lstat()
                check(stat.S_ISSOCK(node.st_mode) and node.st_uid == os.getuid() and node.st_mode & 0o077 == 0,
                      "ipc_path_exists")
                try:
                    _reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(self.path), .1)
                except ConnectionRefusedError:
                    current = self.path.lstat()
                    check((current.st_dev, current.st_ino) == (node.st_dev, node.st_ino), "ipc_socket_changed")
                    self.path.unlink()
                else:
                    writer.close()
                    await writer.wait_closed()
                    raise ProtocolError("ipc_publisher_running")
        except BaseException:
            if self.lease is not None:
                os.close(self.lease)
                self.lease = None
            raise
        # Bind synchronously with mode restricted before the event loop admits peers.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self.path))
            self.inode = self.path.lstat().st_ino
            os.chmod(self.path, 0o600)
            sock.listen(self.max_clients)
            sock.setblocking(False)
            self.server = await asyncio.start_unix_server(self._accept, sock=sock, limit=MAX_CONTROL + 1)
        except BaseException:
            sock.close()
            with contextlib.suppress(FileNotFoundError):
                if self.path.lstat().st_ino == self.inode:
                    self.path.unlink()
            if self.lease is not None:
                os.close(self.lease)
                self.lease = None
            raise
        return self

    async def _accept(self, reader, writer):
        task = asyncio.current_task()
        self._accept_tasks.add(task)
        channel = None
        try:
            channel = LineChannel(reader, writer, "client", codec=self.codec)
            if self.closing or len(self.tasks) >= self.max_clients or peer_uid(writer) != os.getuid():
                return
            self.tasks.add(task)
            try:
                await self.handler(channel)
            except (EOFError, ConnectionError, ProtocolError, TimeoutError):
                pass
        finally:
            try:
                if channel is not None:
                    await channel.close()
            finally:
                self.tasks.discard(task)
                self._accept_tasks.discard(task)

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.closing = True
        server = self.server
        handler = self.handler
        if server is not None:
            server.close()
        tasks = tuple(self._accept_tasks)
        for task in tasks:
            task.cancel()
        cancelled = False
        try:
            await _finish_owned_tasks(tasks)
        except asyncio.CancelledError:
            cancelled = True
        finally:
            tasks = ()
        if server is not None:
            wait_task = asyncio.create_task(server.wait_closed())
            try:
                try:
                    await _finish_owned_tasks((wait_task,))
                except asyncio.CancelledError:
                    cancelled = True
                wait_task.result()
            finally:
                wait_task = None
        while self._accept_tasks:
            tasks = tuple(self._accept_tasks)
            for task in tasks:
                task.cancel()
            try:
                await _finish_owned_tasks(tasks)
            except asyncio.CancelledError:
                cancelled = True
            finally:
                tasks = ()
        if self.server is server:
            self.server = None
        if self.handler is handler:
            self.handler = None
        with contextlib.suppress(FileNotFoundError):
            if self.path.lstat().st_ino == self.inode:
                self.path.unlink()
        if self.lease is not None:
            os.close(self.lease)
            self.lease = None
        if cancelled:
            server = handler = wait_task = tasks = task = None
            raise asyncio.CancelledError
