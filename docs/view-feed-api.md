# Explicit complete-view change feed

The source implementation of the [conservative design](view-change-feed-design.md)
is an additive, opt-in feed. Its [separate contract](../contracts/view-feed-v1/contract.md)
defines packet, setup, ownership and recovery behavior. It does not enable the
retained semantic delta engine or select a release/deployment.

The publisher continues to supply complete native views through the existing
`CachedPublisher` and pure SDK profile. Mesh computes whole-record changes,
replaces complete metadata atomically and verifies the complete native target.
The receiver reconstructs and independently validates that target. Hashing is
the default; a bounded publisher token is optional and cannot bypass target
verification. A gap or reconnect requires a complete replacement.

```python
from mesh_plus.transport import IPCServer, connect_ipc
from mesh_plus.view_feed import ViewFeedBridge, ViewFeedClient

# publisher is an existing configured CachedPublisher; profile is its pure profile.
server = await IPCServer(path, ViewFeedBridge(publisher, profile=profile).serve).start()
client = await ViewFeedClient.connect(
    await connect_ipc(path), host=host, source=source, profile=profile,
)
changes = client.changes()
try:
    async for event in changes:
        if isinstance(event, dict):
            # Explicit Delivery controls: gap invalidates an application view.
            handle_control(event)
            continue
        try:
            if event.kind == "replacement":
                reset_view(event.candidate)
            else:
                apply_record_changes(event.upserts, event.removals, event.order)
        finally:
            event.close()
finally:
    await changes.aclose()
    await client.close()
    await server.close()
```

`event.candidate` always contains the full validated original Bridge candidate.
Its `ownerFrame` carries the complete new native metadata and records. An
application maintaining a view must consume that metadata atomically with the
record operations, or use the full candidate. The immutable borrowed containers
retain their reservation while borrowed. `copy.deepcopy` produces caller-owned
plain JSON for APIs that require exact dict/list types. A replacement event
has a full candidate; consumers must not treat its empty operation lists as an
empty view. Closing a handle forbids further handle access; previously borrowed
data keeps its physical reservation until dropped.

For existing Reader consumers, import `configured_reader` from
`mesh_plus.view_feed` instead of changing the existing default API. It uses the
same catalog/route policy and returns the ordinary Reader. Constructed endpoint
clients return ordinary full candidates to Reader after feed reconstruction.
Snapshot/proof requests remain full native replies, including fresh nonces.
The Reader's watch candidate remains a wakeup: its existing full read/proof cost
is still present. Events alone confer no currentness or action authority.

CLI entry points are explicit `view-feed-serve --source ID --socket PATH` and
`view-feed-bridge --source ID --stdio`, with the existing private source config.
Trusted embedded factory injection selects domain-specific pure profiles and
source windows; configuration never accepts executable imports from the wire.
The fixed remote command is the latter over the existing SSH policy. Unsupported
feed negotiation fails setup; no wire sniffing or automatic fallback is used.

Limits default to 32 MiB encoded / 64 MiB heap, 4096 records, and the existing
Delivery message maximum. Shared `FeedBudget` reservations cover feed-owned
state/intake/queues/serialization and survive held errors, output handles and
active cleanup. At channel handoff the carrier prepays bounded buffer overlap,
so a negotiated cap smaller than that carrier can refuse before source IO.
Channel creation and pre-handoff buffering belong to the caller. Reported peaks are
reservation peaks. They exclude caller-owned source input, source caches,
ordinary Reader copies and validator/code storage; no inclusive process/RSS or
combined producer acceptance is claimed. Capacity refusal closes the affected
operation without an approximate or partially admitted target.

Run `scripts/check.py` for the standalone contract/core/lifetime/IPC/stdio gate.
An additional explicit `scripts/check-view-feed-observer.py --observer PATH
--output REPORT` uses synthetic accepted data and a disposable `collect=False`
Observer Runtime, IPC/stdio feed, ordinary Reader and domain facade. It performs
no provider collection, native fleet connection, installation or deployment.

The [source qualification checkpoint](evidence/2026-10-20-view-feed/README.md)
records exact source/wheel inputs, dual-version results and remaining boundaries.
