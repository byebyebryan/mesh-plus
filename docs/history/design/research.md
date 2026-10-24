# Mesh Plus source baselines and research

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

## Initial research and subsequent source reviews

Initially inspected 2026-10-09. The table and tracking comparisons below describe
that research history, not current remote publication or deployment status.
Full reviewed heads and input digests are recorded in
[source baselines](../../evidence/source-baselines.json); see [the handoff](../../handoff.md)
for current integration readiness. The local checkout review is
read-only outside Mesh Plus; remote runtime and installed artifact parity are
separate evidence.

| Repository | Baseline | Relevant source |
| --- | --- | --- |
| SSH Plus | `a69bd75` initially; `e01f89c` after default authority adoption | [Host Mesh v1](../../../reference/rofi-ssh-plus/docs/HOST_MESH_V1.md), facade/legacy authority, `probe.py`, canonical fixtures |
| Tmux Observer | `128f7f8`, 0.5.0a1 | [Boundaries](../../../reference/tmux-observer/docs/component-boundaries.md), [wire rules](../../../reference/tmux-observer/docs/wire-v1.md), `ssh.py`, `_remote_state.py`, `_fleet_state.py` |
| Tmux Plus | `5105eae` | `observer_client.py`, pinned artifact, [fleet performance](../../../reference/rofi-tmux-plus/docs/fleet-performance.md) |
| Agent Observer | `43b8d3e` initially, `bca4c26` after event research, `8776cc6` after state-push refinement; 0.5.0a11 | [API 2](../../../reference/agent-observer/docs/api-v2.md), [service 2](../../../reference/agent-observer/docs/service-protocol-v2.md), [state push](../../../reference/agent-observer/docs/state-push-design.md), [client handoff](../../../reference/agent-observer/docs/api-v2-client-handoff.md) |
| Agent Plus | `f28e562`, deliberately deferred | README and `contract_backend.py` show old routed reads/cache and separate guarded writes; not current read semantics |

Agent Observer was 38 commits ahead at initial inspection, 39 after event research
and 40 after state-push refinement; Agent Plus is ten ahead. These are local tracking comparisons, not a refreshed remote
publication audit. Both have clean worktrees. Tmux/Plus and SSH Plus are clean
and match their local tracking branches.

Agent advanced during design validation. The intervening `bca4c26` commit settles
a proposed state/native-event publication design and adds the explicit Mesh
boundary to its ownership document. The accepted state schemas and public
read/service implementation are unchanged. The source manifest records both
heads and the reviewed new document hashes; frozen state fixtures remain exact.
The new [event networking note](event-delivery.md) preserves cursor/gap semantics
without treating the proposed event API as implemented.

During the transport follow-up, `8776cc6` added complete-view state-push design,
consumer studies and installed/native evidence. Production APIs and frozen
schema/fixture bytes remain unchanged. We read its design/review as producer
authority; we did not rerun its native study or promote it into Mesh network
acceptance. Native occurrence events are now explicitly deferred. The original
manifest is preserved in [first-pass baselines](../../evidence/read-design-baselines.json).

The [transport evaluation](transport-evaluation.md) records the second pass's
primary references and judgments for SSH, WSS, HTTP/SSE, gRPC, NATS, MQTT,
JSON-RPC and framing/encoding alternatives. The
[carrier study](../../evidence/carrier-study.json) is owned synthetic evidence only.

## Findings that shape the contract

Tmux already has persistent owner-only SSH subscriptions, conservative nonce
proofs, source/desktop separation and cached fleet views. Its implementation
is useful extraction evidence, but its 10-second owner lease, desktop context,
session comparisons and 1 MiB aggregate protocol cannot become generic Agent
assumptions.

Agent's shared service is host-local, exposes cached snapshot/watch and has no
nonce probe or client-triggered refresh. Its public pure codecs and local
transport validate source scope and independently leased runtime/history.
Host-local bridge proof can reuse those cached reads. The original source lease
and boot/time namespace, rather than pipe arrival, anchor remaining validity.

Both native row identities already include host scope. Their envelopes are
different: Tmux's native observation has a single `source`; Agent snapshot has a
single `host` with provider sources. Neither singular envelope can represent a
fleet unchanged. The candidate introduces a common mesh-aware domain envelope
while preserving complete row shapes and lossless native reconstruction.

Agent's metadata receipt dependencies and unsaved retention are not fully
encoded as per-field/per-row public proofs. Conservative provider invalidation
and omission of unsaved historical rows avoid inventing stronger guarantees.
Exact parity may motivate later producer contract additions independently.

Tmux Plus currently checks exact packaged runtime modules. Pure wire compatibility
does not make a newly separated Mesh distribution an accepted installed tuple.
Agent Plus's intentionally old reader/cache should migrate after the producer
and Mesh adapter settle; it should not constrain active Agent design.

## Primary external references

Research consulted these primary specifications and manuals on 2026-10-09:

- [OpenSSH remote command and PTY behavior](https://man.openbsd.org/ssh): remote
  commands are sent as a command line, so the bridge boundary needs tested quoting.
- [OpenSSH configuration and connection sharing](https://man.openbsd.org/ssh_config):
  a private owned control path is required if optional sharing is adopted.
- [Linux BOOTTIME](https://man7.org/linux/man-pages/man2/clock_gettime.2.html):
  suspend-aware local deadlines must carry their clock domain.
- [Linux time namespaces](https://man7.org/linux/man-pages/man7/time_namespaces.7.html):
  clock origin is not safely compared across namespaces or hosts.
- [JSON Schema 2020 12 validation](https://json-schema.org/draft/2020-12/json-schema-validation):
  structural constraints complement the explicit semantic/clock/scope checks.

These establish transport/clock/schema mechanics, not current installed native
behavior. Repository contracts remain the source of Observer meanings.
