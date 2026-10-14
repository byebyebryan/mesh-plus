"""Owned expiry checks preserve BOOTTIME and pending subscription ownership."""

import asyncio
import unittest
from unittest.mock import patch

from mesh_plus.transport import _wait_until, boottime_ms, within_deadline


class DeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_waiter_does_not_hide_new_earlier_deadline(self):
        loop = asyncio.get_running_loop()
        now = [1000]
        pending = [loop.create_future() for _ in range(3)]
        with patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0]):
            jobs = [asyncio.create_task(_wait_until(task, deadline))
                    for task, deadline in zip(pending[:2], (1100, 5000))]
            await asyncio.sleep(0)
            checks = loop._mesh_expiry_checks
            checks.timer.cancel()
            now[0] = 1100
            checks.tick()
            # The expired first waiter is still queued for coroutine retirement.
            jobs.append(asyncio.create_task(_wait_until(pending[2], 1110)))
            try:
                await asyncio.sleep(0)
                self.assertLessEqual(checks.timer.when(), loop.time() + .02)
            finally:
                for job in jobs:
                    job.cancel()
                await asyncio.gather(*jobs, return_exceptions=True)

    async def test_repeated_cancellation_waits_for_owned_read_cleanup(self):
        cleaning, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def read():
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
                finished.set()

        job = asyncio.create_task(within_deadline(read(), boottime_ms() + 1000))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        job.cancel()
        await cleaning.wait()
        for _ in range(3):
            job.cancel()
            await asyncio.sleep(0)
            self.assertFalse(job.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await job
        self.assertTrue(finished.is_set())
        self.assertFalse(hasattr(asyncio.get_running_loop(), "_mesh_expiry_checks"))

    async def test_shared_timer_wakes_only_expired_waiters_and_retires(self):
        loop = asyncio.get_running_loop()
        now = [1000]
        with patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0]):
            pending = [loop.create_future() for _ in range(3)]
            jobs = [asyncio.create_task(_wait_until(task, deadline))
                    for task, deadline in zip(pending, (1100, 1200, 1300))]
            await asyncio.sleep(0)
            checks = loop._mesh_expiry_checks
            self.assertEqual(len(checks.waiters), 3)
            self.assertIsNotNone(checks.timer)
            # Simulated suspension advances BOOTTIME without advancing loop time.
            now[0] = 1150
            checks.timer.cancel()
            checks.tick()
            self.assertFalse(await jobs[0])
            self.assertTrue(all(not task.done() for task in pending))
            self.assertTrue(all(not task.done() for task in jobs[1:]))
            pending[1].set_result(None)
            self.assertTrue(await jobs[1])
            jobs[2].cancel()
            with self.assertRaises(asyncio.CancelledError):
                await jobs[2]
            self.assertFalse(pending[2].cancelled())
            self.assertFalse(hasattr(loop, "_mesh_expiry_checks"))
            self.assertTrue(checks.timer.cancelled())

    async def test_earlier_registration_reschedules_without_broadcast(self):
        loop = asyncio.get_running_loop()
        now = boottime_ms()
        first, second = loop.create_future(), loop.create_future()
        one = asyncio.create_task(_wait_until(first, now + 1000))
        await asyncio.sleep(0)
        checks = loop._mesh_expiry_checks
        timer = checks.timer
        two = asyncio.create_task(_wait_until(second, now + 20))
        await asyncio.sleep(0)
        self.assertTrue(timer.cancelled())
        self.assertFalse(await two)
        self.assertFalse(one.done())
        first.set_result(None)
        self.assertTrue(await one)
        self.assertFalse(hasattr(loop, "_mesh_expiry_checks"))

    async def test_completion_at_deadline_or_late_validation_is_rejected(self):
        now = [1000]
        with patch("mesh_plus.transport.boottime_ms", side_effect=lambda: now[0]):
            async def late():
                now[0] = 1100
                return "late"

            with self.assertRaises(TimeoutError):
                await within_deadline(late(), 1100)
            self.assertFalse(hasattr(asyncio.get_running_loop(), "_mesh_expiry_checks"))

    async def test_ordinary_boundary_keeps_read_but_final_retirement_cancels_it(self):
        finished = asyncio.Event()

        async def read():
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

        task = asyncio.create_task(read())
        self.assertFalse(await _wait_until(task, boottime_ms() + 10))
        self.assertFalse(task.done())
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertTrue(finished.is_set())

    async def test_cancelled_deadline_owner_retires_owned_io(self):
        finished = asyncio.Event()

        async def read():
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

        job = asyncio.create_task(within_deadline(read(), boottime_ms() + 1000))
        await asyncio.sleep(0)
        job.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await job
        self.assertTrue(finished.is_set())
        self.assertFalse(hasattr(asyncio.get_running_loop(), "_mesh_expiry_checks"))
