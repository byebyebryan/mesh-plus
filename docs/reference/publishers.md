# Cached publishers

`CachedSource`, `CachedPublication` and `CachedPublisher` are supported SDK 1
interfaces for Observer-owned cached publication, independent of optional WSS.
Readers and publishers keep their explicit native profiles and frozen wire
bindings. [Integration](../guides/integration.md) describes the owning gates.

## Public types and constructor

Import `CachedSource`, `CachedPublication`, `CachedPublisher` from
`mesh_plus.api` (also available from `mesh_plus.publisher`).

- `CachedSource.snapshot()` is async and returns one checked native service
  frame. It reads cached state without scheduling collection. Each invocation
  owns and retires its connections, including cancellation during acquisition.
- `CachedSource.watch()` returns an async iterator with `aclose()`, yielding
  `CachedPublication(frame, epoch, barrier)`. The source filters native heartbeats,
  validates native request/UID/host/clock/order and reports loss/restart; it never
  turns a missing record into positive evidence. Each iterator owns its resources.
- `CachedPublisher(domain, host, source, native, *, profile)` requires an explicit
  pure `StateProfile`. Domain remains tmux or agent and its descriptor is frozen.
  No subclassing or reference-adapter import is needed.

The helper supplies the existing Bridge adapter interface: fixed `host`, `source`,
`profile`, `capabilities = ("snapshot", "proof", "subscribe")`, `validate(payload)`,
async `snapshot(parameters)`, `proof(parameters)` and `watch()` yielding existing
`Publication`. Snapshot parameters are `{}`; proof parameters contain only a
32–64-character lowercase hexadecimal nonce. Watch barriers retain the existing
Delivery baseline schema and are producer-owned, bounded JSON.

Mesh deep-copies admitted frames/barriers, checks profile binding, lossless native
reconstruction, local clock and chronology, constructs canonical owner digests,
and derives remaining leases exclusively from original receipts. For receipts
present in consecutive accepted acquisitions within one stream under the same
publisher/clock, counters cannot regress or change expiry without advancing
acceptance. Each watch owns its history; snapshot/proof acquisitions are serialized
and share a separate history. Independent reads and watches can finish in a
different order from their native observations. Tracking commits
only after successful validation. The native source must enforce its own sample
ordering, including disappearance/reappearance of components; this helper is
not an unbounded history of retired native namespaces.

Proof validates its nonce before calling a **new** `native.snapshot()`. Neither a
watch copy nor a retained prior snapshot proves current acquisition. Receiver
nonce matching, clock/lease admission and conservative effective rows remain
compulsory. A source frame can be historical/stale: it does not become fresh
merely because it was wrapped again. Watch `aclose()` is owned through repeated
caller cancellation. Source operations themselves remain responsible for their
own cancellation-safe acquisition/read cleanup. Synchronous trusted callbacks
are not preemptible; no collection/action, global memory or CPU guarantee is added.

## Installed factory and fixed SSH command

The supported trusted Python hooks are:

```python
from mesh_plus.cli import configured_adapter, main

# factory(host: str, source: str, socket: str) -> Bridge-compatible publisher
publisher = configured_adapter(private_sources_toml, source_id,
                               publisher_factories={"tmux": make_tmux_publisher})
main(publisher_factories={"tmux": make_tmux_publisher})
```

`run(args, *, publisher_factories=None)` supports embedded async hosting.
`mesh_plus.wss.cli.main/run` accept the same keyword for an explicitly selected
WSS listener. `publisher_factories` is captured before dispatch, contains only
`tmux`/`agent` callable factories, and is never supplied by wire, config or CLI.
Factories are synchronous, lazy and acquire no native resources during
construction. They return publishers whose fixed host/source/profile match the
selected descriptor and whose capabilities/methods implement the reviewed state
surface. A selected exception or invalid binding fails; there is no reference
fallback. Domains intentionally omitted from the map retain the legacy adapter.

A trusted installed launcher named **mesh-plus**, in the independently selected
remote environment, calls `main(publisher_factories=...)`. For example:

```python
from mesh_plus.cli import main

def make_tmux_publisher(host, source, socket):
    # This module/function is supplied by the Observer owner, not discovered.
    from tmux_observer.mesh_publisher import make_publisher
    return make_publisher(host, source, socket)

if __name__ == "__main__":
    raise SystemExit(main(publisher_factories={"tmux": make_tmux_publisher}))
```

The example uses Tmux Observer's installed `mesh_publisher.make_publisher`
factory. Install the compatible owning package and keep the import lazy. Mesh authority commands
(`mesh-plus mesh ...`) bypass the mapping and all state/native imports. Preserve
the authority's existing launcher/import rules when composing a real deployment.

The unchanged remote invocation is `mesh-plus bridge --source SOURCE --stdio`.
The unchanged private descriptor is version 1 with host and per-source
`domain`/absolute `socket` only. Install the same static map for local `serve`
and remote `bridge`; a local subclass change does not change remote dispatch.
No executable/module selector, entry-point discovery or config version is added.
The stock console script continues using reference adapters unless a trusted
launcher explicitly opts in. No global publisher shutdown callback exists;
snapshot/watch must own all operation resources.
## Owner acceptance

Qualify the actual native source's validation, cached status/watch acquisition,
proof-after-nonce, receipt preservation, failure/restart, capacity and owned
cleanup. Then qualify installed local/fixed-SSH publication, resource bounds,
selection and paired rollback separately. A pure fixture pass does not establish
native, managed, graphical or physical acceptance.
