"""Public lifecycle observations with disclosed test-only proof scaffolding.

No native source/service/network. The optional release audit instruments private
accounting only to observe which live material is released inside a callback.
"""

import gc
import json
from unittest.mock import patch

from test_sync_cache import CLOCK, IDENTITY, REQUEST, CacheProfile, baseline, proof

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import OwnedSyncCache, source_binding
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.reconstruction import MaterialRoot


def result(call):
    try:
        return {"ok": True, "value": call()}
    except ProtocolError as error:
        return {"ok": False, "error": str(error)}


def seal(inputs, raw):
    with inputs.reserve(inputs.buffer_heap(len(raw)), encoded_bytes=len(raw)) as lease:
        return lease.seal(raw)


def setup(ledger, name):
    profile = CacheProfile()
    cache = OwnedSyncCache(
        profile, source_binding("fixture", name, profile.descriptor), ledger=ledger,
        request_binding=REQUEST, _now_ms=lambda: 10000, _clock=CLOCK,
    )
    inputs = cache.input_owner()
    raw, _, _ = baseline(profile)
    candidate = cache.admit_baseline(seal(inputs, raw))
    return profile, cache, inputs, candidate, raw


def main():
    enabled = gc.isenabled()
    gc.disable()
    ledger = AllocationLedger()
    cache = sibling = callback_cache = receive = None
    findings = {}
    try:
        _, cache, inputs, candidate, raw = setup(ledger, "source")
        view = cache.confirm(candidate, seal(inputs, proof(cache, candidate)), CLOCK)
        retained = view.lookup("records", IDENTITY)
        _, sibling, sibling_inputs, sibling_candidate, _ = setup(ledger, "sibling")
        sibling_view = sibling.confirm(
            sibling_candidate, seal(sibling_inputs, proof(sibling, sibling_candidate)), CLOCK
        )
        receive = inputs.reserve(8192, encoded_bytes=1024)
        pending_ref = seal(inputs, b"pending")
        inputs.close()
        findings["afterOwnerClose"] = {
            "acquire": result(lambda: cache.acquire().tag is not None),
            "view": result(lambda: view.context(10000, CLOCK)["receipts"][0]["current"]),
            "candidate": result(lambda: candidate.tag is not None),
            "value": result(lambda: retained.materialize() is not None),
            "sealedRef": result(lambda: pending_ref.nbytes),
            "receiveResize": result(lambda: receive.resize(8192, encoded_bytes=1024)),
            "receiveSeal": result(lambda: receive.seal(b"late")),
            "receiveCredit": [receive.heap_bytes, receive.encoded_bytes],
            "encodedReserved": ledger.encoded_reserved,
            "siblingCurrent": sibling_view.context(10000, CLOCK)["receipts"][0]["current"],
        }
        replacement = cache.input_owner()
        fresh = cache.admit_baseline(seal(replacement, raw))
        fresh_view = cache.confirm(fresh, seal(replacement, proof(cache, fresh)), CLOCK)
        inputs.close()
        inputs.close()
        findings["afterReplacementAndStaleClose"] = {
            "replacementIsDistinct": replacement is not inputs,
            "replacementCurrent": fresh_view.context(10000, CLOCK)["receipts"][0]["current"],
            "siblingCurrent": sibling_view.context(10000, CLOCK)["receipts"][0]["current"],
            "receiveCredit": [receive.heap_bytes, receive.encoded_bytes],
        }
        profile, callback_cache, callback_inputs, callback_candidate, _ = setup(ledger, "callback")
        callback_proof = seal(callback_inputs, proof(callback_cache, callback_candidate))
        releases, during = [], {}
        original_release = ledger.release

        def release(value):
            if isinstance(value, MaterialRoot):
                releases.append(type(value).__name__)
            return original_release(value)

        def close_from_head(ctx):
            before = ledger.used
            callback_inputs.close()
            during.update({
                "materialReleasesInsideHead": list(releases),
                "chargedHeapBeforeClose": before,
                "chargedHeapAfterClose": ledger.used,
                "acquire": result(lambda: callback_cache.acquire().tag is not None),
            })

        profile.head_callback = close_from_head
        with patch.object(ledger, "release", side_effect=release):
            confirmation = result(lambda: callback_cache.confirm(callback_candidate, callback_proof, CLOCK).tag is not None)
        findings["reentrantHeadClose"] = {
            "confirmation": confirmation,
            "afterAcquire": result(lambda: callback_cache.acquire().tag is not None),
            "duringCallback": during,
        }
    finally:
        if receive is not None:
            receive.close()
        for owned in (callback_cache, cache, sibling):
            if owned is not None:
                owned.close()
        if enabled:
            gc.enable()
    findings["afterCloseLedger"] = ledger.inspect()
    assert ledger.used == ledger.reserved == ledger.encoded == ledger.encoded_reserved == ledger.pending_units == 0
    print(json.dumps(findings, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
