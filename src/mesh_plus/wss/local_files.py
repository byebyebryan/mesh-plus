"""Owned local-file jobs; caller deadlines do not interrupt kernel file reads."""

import asyncio
import concurrent.futures
import threading

from mesh_plus.protocol import check
from mesh_plus.transport import boottime_ms, within_deadline


class LocalReadOwner:
    """One outstanding daemon job, with explicit unretired-job reporting.

    Configuration must be on an owner-controlled local filesystem. Closing
    revokes all callers; an uninterruptible read can outlive the close budget.
    No late value is delivered and no replacement job starts while it runs.
    """

    def __init__(self):
        self.lock = asyncio.Lock()
        self.job = self.thread = None
        self.closed = False

    async def read(self, capture, *, timeout_ms=5000):
        deadline = boottime_ms() + timeout_ms

        async def execute():
            async with self.lock:
                check(not self.closed, "wss_configuration_closed")
                check(self.job is None or self.job.done(), "wss_configuration_busy")
                job = self.job = concurrent.futures.Future()
                job.set_running_or_notify_cancel()

                def run():
                    try:
                        job.set_result(capture())
                    except BaseException as error:
                        job.set_exception(error)

                self.thread = threading.Thread(target=run, name="mesh-wss-config", daemon=True)
                self.thread.start()
                future = asyncio.wrap_future(job)
                future.add_done_callback(lambda value: None if value.cancelled() else value.exception())
                value = await future
                check(not self.closed, "wss_configuration_closed")
                return value

        return await within_deadline(execute(), deadline)

    def close(self, *, timeout=5):
        self.closed = True
        if self.thread is not None:
            self.thread.join(timeout=timeout)
            check(not self.thread.is_alive(), "wss_configuration_busy")
