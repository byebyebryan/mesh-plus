# Mesh Plus integration handoff

## Current disposition

The cached-state core is integrated with both Observers. It supports polling and
pushed replacement state over private local IPC and persistent SSH stdio. The
wire boundary is frozen by [the state contract](contract-freeze.md) and
[`contracts/LOCK.json`](../contracts/LOCK.json). The lock takes precedence over
broader design studies and reserved schema variants.

The released **0.1.0a9** wheel is frozen from
`3b6754312000d1c39a3ab407986130b9c621f0d4`, SHA-256
`07882909a49cd513b5c114da7890bebfe9b1592da3a08cca69a68c24817164c2`.
All frozen schema, lock and authority inputs retain their reviewed bytes.
Installed standalone acceptance passes 74 tests without Observer packages;
installed native/SSH acceptance passes 106 tests on Python 3.14.

Current source additionally contains an **a10 candidate** subscription-admission
cancellation fix. Its isolated wheel passes 75 standalone and 107 native/SSH
tests; it has not replaced the released a9 artifact or consumer pins. The
[operational hardening record](evidence/2026-10-10-operational-hardening/README.md)
separates source fixes, private-input measurements and pending adoption gates.
Tmux source additionally rejects stale control bindings and reserves one retiring
local bridge handler alongside its active Reader; seven owned a10 integration
tests pass. Agent source has a compatible ASCII validator fast path. Exact new
Observer/picker artifacts and paired deployment remain separate acceptance.

Snap and Starship select a9 for the public CLI/catalog authority and Tmux
Observer 0.6.0a4 / Plus 0.12.0a4. Agent uses new private a9 environments with
the same a13 reader and a12 bridge Observer artifacts. Its a15 collector and
a16 writer retain their prior selections. Source, installed bytes, collector
incarnation and foreign managed checkout preservation are separate checks.
See the [coordinated adoption record](evidence/2026-10-10-fleet-adoption/README.md)
for dated gates and limits; the [reliability plan](reliability-and-measurement.md)
records proactive channel rotation, cancellation-safe cleanup and measured costs.
Earlier managed SDK roots remain available for paired rollback. Graphical input,
physical suspend, multi-hour production-budget rotation and further consumer
migrations remain separate acceptance work.

The [changelog](../CHANGELOG.md) records version differences. The
[Agent SDK checkpoint](agent-integration.md) records the a4 source checks and
the historical exact-HEAD check limitation. The
[review evidence](evidence/handoff-review.json) binds the prior a2 pass to source,
tests, candidate package bytes and the unchanged contract lock. The
[operations pass](mesh-operations.md) and [lab evidence](evidence/mesh-lab.json)
describe a3 diagnostics, synthetic workloads and the optional pool proposal. Older evidence
files describe their own checkpoints; they do not certify changed source bytes.

## Ownership and implementation entry points

| Owner | Reusable boundary | Responsibility |
| --- | --- | --- |
| Mesh | `transport.LineChannel`, `IPCServer`, `connect_ipc`, `connect_ssh` | Authenticated bounded delivery, owned lifetime and cleanup |
| Mesh | `client.Client`, `Subscription`, `bridge.Bridge`, `Publication` | Concurrent request/reply, subscription barriers, credit, gap/resync and terminal handling |
| Mesh | `reader.Reader`, `Endpoint` | Immutable fleet selection, per-host outcomes, proofs, catalog monitoring and replacement views |
| Mesh | `configured_read.configured_reader` | Configured local/catalog binding; route reporting requires explicit opt-in |
| Mesh | `view.validate_response`, `current_sessions`, `ReadGuard` | Validated native reconstruction, expiry and conservative current rows |
| Mesh | `authority`, `catalog.Catalog`, `MeshAuthority`, `SSHPlusAuthority` | Configured hosts/routes, revisions and route reports; one selected writer |
| Observer | Supported pure domain codecs and cached publisher hooks | Native identity, state, coverage, original source receipts, expiry and collection scheduling |
| Tmux coordinator | Mesh endpoint binding and compatibility projection | Desktop context, Open/Attached joins, existing Fleet/Session contracts and action revalidation |
| Agent consumer | New profile adoption after producer acceptance | Presentation, provider interpretation, guarded actions and UI lifetime |
| SSH Plus | Shared authority facade plus its picker | Terminal launch, ad-hoc destinations, connection history and recent ordering |

