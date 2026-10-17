"""Opt-in prepaid IPC/fixed-stdio ingress with immutable first-byte provenance."""

import asyncio
import copy
import fcntl
import os
import socket
import threading
import weakref

from ..evidence import clock_domain
from ..protocol import ProtocolError, check
from ..transport import LineChannel, boottime_ms, finish_owned, within_deadline
from ._boundary import _retire_error, admission_boundary, async_admission_boundary
from .budget import AllocationLedger
from .control_json import parse_control

_MINT = object()
_CAPACITY = 65536
_BASE_HEAP = 196608  # full ring, 256 physical range slots, controls/tasks/views


async def _ready(owner, fd, *, write=False):
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    owner._check()
    owner._waiters.add(future)
    add, remove = (loop.add_writer, loop.remove_writer) if write else (loop.add_reader, loop.remove_reader)
    def wake():
        if not future.done():
            future.set_result(None)
    try:
        add(fd, wake)
        await future
    finally:
        if not owner._closed:
            remove(fd)
        owner._waiters.discard(future)


class _NoRead:
    async def readexactly(self, _count):
        raise ProtocolError("sync_control_provenance")


class _Writer:
    def __init__(self, owner):
        self._owner = weakref.ref(owner)
        self._pending = None
        self._limits = (16384, 65536)

    @property
    def transport(self):
        return self

    def _live(self):
        owner = self._owner()
        check(owner is not None and not owner._closed, "sync_control_retired")
        owner._check()
        return owner

    def get_write_buffer_limits(self):
        return self._limits

    def set_write_buffer_limits(self, *, high, low):
        self._limits = low, high

    def get_write_buffer_size(self):
        return 0 if self._pending is None else len(self._pending)

    def write(self, value):
        self._live()
        check(self._pending is None and len(value) <= 65536, "sync_control_output")
        self._pending = memoryview(value)
        self._flush()

    def _flush(self):
        owner = self._live()
        while self._pending is not None:
            try:
                count = os.write(owner._write_fd, self._pending)
            except BlockingIOError:
                return
            check(count > 0, "sync_control_output")
            owner._output._metrics["physicalSentBytes"] += count
            self._pending = self._pending[count:] if count < len(self._pending) else None

    async def drain(self):
        owner = self._live()
        owner._bind_loop()
        task = asyncio.current_task()
        owner._io_jobs.add(task)
        try:
            while self._pending is not None:
                await _ready(owner, owner._write_fd, write=True)
                self._flush()
            self._live()
        finally:
            owner._io_jobs.discard(task)
            if owner._closed:
                owner._drop_storage()

    def close(self):
        self._pending = None
        owner = self._owner()
        if owner is not None:
            owner._begin_close()

    async def wait_closed(self):
        owner = self._owner()
        if owner is not None:
            await owner.aclose()


class _Header:
    def __init__(self, frame):
        self._frame = weakref.ref(frame)

    def _live(self):
        frame = self._frame()
        check(frame is not None, "sync_control_retired")
        frame._check()
        return frame

    @property
    @admission_boundary
    def materialization_bytes(self):
        return self._live()._copy_bytes

    @admission_boundary
    def materialize(self):
        # Caller prepays/retains the advertised independent detached-copy lease.
        frame = self._live()
        owner, original = frame._pin_copy()
        value = failure = None
        try:
            value = copy.deepcopy(original)
            frame._check()  # retirement during copy cannot publish a late DTO
        except BaseException as error:
            failure = _retire_error(error)
            value = None
        finally:
            original = None
            owner._end_copy(frame)
            owner = frame = None
        if failure is not None:
            code, signal, public = failure
            if signal is not None:
                raise signal
            raise public if public is not None else ProtocolError(code)
        return value


