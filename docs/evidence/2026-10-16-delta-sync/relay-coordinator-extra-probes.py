"""Controlled source-fixture protocol probes; no normal/native service action."""
import asyncio
import gc
from hashlib import sha256
import json
from unittest.mock import patch

import mesh_plus.transport as transport
from mesh_plus.sync.canonical import canonical
from test_sync_relay import RelayTests


async def head_deadline():
    fixture = RelayTests()
    await fixture.asyncSetUp()
    capsule = None
    try:
        channel, writer = await fixture.channel()
        capsule = channel.begin_acquisition(deadline_ms=transport.boottime_ms() + 15000)
        clock = [transport.boottime_ms()]
        original = clock[0]
        writes = []
        write = writer.write

        def observe(value):
            writes.append(clock[0] - original)
            return write(value)

        writer.write = observe
        # Synchronous scanner work crosses the original local head budget.
        # Both relay and transport see the SAME BOOTTIME clock. No sleep or
        # fake change to the 15s capsule, root/schema or proof bytes is needed.
        fixture.codec.hook = lambda: clock.__setitem__(0, original + 2101)
        challenge = {'nonce': 'b' * 64, 'target': 'd' * 64,
                     'request': sha256(canonical(fixture.request())).hexdigest()}
        error = None
        with (patch('mesh_plus.sync.relay.boottime_ms', side_effect=lambda: clock[0]),
              patch('mesh_plus.transport.boottime_ms', side_effect=lambda: clock[0]),
              patch('mesh_plus.sync.relay.clock_domain',
                    return_value={'bootId': 'owner-boot', 'timeNamespace': 'time:1'})):
            try:
                await capsule.head_after_nonce(challenge)
            except BaseException as caught:
                error = type(caught).__name__ + ':' + str(caught)
        frames = writer.frames()
        proof_frames = [frame for frame in frames if frame.get('kind') == 'delivery' and
                        frame.get('payload', {}).get('kind') == 'proof']
        return {'headDeadlineMs': 2000, 'scannerExitMs': 2101,
                'writesAfterStartMs': writes, 'completeProofFramesAfterExpiry': len(proof_frames),
                'callError': error, 'gcEnabled': gc.isenabled(),
                'observation': 'A write is attempted after the original head deadline. In this probe no complete proof is emitted and the outer operation rejects; Reader authority is not exercised.'}
    finally:
        if capsule is not None:
            await capsule.aclose()
        await fixture.asyncTearDown()


async def malformed_batch():
    fixture = RelayTests()
    await fixture.asyncSetUp()
    capsule = None
    try:
        channel, writer = await fixture.channel()
        fixture.source.chain = [fixture.source.raw] * 5
        session = fixture.source.sessions[0]
        capsule = channel.begin_acquisition(deadline_ms=transport.boottime_ms() + 15000)
        error = None
        try:
            await capsule.changes(fixture.source.tag, target=fixture.source.tag, max_transactions=4)
        except BaseException as caught:
            error = type(caught).__name__ + ':' + str(caught)
        try:
            usable = channel.input_owner() is not None
        except Exception:
            usable = False
        return {'returnedTransactionRefs': len(session.refs), 'requestedMaximum': 4,
                'returnedRefsRetired': all(fixture.retired(ref) for ref in session.refs),
                'sourceSessionClosedAfterRejection': session.closed,
                'channelUsableAfterRejection': usable,
                'materialFramesEmitted': len(writer.frames()) - 1,
                'callError': error, 'gcEnabled': gc.isenabled(),
                'observation': 'Oversized tuple is closed in generic finally while source session remains open; R4 requires pre-transfer rejection and source-session cleanup.'}
    finally:
        if capsule is not None:
            await capsule.aclose()
        await fixture.asyncTearDown()


async def main():
    result = {'headDeadline': await head_deadline(), 'malformedBatch': await malformed_batch()}
    print(json.dumps(result, indent=2, sort_keys=True))


asyncio.run(main())
