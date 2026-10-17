"""Real structural codec + fixture batch, not the actual owned-source seam."""

import argparse
import asyncio
import gc
import json
import sys
from hashlib import sha256
from pathlib import Path


async def run(args):
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    sys.path[:0] = [str(mesh / "src"), str(mesh / "tests"), str(observer), str(observer / "tests")]
    from agent_observer.mesh_sync_profile import AgentSyncProfile
    from agent_observer.sync_transport import AgentSyncTransportCodec
    from test_sync_relay import Source, Writer
    from test_sync_source import message_fixture, wire

    from mesh_plus.protocol import ProtocolError
    from mesh_plus.sync import NativeTag, SyncBudgets, create_sync_relay, source_binding
    from mesh_plus.sync.budget import AllocationLedger
    from mesh_plus.sync.canonical import canonical
    from mesh_plus.transport import LineChannel, boottime_ms

    results, errors = [], []
    gc.disable()
    for view in ("full", "active"):
        for count in (0, 1, 4):
            profile = AgentSyncProfile(profile_schema_digest="a" * 64, view=view)
            source = Source(profile)
            original = message_fixture("baseline", view=view)
            source.tag = NativeTag.parse(original["tag"])
            source.raw = wire(original)
            source.chain = [wire(message_fixture("transaction", view=view, generation=i + 2)) for i in range(count)]
            target = source.tag if not count else NativeTag.parse(json.loads(source.chain[-1])["resultTag"])
            terminal = message_fixture("control", view=view, generation=count + 1)
            terminal.update(baseTag=source.tag.wire(), targetTag=target.wire())
            raw_terminal = wire(terminal)[:-1] + b"  \n"
            source.control_transform = lambda _, raw=raw_terminal: raw
            codec = AgentSyncTransportCodec(view, encoding_id="fixture-expanded/1", expected_host="fixture")
            ledger = AllocationLedger()
            relay = create_sync_relay(source, profile.descriptor, source_binding("fixture", "agents", profile.descriptor),
                                      native_codec=codec, budgets=SyncBudgets(), ledger=ledger)
            writer = Writer()
            binding = {"readerEpoch": "a" * 32, "requestId": "fixture", "catalogRevision": "fixture",
                       "hosts": ["fixture"], "route": "fixture", "channelEpoch": "c" * 32,
                       "bridgeId": relay.bridge_id, "role": "transport-relay",
                       "encodingDigest": sha256(canonical(dict(codec.encoding))).hexdigest()}
            channel = capsule = None
            accepted = False
            try:
                channel = await relay.open_channel(LineChannel(None, writer, "fixture"), binding,
                                                   setup_deadline_ms=boottime_ms() + 15000)
                capsule = channel.begin_acquisition(deadline_ms=boottime_ms() + 15000)
                try:
                    await capsule.changes(source.tag, target=target)
                except ProtocolError as error:
                    errors.append(error)
                    assert args.expect_old_control_failure, str(error)
                    assert len(writer.frames()) == 1
                else:
                    assert not args.expect_old_control_failure
                    frames = writer.frames()[1:]
                    assert len(frames) == count + 1
                    assert [frame["payload"]["kind"] for frame in frames] == ["material"] * count + ["control"]
                    assert raw_terminal[:-1] in b"".join(writer.fragments)
                    assert frames[-1]["payload"]["native"] == terminal
                    accepted = True
            finally:
                if capsule is not None:
                    await capsule.aclose()
                await relay.aclose()
            counters = {name: getattr(ledger, name) for name in
                        ("used", "reserved", "encoded", "encoded_reserved", "pending_units")}
            assert not any(counters.values()), counters
            results.append({"view": view, "transactions": count, "accepted": accepted,
                            "nativeControlHasBindingDigestField": "nativeBindingDigest" in terminal,
                            "terminalBytesUnchanged": accepted, "finalCounters": counters})
    print(json.dumps({"result": "PASS", "cases": results, "cyclicGC": "disabled", "heldErrors": len(errors),
                      "scope": "actual Agent structural codec with fixture source/batch and fabricated roots; no actual OwnedSourceSession completion, semantic Reader, producer, real transport, aggregate resource/RSS/performance or route acceptance"},
                     indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--observer", required=True, type=Path)
    parser.add_argument("--expect-old-control-failure", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
