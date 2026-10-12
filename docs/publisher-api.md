# Observer-owned cached publisher API

Accepted additive SDK interface 1 surface in the **0.1.0a15 candidate**. This
seam is independent of optional WSS. All Read/Delivery/profile schemas and the
contract lock retain their bytes. Reader SDK signatures and default reference
publishers remain supported. See the [installed acceptance](evidence/2026-10-11-publisher-factory/README.md)
for the exact artifact and independent carrier/compatibility gates.

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
present in consecutive accepted samples under the same publisher/clock, counters
cannot regress or change expiry without advancing acceptance. Tracking commits
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

The Observer module above is an integration example, **not an existing supported
Observer export**. Keep that import inside the factory. Mesh authority commands
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

## Handoff and owner acceptance

Both owners can now implement their cached source and static factory against
this surface independently. Retain existing reader `profile=` usage and the
frozen protocol/profile identifiers. Use the exact reviewed a15 wheel; Tmux's
current exact a13 guard needs a separately reviewed owner artifact change.
Agent's broad dependency floor alone does not accept a future artifact.

Each owner must prove native validation, passivity, status/watch-only acquisition,
proof-after-nonce, receipt preservation, iterator cleanup, failure/restart and
capacity against its own public native service. Then accept installed local and
fixed remote SSH publisher paths, mixed old/new bridges, resources, immutable
selection, recovery and rollback. Pure synthetic conformance cannot certify those
native/operational gates. WSS, desktop/UI/action behavior and physical suspend are
separate. Retaining the existing reference installation is supported throughout.