The current `observer.ObserverCodec` and `ObserverAdapter` are reference
integrations against supported pure producer facades. Their existence does not
prove acceptance of a producer-owned adapter or a live service migration.
Adapters may move into their owning Observer package while retaining the Mesh
boundary and exact producer semantics.

An adapter declares fixed `host`, `source`, `profile` and `capabilities`, and
implements `validate(payload)`, async `snapshot(parameters)`, async
`proof(parameters)` and async `watch()` yielding `Publication(payload, epoch,
barrier)`. The supported capabilities are `snapshot`, `proof`, `subscribe`.
`source` is a configured selector matching `[a-z][a-z0-9_]{0,127}`; Agent's
provider/namespace receipt IDs are separate native identities.

`Client` accepts a pure payload validator. The current `Reader` additionally
expects `client.codec` to be the bound `ObserverCodec.validate` method, whose
owner provides `domain`, `host`, `receipts()` and native frame helpers. Supplying
an arbitrary lambda is sufficient for generic Delivery tests but not for domain
Reader integration. A producer-owned replacement must preserve this boundary or
coordinate an explicit compatible SDK refactor.

## How a consumer uses the contract

Resolve ordered immutable endpoints before calling `Reader.execute(request)`.
It yields one snapshot or a replacement watch stream, followed by at most one
terminal base error. Each endpoint connects an owned `Client`; Reader closes it.
Fleet watches require a catalog revision check callback. There is no implicit
polling fallback when subscription capability is missing.

Snapshot consumers call `validate_response` and `current_sessions`. Watch
consumers use one `ReadGuard` per request, call `accept(frame)` for each frame,
then `current(now_ms, clock)` when rendering. The transport owner calls
`disconnect()` on EOF, invalid frames or liveness failure and creates a new
guard for reconnect. Retaining the last JSON object does not retain authority.

Subscription terminal items are permanent: completion stops iteration; failure
raises once and subsequent iteration stops. Explicit `Subscription.close()`
still releases SDK bookkeeping. A request `ended` frame wakes its caller with
a typed Delivery error while independent work remains usable.

Mesh transports cached reads and state changes. It does not start collectors,
increase collection cadence, infer idle state, or retry actions. Remote pushed
state requires a nonce-bound cached read/proof before granting positive validity.
Heartbeats, polling and new connections never renew original source receipts.

## Integration work and gates

Tmux's producer/coordinator integration and paired a9 selection are accepted in
the coordinated adoption record above. Agent's independently selected a9 transport
uses the frozen profile; its a15 collector performance work is producer-owned
and does not establish lower transport cost. The gates below remain applicable
to changed artifacts and further consumers; they are not a claim that either
Observer is still awaiting initial Mesh adaptation.

1. **Tmux Observer and coordinator:** bind the owned cached publisher through
   Mesh, retain native source and desktop separation, compare the existing
   Fleet/Session compatibility projections, and prove passivity, receipt expiry,
   reconnect and action revalidation. Publish and accept the paired artifact/UI
   tuple independently of pure schema parity.
2. **Agent Observer:** review its current API 2 / snapshot 4 / service 2 inputs
   against the frozen profile before moving or replacing the reference adapter.
   Preserve per-provider partial/unknown states, original component receipts,
   saved/unsaved retention limits and cached-only proof. Producer collection
   and native-service acceptance remain producer-owned.
3. **Consumers:** adopt the new explicit profile and the pure validity facade;
   preserve complete host-qualified record identities. Agent Plus remains
   deferred to its own consumer implementation and acceptance pass. Its older
   backend is not a reference for Agent observation semantics.
