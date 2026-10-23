# Active-only Agent profile withdrawal

Reviewed retirement amendment for source candidate 0.1.0a25, 2026-10-23.
The user approved withdrawal of the standalone active-only interface after
selecting working-set as its replacement. This changes current runtime
capability admission; it does not reinterpret a frozen message or published
artifact. Publication and fleet acceptance remain separate checkpoints.

The current descriptor registry, codec admission and configured publisher
advertisement reject agent-observer.mesh-active.v1. No active request is
silently converted to a working-set or full request. Existing profile_descriptor
failures occur before codec binding or endpoint dispatch. Full Agent profiles,
agent-observer.mesh-working-set.v1, Tmux and Host Mesh retain their identifiers,
schema bytes and receipt/lifecycle meanings.

The frozen [lock](../contracts/LOCK.json), contract definitions and packaged
schema copies retain their historical hashes. They are archival definitions for
prior releases, not a current capability registry. This explicit withdrawal
amendment governs current support; the original freeze retains its dated wire
semantics. No lock regeneration, default change, delta/view-feed enablement or
unrelated SDK adoption is part of the withdrawal.

Working-set preserves the active membership branch and adds independently
qualified recent membership. Its wire shape is distinct. Consumer migration and
same-input active-identity parity are required before producer retirement. See
the [execution plan](agent-ecosystem-maintenance-plan.md) and
[ledger](agent-ecosystem-maintenance-status.md).
