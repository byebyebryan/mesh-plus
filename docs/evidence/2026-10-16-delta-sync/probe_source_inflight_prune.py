"""Source scope diagnostic with a private generic pin; no relay-output claim."""

import argparse
import asyncio
import gc
import json
import sys
from pathlib import Path


async def run(args):
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]
    from test_sync_owned_source import HAS_INPUTS, OwnedSourceTest

    from mesh_plus.protocol import ProtocolError
    from mesh_plus.sync.inputs import input_bytes

    assert HAS_INPUTS
    errors, results = [], []
    gc.disable()
    for prune in (False, True):
        fixture = OwnedSourceTest("test_head_and_explicit_resync_control_are_owned_without_authority")
        await fixture.asyncSetUp()
        result = {"pruneDuringPin": prune}
        try:
            ref = await fixture.session.head_after_nonce({"nonce": "b" * 32})
            result["rawBytes"] = ref.nbytes
            result["registeredBefore"] = fixture.session.inspect()["ownedRefs"]
            try:
                # Disclosed private Mesh pin scaffolding. Source lifecycle and
                # counts use public inspect/aclose; no source state is patched.
                with input_bytes(fixture.cache, ref) as (raw, _):
                    if prune:
                        result["registeredDuringPin"] = fixture.session.inspect()["ownedRefs"]
                    await fixture.session.aclose()
                    result["closedSession"] = fixture.session.inspect()["closed"]
                    result["heldEncodedDuringPin"] = fixture.cache.ledger.encoded_reserved
                    lease = fixture.inputs.reserve(1)
                    lease.close()  # Source close preserves the shared owner.
                    raw = None
            except ProtocolError as error:
                errors.append(error)
                result["pinExitError"] = str(error)
            else:
                result["pinExitError"] = None
        finally:
            await fixture.asyncTearDown()
            fixture.doCleanups()
        result["finalCounters"] = {name: getattr(fixture.cache.ledger, name) for name in
                                   ("used", "reserved", "encoded", "encoded_reserved", "pending_units")}
        assert not any(result["finalCounters"].values()), result
        results.append(result)
    assert results[0]["pinExitError"] == "sync_input_retired", results
    assert results[1]["registeredDuringPin"] == 0 and results[1]["pinExitError"] is None, results
    print(json.dumps({"result": "GAP_REPRODUCED", "cases": results, "cyclicGC": "disabled",
                      "heldErrors": len(errors),
                      "scope": "actual Observer source public inspect/aclose with synthetic native Unix fixture and fabricated roots; private Mesh input_bytes pin scaffolding; no material authority, actual relay output, route, aggregate resource/RSS or performance acceptance"},
                     indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True, type=Path)
    parser.add_argument("--observer", required=True, type=Path)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