class StampedControlFrame:
    def __init__(self, owner, start, stop, floor, value, credit, *, _mint=None):
        check(_mint is _MINT, "sync_control_provenance")
        self._owner, self._start, self._stop, self._floor = weakref.ref(owner), start, stop, floor
        self._value, self._credit = value, credit
        self._retired = self._copying = self._retire_pending = False
        self._copy_bytes = (stop - start) * 24 + 65536
        self._header = _Header(self)

    def _check(self):
        owner = None if self._owner is None else self._owner()
        check(owner is not None, "sync_control_retired")
        with owner._copy_lock:
            check(not self._retired and not owner._closed and self._value is not None,
                  "sync_control_retired")
            owner._check()

    def _pin_copy(self):
        owner = None if self._owner is None else self._owner()
        check(owner is not None, "sync_control_retired")
        with owner._copy_lock:
            self._check()
            check(not self._copying, "sync_control_copy_busy")
            self._copying = True
            owner._copies += 1
            return owner, self._value

    @property
    @admission_boundary
    def start(self):
        self._check()
        return self._start

    @property
    @admission_boundary
    def stop(self):
        self._check()
        return self._stop

    @property
    @admission_boundary
    def first_byte_ms(self):
        self._check()
        return self._floor

    @property
    @admission_boundary
    def header(self):
        self._check()
        return self._header

    def close(self):
        owner = None if self._owner is None else self._owner()
        if owner is not None:
            with owner._copy_lock:
                self._retired = True
                if self._copying or self._retire_pending:
                    return
                self._retire_pending = True
            owner._on_loop(owner._retire_frame, self)


