"""Minted control ingress: physical socket/pipe storage, strict JSON and expiry."""

import asyncio
import gc
import json
import os
import socket
import unittest
import weakref
from unittest.mock import patch

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.control_carrier import (
    _BASE_HEAP,
    control_carrier_from_ipc,
    control_carrier_from_stdio,
)
from mesh_plus.transport import boottime_ms


class CarrierTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gc_enabled = gc.isenabled()
        gc.disable()
        self.carriers, self.peers, self.errors = [], [], []

    async def asyncTearDown(self):
        try:
            for carrier, ledger in self.carriers:
                await carrier.aclose()
                self.assertEqual((ledger.used, ledger.reserved, ledger.encoded,
                                  ledger.encoded_reserved, ledger.pending_units), (0,) * 5)
            for peer in self.peers:
                peer.close()
            self.assertFalse(gc.isenabled())
        finally:
            if self.gc_enabled:
                gc.enable()

    def carrier(self, ledger=None):
        supplied, peer = socket.socketpair()
        peer.setblocking(False)
        self.peers.append(peer)
        ledger = AllocationLedger() if ledger is None else ledger
        carrier = control_carrier_from_ipc(supplied, ledger=ledger)
        self.assertEqual(supplied.fileno(), -1)
        self.carriers.append((carrier, ledger))
        return carrier, peer, ledger

    async def send(self, peer, raw):
        await asyncio.get_running_loop().sock_sendall(peer, raw)

    async def frame(self, carrier, maximum=8192):
        return await carrier.receive_control(maximum_bytes=maximum, deadline_ms=boottime_ms() + 15000)

    def value(self, frame, ledger):
        with ledger.reserve(frame.header.materialization_bytes):
            result = frame.header.materialize()
            # This helper's returned DTO is a test-owned semantic oracle, not a
            # retained production copy or aggregate resource measurement.
            return result

    async def test_coalesced_tail_and_fragment_keep_first_application_ingress_floor(self):
        carrier, peer, ledger = self.carrier()
        now = [boottime_ms()]
        with patch("mesh_plus.sync.control_carrier.boottime_ms", side_effect=lambda: now[0]):
            await self.send(peer, b'{"n":1}\n{"n":2}\n{"n":')
            first = await self.frame(carrier)
            floor = first.first_byte_ms
            self.assertEqual((first.start, first.stop), (0, 8))
            first.close()
            now[0] += 3500
            second = await self.frame(carrier)
            self.assertEqual(second.first_byte_ms, floor)
            second.close()
            await self.send(peer, b'3}\n')
            third = await self.frame(carrier)
            self.assertEqual(third.first_byte_ms, floor)
            self.assertEqual(self.value(third, ledger), {"n": 3})
            third.close()

    async def test_two_handle_limit_pauses_without_parsing_a_third_frame(self):
        carrier, peer, ledger = self.carrier()
        await self.send(peer, b'{}\n{}\n{}\n')
        first, second = await self.frame(carrier), await self.frame(carrier)
        task = asyncio.create_task(self.frame(carrier))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        held = ledger.reserved
        self.assertEqual(len(carrier._frames), 2)  # bounded private slot inventory
        await asyncio.sleep(0)
        self.assertEqual(ledger.reserved, held)
        first.close()
        third = await task
        self.assertEqual((second.start, third.start), (3, 6))
        second.close()
        third.close()

    async def test_copy_credit_and_revoked_handles_survive_close_without_owner_cycle(self):
        carrier, peer, ledger = self.carrier()
        writer = weakref.ref(carrier.output_channel.writer)
        await self.send(peer, b'{"values":[1,true,null,"\\ud83d\\ude00"]}\n')
        frame = await self.frame(carrier)
        header = frame.header
        copy_credit = ledger.reserve(header.materialization_bytes)
        detached = header.materialize()
        frame.close()
        for access in (lambda: frame.start, lambda: frame.stop, lambda: frame.first_byte_ms,
                       lambda: frame.header, lambda: header.materialization_bytes, header.materialize):
            try:
                access()
            except ProtocolError as error:
                self.errors.append(error)
            else:
                self.fail("retired stamped access remained usable")
        await carrier.aclose()
        self.assertEqual(ledger.reserved, copy_credit.amount)
        self.assertEqual(detached, {"values": [1, True, None, "😀"]})
        detached = None
        copy_credit.close()
        owner = weakref.ref(carrier)
        self.carriers.clear()
        carrier = None
        self.assertIsNone(owner())
        self.assertIsNone(writer())

    async def test_strict_syntax_unicode_duplicates_and_tree_reject_before_public_header(self):
        invalid = (b'{"x":1,"x":2}\n', b'{"x":1,"\\u0078":2}\n', b'{"x":-0}\n',
                   b'{"x":1.5}\n', b'{"x":NaN}\n', b'\xef\xbb\xbf{}\n', b'{}\r\n',
                   b'{"x":"\\ud800"}\n', b'{"x":"\\udc00"}\n', b'{"x":"\xc0\x80"}\n',
                   b'{"x":"' + b'x' * 4097 + b'"}\n', b'{"x":' + b'[' * 9 + b'0' + b']' * 9 + b'}\n',
                   b'{"x":[' + b'0,' * 32 + b'0]}\n')
        for raw in invalid:
            with self.subTest(raw=raw[:50]):
                carrier, peer, ledger = self.carrier()
                await self.send(peer, raw)
                try:
                    await self.frame(carrier)
                except ProtocolError as error:
                    self.errors.append(error)
                else:
                    self.fail("malformed control minted a public header")
                self.assertTrue(carrier._closed)
                self.assertEqual(ledger.reserved, 0)

    async def test_failed_detached_copy_clears_payload_and_hook_frames_before_credit_return(self):
        carrier, peer, ledger = self.carrier()
        await self.send(peer, b'{"payload":"held-copy-error"}\n')
        frame = await self.frame(carrier)
        header = frame.header
        scratch, markers = ledger.reserve(header.materialization_bytes), []
        class Marker:
            pass
        def fail_copy(value):
            marker = Marker()
            markers.append(weakref.ref(marker))
            raise ProtocolError("copy_failure")
        try:
            with patch("mesh_plus.sync.control_carrier.copy.deepcopy", side_effect=fail_copy):
                try:
                    header.materialize()
                except ProtocolError as error:
                    self.assertEqual(str(error), "copy_failure")
                    self.errors.append(error)  # retain the actual public error/trace
                else:
                    self.fail("copy failure was lost")
            self.assertIsNone(markers[0]())
            self.assertEqual(self.value(frame, ledger), {"payload": "held-copy-error"})
            frame.close()
            await carrier.aclose()
            self.assertEqual(ledger.reserved, scratch.amount)
        finally:
            scratch.close()

    async def test_exact_frame_capacity_and_refusal_before_decoder_allocation(self):
        carrier, peer, _ = self.carrier()
        await self.send(peer, b'{}' + b' ' * 8189 + b'\n')
        (await self.frame(carrier)).close()
        carrier, peer, ledger = self.carrier(AllocationLedger(maximum=_BASE_HEAP + 3 * 40 + 131072 - 1))
        await self.send(peer, b'{}\n')
        with patch("mesh_plus.sync.control_carrier.parse_control", side_effect=AssertionError("unpaid parser")):
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                await self.frame(carrier)
        self.assertEqual(ledger.reserved, 0)

    async def test_factory_refusal_precedes_buffers_and_invalid_arguments_keep_ownership(self):
        supplied, peer = socket.socketpair()
        self.peers.extend((supplied, peer))
        with self.assertRaisesRegex(ProtocolError, "sync_control_owner"):
            control_carrier_from_ipc(supplied, ledger=object())
        self.assertGreaterEqual(supplied.fileno(), 0)
        ledger = AllocationLedger(maximum=_BASE_HEAP - 1)
        with patch("mesh_plus.sync.control_carrier.SyncControlCarrier.__init__", side_effect=AssertionError("unpaid buffers")):
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                control_carrier_from_ipc(supplied, ledger=ledger)
        self.assertEqual(supplied.fileno(), -1)
        self.assertEqual((ledger.reserved, ledger.encoded_reserved), (0, 0))

    async def test_exact_tree_node_limit_and_truncated_eof_leave_no_live_frame(self):
        # Root + key + outer list + 16*(list + 30 scalars) + 13 scalars = 512.
        at_limit = {"x": [[0] * 30 for _ in range(16)] + [0] * 13}
        carrier, peer, ledger = self.carrier()
        await self.send(peer, json.dumps(at_limit).encode() + b'\n')
        frame = await self.frame(carrier)
        self.assertEqual(self.value(frame, ledger), at_limit)
        frame.close()
        for raw, expected in ((json.dumps({"x": at_limit["x"] + [0]}).encode() + b'\n', "sync_control_tree"),
                              (b'{"incomplete":', "sync_control_truncated")):
            carrier, peer, ledger = self.carrier()
            await self.send(peer, raw)
            peer.shutdown(socket.SHUT_WR)
            with self.assertRaisesRegex(ProtocolError, expected) as failure:
                await self.frame(carrier)
            self.errors.append(failure.exception)
            self.assertEqual((ledger.reserved, ledger.encoded_reserved, len(carrier._frames)), (0, 0, 0))

    async def test_clock_regression_scope_replacement_and_offset_overflow_retire_connection(self):
        for mode in ("regress", "scope", "offset"):
            carrier, peer, ledger = self.carrier()
            await self.send(peer, b'{}\n')
            (await self.frame(carrier)).close()
            await self.send(peer, b'{}\n')
            if mode == "regress":
                context = patch("mesh_plus.sync.control_carrier.boottime_ms", return_value=carrier._last_floor - 1)
            elif mode == "scope":
                context = patch("mesh_plus.sync.control_carrier.clock_domain", return_value={"bootId": "new"})
            else:
                carrier._end = carrier._cursor = carrier._low = 2**64 - 2
                context = patch("mesh_plus.sync.control_carrier.clock_domain", return_value=carrier._scope)
            with context, self.assertRaisesRegex(ProtocolError, "sync_control_provenance"):
                await self.frame(carrier)
            self.assertTrue(carrier._closed)
            self.assertEqual(ledger.reserved, 0)

    async def test_buffered_tail_and_minted_header_reject_changed_clock_before_new_read(self):
        for mode in ("scope-tail", "regress-tail", "scope-header", "regress-output"):
            with self.subTest(mode=mode):
                await self._changed_clock(mode)

    async def _changed_clock(self, mode):
        carrier, peer, ledger = self.carrier()
        await self.send(peer, b'{}\n{}\n')
        first = await self.frame(carrier)
        header = first.header
        if mode.endswith("tail"):
            first.close()
        if mode.startswith("scope"):
            context = patch("mesh_plus.sync.control_carrier.clock_domain", return_value={"bootId": "new"})
        else:
            context = patch("mesh_plus.sync.control_carrier.boottime_ms", return_value=carrier._last_floor - 1)
        line = carrier.output_channel
        with context, patch("mesh_plus.sync.control_carrier.os.readv", side_effect=AssertionError("unexpected read")):
            with self.assertRaisesRegex(ProtocolError, "sync_control_provenance") as failure:
                if mode.endswith("tail"):
                    await self.frame(carrier)
                elif mode.endswith("header"):
                    _ = header.materialization_bytes
                else:
                    line.writer.write(b'prohibited')
            self.errors.append(failure.exception)
        self.assertEqual(line.inspect()["physicalSentBytes"], 0)
        self.assertTrue(carrier._closed)
        await carrier.aclose()
        self.assertEqual((ledger.reserved, ledger.encoded_reserved), (0, 0))

    async def test_preallocated_range_pressure_coalesces_without_later_floor(self):
        carrier, peer, ledger = self.carrier()
        raw = b'{"x":"' + b'x' * 270 + b'"}\n'
        reads, wake, now = [0], asyncio.Event(), [boottime_ms()]
        first = now[0]
        readv = os.readv
        def counted(*args):
            result = readv(*args)
            reads[0] += 1
            wake.set()
            return result
        with (patch("mesh_plus.sync.control_carrier.os.readv", side_effect=counted),
              patch("mesh_plus.sync.control_carrier.boottime_ms", side_effect=lambda: now[0])):
            task = asyncio.create_task(self.frame(carrier))
            for index, char in enumerate(raw):
                wake.clear()
                now[0] = first + index
                await self.send(peer, bytes((char,)))
                while reads[0] <= index:
                    await asyncio.wait_for(wake.wait(), 1)
                self.assertLessEqual(carrier._count, 256)
                self.assertEqual(len(carrier._ranges), 256)
            frame = await task
            self.assertEqual(frame.first_byte_ms, first)
            self.assertEqual(self.value(frame, ledger), {"x": "x" * 270})
            frame.close()

    async def test_fixed_stdio_and_direct_linechannel_read_cannot_add_an_input_reader(self):
        read_fd, input_peer = os.pipe()
        output_peer, write_fd = os.pipe()
        ledger = AllocationLedger()
        carrier = control_carrier_from_stdio(read_fd, write_fd, ledger=ledger)
        self.carriers.append((carrier, ledger))
        try:
            os.write(input_peer, b'{}\n')
            (await self.frame(carrier)).close()
            with self.assertRaisesRegex(ProtocolError, "sync_control_provenance"):
                await carrier.output_channel.receive()
            carrier.output_channel.writer.write(b'output')
            await carrier.output_channel.writer.drain()
            self.assertEqual(os.read(output_peer, 6), b'output')
        finally:
            os.close(input_peer)
            os.close(output_peer)

    async def test_disconnect_and_repeated_cancel_retire_only_this_carrier(self):
        carrier, _peer, ledger = self.carrier()
        sibling, other, shared = self.carrier(ledger)
        task = asyncio.create_task(self.frame(carrier))
        await asyncio.sleep(0)
        task.cancel()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await carrier.aclose()
        await self.send(other, b'{}\n')
        (await self.frame(sibling)).close()
        self.assertEqual(ledger.encoded_reserved, 65536)
        await sibling.aclose()
        self.assertEqual(shared.reserved, 0)

    async def test_blocked_writer_pin_unwinds_before_shared_carrier_credit_returns(self):
        carrier, peer, ledger = self.carrier()
        supplied = socket.socket(fileno=carrier._write_fd)
        supplied.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
        supplied.detach()
        peer.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        copy_credit = ledger.reserve(65536, encoded=65536)
        raw = b'x' * 65536
        carrier.output_channel.writer.write(raw)
        self.assertGreater(carrier.output_channel.writer.get_write_buffer_size(), 0)
        task = asyncio.create_task(carrier.output_channel.writer.drain())
        await asyncio.sleep(0)
        carrier._begin_close()
        self.assertGreaterEqual(ledger.reserved, _BASE_HEAP + copy_credit.amount)
        await carrier.aclose()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual((ledger.reserved, ledger.encoded_reserved), (65536, 65536))
        raw = None
        copy_credit.close()
        self.assertEqual((ledger.reserved, ledger.encoded_reserved), (0, 0))


if __name__ == "__main__":
    unittest.main()
