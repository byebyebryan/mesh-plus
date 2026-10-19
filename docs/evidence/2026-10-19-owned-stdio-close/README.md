# Owned stdio close ordering

Runtime `bfa91a6936a089d37c1a83752d3267148ba7dc69` corrects a shutdown race in
`LineChannel.close`. Closing stdin and immediately terminating an owned SSH or
relay process can interrupt a protocol-close frame already sent by the client.
The installed Observer b176 / Mesh b9 fixed-SSH attempt preserved functional
selection and independent process cleanup, but its remote Bridge ended with
`RemoteBridgeEOFError` and exit 1. That is retained as a failed graceful-close
observation, not a passing terminal result.

The channel now allows up to 250 ms for natural child exit within the original
one-second natural-exit-plus-TERM budget. TERM and KILL target the captured owned
process only; KILL/reap retains its existing one-second limit. Wire bytes,
schemas, source APIs, proof rules and authority are unchanged.

The local reproduction uses a real Client, a relay that delays forwarding the
complete close frame by 50 ms, and a real Bridge. Both interpreters reproduce
the old premature-termination path. The source correction lets the Bridge and
relay return normally. That separate source reproduction records the Bridge as
gone; the final regression below independently records successful reap.

An immutable b9 export plus the final test overlay fails the one close-order
method on Python 3.14.8 and 3.11.17: the relay records receipt of the full close
frame, then the Bridge exits 1. The immutable bfa export passes all 39 transport
and terminal-lifetime methods on each interpreter, with cyclic GC disabled.
Both before and after runs record `bridgeReaped=true`; after records Bridge and
relay exit 0. A second new test retains escalation and reap for a TERM-ignoring
owned child. The test-only audit copies its bounded receipt before ordinary
temporary-directory cleanup and changes no source or test bytes.

The canonical gate passes 443 tests with no skips, 37 locked files, 28 packaged
schemas, 116 design checks, 169 delivery checks and Ruff. The exact gate result,
log, final GC-disabled controller, four results/logs/close receipts and earlier
local reproductions are preserved under `artifacts/`. `receipt.json` binds their
original paths and hashes. Two failed primary audit setups remain named in the
diagnostic JSONs; they do not represent product failures. Earlier tool-only
17-test reports have no saved logs and are not invented as durable evidence.

This packet establishes the bounded source correction. It does not include a
fresh installed fixed-SSH replay, native-provider qualification, cost/RSS
reattribution, release, normal-role change or consumer adoption. The earlier
fixed-SSH failure and all original producer gates retain their own source pins.