class SyncControlCarrier:
    def __init__(self, read_fd, write_fd, ledger, credit, *, _mint=None):
        check(_mint is _MINT, "sync_control_provenance")
        self._read_fd, self._write_fd, self._ledger, self._credit = read_fd, write_fd, ledger, credit
        self._closed, self._close_task, self._read_task = False, None, None
        self._data, self._ranges = bytearray(_CAPACITY), [[0, 0, 0] for _ in range(256)]
        self._count = self._cursor = self._end = self._low = 0
        self._frames, self._space = {}, asyncio.Event()
        self._waiters = set()
        self._io_jobs = set()
        self._copy_lock, self._copies = threading.RLock(), 0
        self._copy_idle, self._io_retired = asyncio.Event(), False
        self._copy_idle.set()
        try:
            self._loop, self._thread = asyncio.get_running_loop(), threading.get_ident()
        except RuntimeError:
            self._loop = self._thread = None
        self._scope, self._last_floor = clock_domain(), -1
        self._output = LineChannel(_NoRead(), _Writer(self), "client")
        self._output._metrics.update(physicalReceivedBytes=0, physicalSentBytes=0)

    def _check(self):
        with self._copy_lock:
            check(not self._closed, "sync_control_retired")
            now = boottime_ms()
            if (type(now) is not int or now < 0 or now < self._last_floor or
                    clock_domain() != self._scope):
                self._begin_close()
                raise ProtocolError("sync_control_provenance")
            self._last_floor = now

    def _bind_loop(self):
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop, self._thread = loop, threading.get_ident()
        check(self._loop is loop, "sync_control_owner")

    def _on_loop(self, callback, *args):
        if self._loop is not None and threading.get_ident() != self._thread:
            self._loop.call_soon_threadsafe(callback, *args)
        else:
            callback(*args)

    def _end_copy(self, frame):
        # One pending completion per frame; _copying remains true until this
        # owner-loop callback, so worker loops cannot queue unbounded history.
        self._on_loop(self._complete_copy, frame)

    def _complete_copy(self, frame):
        with self._copy_lock:
            frame._copying = False
            self._copies -= 1
        if frame._retired:
            self._retire_frame(frame)
        if not self._copies:
            self._copy_idle.set()
        if self._closed:
            self._drop_storage()

    def _retire_frame(self, frame):
        with self._copy_lock:
            if not frame._retired or frame._copying or frame._credit is None:
                return
            frame._owner = frame._value = None
            credit, frame._credit = frame._credit, None
            self._frames.pop(id(frame), None)
        self._retire_ranges()
        self._space.set()
        credit.close()

    @property
    @admission_boundary
    def output_channel(self):
        self._check()
        return self._output

    def _retire_ranges(self):
        self._low = min((frame._start for frame in self._frames.values()), default=self._cursor)
        drop = 0
        while drop < self._count and self._ranges[drop][1] <= self._low:
            drop += 1
        if drop:
            for index in range(self._count - drop):
                for field in range(3):
                    self._ranges[index][field] = self._ranges[index + drop][field]
            self._count -= drop
        if self._count:
            self._ranges[0][0] = max(self._ranges[0][0], self._low)

    def _coalesce(self):
        if self._count == 256:
            self._ranges[0][1] = self._ranges[1][1]
            self._ranges[0][2] = min(self._ranges[0][2], self._ranges[1][2])
            for index in range(1, 255):
                for field in range(3):
                    self._ranges[index][field] = self._ranges[index + 1][field]
            self._count = 255

    async def _fill(self, deadline):
        while True:
            self._check()
            self._retire_ranges()
            capacity = _CAPACITY - (self._end - self._low)
            if capacity == 0:
                self._space.clear()
                await within_deadline(self._space.wait(), deadline)
                continue
            self._coalesce()  # never allocate a 257th range, even temporarily
            check(clock_domain() == self._scope, "sync_control_provenance")
            index = self._end % _CAPACITY
            size = min(4096, capacity, _CAPACITY - index)
            view = memoryview(self._data)[index:index + size]
            buffers = (view,)
            try:
                # No suspension/parser/dispatcher between floor and first read.
                with self._copy_lock:
                    self._check()
                    floor = boottime_ms()
                    check(type(floor) is int and floor >= self._last_floor and floor >= 0 and floor < deadline,
                          "sync_control_provenance")
                    self._last_floor = floor
                    count = os.readv(self._read_fd, buffers)
            except BlockingIOError:
                count = None
            finally:
                view = buffers = None
            if count is None:
                await within_deadline(_ready(self, self._read_fd), deadline)
                continue
            if count == 0:
                check(self._end == self._cursor, "sync_control_truncated")
                raise EOFError("channel_closed")
            self._output._metrics["physicalReceivedBytes"] += count
            check(self._end + count < 2**64, "sync_control_provenance")
            check(clock_domain() == self._scope, "sync_control_provenance")
            span = self._ranges[self._count]
            span[0], span[1], span[2] = self._end, self._end + count, floor
            self._count += 1
            self._end += count
            return

    @async_admission_boundary
    async def receive_control(self, *, maximum_bytes, deadline_ms):
        check(not self._closed, "sync_control_retired")
        self._bind_loop()
        check(type(maximum_bytes) is int and 0 < maximum_bytes <= _CAPACITY and
              type(deadline_ms) is int and boottime_ms() < deadline_ms, "sync_control_limit")
        check(self._read_task is None, "sync_control_concurrent_read")
        self._read_task = asyncio.current_task()
        credit = value = frame = None
        try:
            self._check()
            while len(self._frames) == 2:
                self._space.clear()
                await within_deadline(self._space.wait(), deadline_ms)
                self._check()
            scan = self._cursor
            while True:
                while scan < self._end and self._data[scan % _CAPACITY] != 10:
                    scan += 1
                check(scan - self._cursor < maximum_bytes, "sync_control_capacity")
                if scan < self._end:
                    break
                await self._fill(deadline_ms)
            stop = scan + 1
            floor = next((span[2] for span in self._ranges[:self._count]
                          if span[0] <= self._cursor < span[1]), None)
            check(floor is not None, "sync_control_provenance")
            credit = self._ledger.reserve((stop - self._cursor) * 40 + 131072)
            value = parse_control(self._data, self._cursor, scan)
            self._check()
            check(boottime_ms() < deadline_ms, "sync_control_deadline")
            frame = StampedControlFrame(self, self._cursor, stop, floor, value, credit, _mint=_MINT)
            self._frames[id(frame)] = frame
            self._cursor = stop
            self._output._metrics["receivedFrames"] += 1
            self._output._metrics["receivedBytes"] += stop - frame._start
            credit = value = None
            return frame
        except BaseException as error:
            code, signal, _ = _retire_error(error)
            value = frame = None
            self._begin_close()
            if signal is not None:
                raise signal
            raise ProtocolError(code) from None
        finally:
            value = frame = None
            if credit is not None:
                credit.close()
            self._read_task = None
            if self._closed:
                self._drop_storage()

    def _begin_close(self):
        with self._copy_lock:
            if self._closed:
                return
            self._closed = self._output.closed = True
        self._on_loop(self._close_io)

    def _close_io(self):
        if self._io_retired:
            return
        for frame in tuple(self._frames.values()):
            frame.close()
        self._space.set()
        self._output.writer._pending = None
        loop = self._loop
        for waiter in tuple(self._waiters):
            if not waiter.done():
                waiter.set_result(None)
        for fd in {self._read_fd, self._write_fd}:
            if loop is not None:
                loop.remove_reader(fd)
                loop.remove_writer(fd)
            os.close(fd)
        self._read_fd = self._write_fd = -1
        self._io_retired = True
        task = self._read_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        self._drop_storage()

    async def aclose(self):
        self._bind_loop()
        self._begin_close()
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await finish_owned(self._close_task)

    async def _close(self):
        if self._read_task is not None:
            await asyncio.gather(self._read_task, return_exceptions=True)
        if self._io_jobs:
            await asyncio.gather(*tuple(self._io_jobs), return_exceptions=True)
        while self._copies:
            self._copy_idle.clear()
            await self._copy_idle.wait()
        self._drop_storage()

    def _drop_storage(self):
        if not self._io_retired or self._read_task is not None or self._io_jobs or self._copies:
            return
        self._data = self._ranges = self._scope = None
        self._waiters.clear()
        if self._credit is not None:
            self._credit.close()
        self._ledger = self._credit = None


