# Explicit Agent timing profile

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

The `0.1.0a16` source candidate implements the reviewed
[Agent v2 extension](../../../contracts/agent-profile-v2/contract.md), binding Agent
Observer API 3 / wire 5 / Service 3 through SDK interface 1. Normal selections
and the latest published a15 package remain unchanged until the owners' exact
package, carrier, resource and operational gates pass.

`descriptor("agent")` still returns v1. An explicit
`descriptor("agent", profile_id="agent-observer.mesh-candidate.v2")` selects
the new schema and native version. Reader request admission, composed response,
strict validator, digest cache, watch guard and trusted publisher factory all
follow that selected descriptor. Unknown/domain-mismatched profiles fail closed.
Default reference clients remain v1; a v2 source requires its explicit owner
profile, with no downgrade or native conversion.

Lock revision 3 adds four normative timing inputs and an explicit profile
extension. Every old native input and wire schema retains its hash. The original
freeze document adds a reviewed addendum link; Tmux's profile, factory contract,
Read/Delivery protocols and transport rules retain their original meaning.

Source acceptance passes 155 tests with no skips, including the historical
v1 native/owned SSH gates and four independent v2 descriptor/schema/IPC/guard
cases. Read/Delivery oracles, lock/package parity and lint pass. The test
environment imports current source but retains older editable distribution
metadata; immutable a16 package/version acceptance is a following gate.

Observer's independent source conformance supplies seven fixed native-v5 cases
and ten owned networking cases. The optional testing `cases` and `profile`
keywords preserve previous calls and defaults, bind successor reports to the
selected descriptor, and attribute supplied cases with independent digests.
They do not modify the frozen built-in v1 corpus or convert runtime data.

The producer's exact native clock proof is independent of these networking
fixtures. Mesh copies original timestamps/receipts and proves their freshness;
it does not infer phase entry, process lifetime or native events. Agent v2 normal
delivery is gated on IPC/SSH. WSS v2 configuration/device acceptance is deferred;
the existing optional WSS support for its accepted profiles remains unchanged.
