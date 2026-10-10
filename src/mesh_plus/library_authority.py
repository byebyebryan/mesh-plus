"""Explicit same-package catalog reads; route reports retain the process writer.

One cancellable caller can own at most one filesystem job. A timed-out job
cannot enqueue replacements or deliver a later catalog. Source files and lock
waits are bounded; shutdown reports any filesystem job that has not retired.
"""

import asyncio
import concurrent.futures
import contextlib
import json
import os
import stat
import threading
import time

from .authority import RouteHealthStore, config_path, fcntl, load_config, route_health_path
from .authority_cli import _json_bytes
from .catalog import Catalog, MeshAuthority
from .protocol import check
from .transport import boottime_ms, within_deadline

MAX_SOURCE_BYTES = 4 * 1024 * 1024


def source_file(path):
    """Read bounded bytes from the same regular descriptor that was checked."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    try:
        node = os.fstat(fd)
        check(stat.S_ISREG(node.st_mode), "catalog_source_policy")
        check(node.st_size <= MAX_SOURCE_BYTES, "catalog_source_capacity")
        chunks = []
        size = 0
        while size <= MAX_SOURCE_BYTES:
            chunk = os.read(fd, min(65536, MAX_SOURCE_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        check(size <= MAX_SOURCE_BYTES, "catalog_source_capacity")
        return b"".join(chunks)
    finally:
        os.close(fd)


class _ReadStore(RouteHealthStore):
    def __init__(self, path, deadline):
        super().__init__(path)
        self.deadline = deadline

    def _read_unlocked(self):
        # Called under the canonical health lock; its parser consumes exactly
        # these checked bytes rather than opening the pathname a second time.
        return super()._read_unlocked(_source_bytes=source_file(self.path))

    @contextlib.contextmanager
    def _locked(self):
        # Use the canonical store's lock name, permissions and read method.
        # There is no new report writer or separate route-health history.
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_NONBLOCK, 0o600)
        try:
            check(stat.S_ISREG(os.fstat(fd).st_mode), "catalog_source_policy")
            os.fchmod(fd, 0o600)
            if self.path.exists():
                os.chmod(self.path, 0o600)
            check(fcntl is not None, "catalog_lock_unsupported")
            while True:
                check(boottime_ms() < self.deadline, "catalog_deadline")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(.01)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


class LibraryMeshAuthority(MeshAuthority):
    """Opt-in authority of the imported SDK, with the same catalog semantics.

The process authority remains the default SDK API and report writer. This
adapter is for an explicitly selected same-package service, never an arbitrary
executable replacement. Config/health inputs above four MiB fail explicitly.
"""

    def __init__(self, *, timeout_ms=5000):
        super().__init__()
        check(type(timeout_ms) is int and 1 <= timeout_ms <= 5000, "catalog_budget")
        self.timeout_ms = timeout_ms
        self.lock = threading.Lock()
        self.job = self.thread = None
        self.closed = False

    def _read(self, environ, deadline):
        raw = source_file(config_path(environ))
        config = load_config(environ=environ, _source_bytes=raw)
        health = _ReadStore(route_health_path(environ), deadline).load()
        # The canonical process encoder still owns stdout capacity and UTF-8
        # representation. Catalog admission retains the same pure validation.
        payload = json.loads(_json_bytes(config.with_health(health).to_dict()))
        check(boottime_ms() < deadline, "catalog_deadline")
        return Catalog(payload)

    async def load(self):
        deadline = boottime_ms() + self.timeout_ms
        with self.lock:
            check(not self.closed, "catalog_closed")
            check(self.job is None or self.job.done(), "catalog_busy")
            job = self.job = concurrent.futures.Future()
            job.set_running_or_notify_cancel()
            environ = dict(os.environ)

            def run():
                try:
                    job.set_result(self._read(environ, deadline))
                except BaseException as error:
                    job.set_exception(error)

            self.thread = threading.Thread(target=run, name="mesh-catalog-read", daemon=True)
            self.thread.start()
        future = asyncio.wrap_future(job)
        future.add_done_callback(lambda value: None if value.cancelled() else value.exception())
        # Cancelling the async wrapper cannot cancel an already running job.
        # It revokes this caller while the one bounded job retires independently.
        value = await within_deadline(future, deadline)
        check(not self.closed, "catalog_closed")
        return value

    def close(self, *, timeout=5):
        with self.lock:
            self.closed = True
            thread = self.thread
        if thread is not None:
            thread.join(timeout=timeout)
            check(not thread.is_alive(), "catalog_busy")