def _validate_ledger(ledger):
    check(type(ledger) is AllocationLedger and ledger.maximum <= 67108864 and
          ledger.encoded_maximum <= 33554432, "sync_control_owner")


def _make(read_fd, write_fd, ledger):
    credit = None
    try:
        credit = ledger.reserve(_BASE_HEAP, encoded=_CAPACITY)
        os.set_blocking(read_fd, False)
        os.set_blocking(write_fd, False)
        return SyncControlCarrier(read_fd, write_fd, ledger, credit, _mint=_MINT)
    except BaseException as error:
        code, signal, _ = _retire_error(error)
        for fd in {read_fd, write_fd}:
            os.close(fd)
        if credit is not None:
            credit.close()
        if signal is not None:
            raise signal
        raise ProtocolError(code) from None


@admission_boundary
def control_carrier_from_ipc(sock, *, ledger):
    _validate_ledger(ledger)
    check(type(sock) is socket.socket and sock.family == socket.AF_UNIX and
          sock.type & socket.SOCK_STREAM and sock.fileno() >= 0, "sync_control_socket")
    sock.getpeername()  # argument validation only; authentication is caller-owned
    fd = sock.detach()
    return _make(fd, fd, ledger)


@admission_boundary
def control_carrier_from_stdio(read_fd, write_fd, *, ledger):
    _validate_ledger(ledger)
    check(type(read_fd) is int and read_fd >= 0 and type(write_fd) is int and write_fd >= 0,
          "sync_control_fd")
    read_flags, write_flags = fcntl.fcntl(read_fd, fcntl.F_GETFL), fcntl.fcntl(write_fd, fcntl.F_GETFL)
    check(read_flags & os.O_ACCMODE != os.O_WRONLY and write_flags & os.O_ACCMODE != os.O_RDONLY,
          "sync_control_fd")
    return _make(read_fd, write_fd, ledger)