4. **Operations:** select exact Mesh/Observer/client artifacts, then validate
   real-host disconnect/reconnect, owner and reader restart, route/catalog
   replacement, rollback, CPU/RSS/network costs and bounded child processes.
   Physical suspend and GUI/focus/action behavior require separate real
   acceptance. Synthetic and owned native tests do not close these gates.

See [Observer adaptation](observer-adaptation.md) and
[migration acceptance](migration-and-validation.md) for detailed domain checks.

Ordered native events, replay/status, digest-proof, WSS runtime/authorization,
shared fleet connection broker/pool, refresh/actions and command idempotence are
deferred. Their schemas and study examples are research material. They require
separate producer/transport acceptance before being advertised as capabilities.
`mesh-plus serve` is a single host-local bridge, not a fleet broker.

## Validation

Services that explicitly select the imported Mesh authority may use
`library_authority.LibraryMeshAuthority`. It reuses the canonical config
parser, route-health model/read method and bounded process encoder. Both parsers
consume the captured bytes without reopening their pathname. The default
`MeshAuthority` remains the process facade; route reports retain its writer.
Library reads reject special files and config/health inputs above four MiB,
admit at most one job per adapter, and enforce a five-second caller budget with
nonblocking health locks. Cancellation cannot deliver a late catalog or enqueue
replacement jobs while the old read runs. The owner must call `close()`; it
reports an unretired filesystem job instead of claiming completed cleanup.
These input limits belong to the explicit library adapter, not Host Mesh wire v1.
Failure does not fall back to a process authority or synthesize a local catalog.
No source facts, receipts, leases or collection are cached by this adapter.

Use Linux and Python 3.11+ with the declared package dependencies. Install into a
dedicated environment; the standalone gate needs no Observer packages:

```sh
rtk proxy uv venv .venv
rtk proxy uv pip install --python .venv/bin/python -e . jsonschema==4.26.0 ruff==0.16.10
rtk proxy .venv/bin/python scripts/check.py
```

`scripts/check.py` runs the unchanged lock/schema check, Read and Delivery
oracles, core runtime suite and lint using the caller's Python. CI runs this
same command on Python 3.11 and 3.13. It does not rewrite evidence files.

Install the exact reviewed Observer packages to run
`scripts/check.py --native`. The producer wheel inputs are recorded in
[the prior package tuple](evidence/package-candidate.json); they are test inputs,
not the managed operational tuple. The full suite uses owned disposable tmux and
SSH endpoints; `tmux`, `ssh`, `sshd` and Linux clock/IPC support are required.
Inspect skipped tests before claiming native acceptance.
The SSH fixture owns a disposable private directory under the user's home so
OpenSSH StrictModes remains enabled even when the environment lives under `/tmp`.

Add `--check-sources` only with reviewed sibling checkouts present. It compares
[source baselines](evidence/source-baselines.json) and supported pure producer
validators; it does not mutate those repositories. Current producers may evolve
without automatically changing a locked profile.

Packaging acceptance requires a fresh wheel, byte-for-byte runtime/schema parity,
and a standalone environment without Observer packages. Full wheel acceptance
uses separately pinned producer wheels. A changed source candidate does not
replace the deployed authority wheel until an explicit paired release/deploy.

## Evidence and historical documents

- [Handoff review](evidence/handoff-review.json): the prior a2 refinement pass and
  its candidate wheel, with explicit exclusions.
- [Source baseline manifest](evidence/source-baselines.json): reviewed producer
  source inputs; [initial design tuple](evidence/read-design-baselines.json)
  preserves the first inspection.
- [Implementation checkpoints](implementation-progress.md): cumulative history
  with counts and pending gates as they stood at each checkpoint.
- [SSH integration](ssh-plus-integration.md): current authority selection and
  retained configuration/history ownership. Managed deployment evidence lives
  in dotfiles `docs/evidence/2026-10-09-ssh-mesh-default.json`.
- [Design review](design-review.md), transport studies and older package reports:
  dated design/candidate evidence, including deferred features.
