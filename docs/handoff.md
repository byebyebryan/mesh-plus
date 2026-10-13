# Mesh Plus integration handoff

## Current disposition

Latest publication is [a15](evidence/2026-10-12-a15-release/README.md), with
SDK interface 1, optional WSS and the generic cached publisher/factory seam.
Release and installed-byte acceptance do not select an owner or live endpoint.
The combined shared launcher now selects both accepted owner factories. The
[coordinated performance/WSS pass](performance-and-wss-plan.md) records the
retain-SSH decision after isolated trials and measurement; [its ledger](evidence/2026-10-12-performance/README.md)
records current evidence. Ordinary readers remain on IPC/SSH.

The subsequent [controlled benchmark pass](controlled-performance-plan.md) is
complete: [192 exact-work cases](evidence/2026-10-12-controlled-performance/README.md)
compare IPC/SSH/WSS with a pinned pure Tmux profile, without Agent development
inputs. It records a multi-upstream sharing benefit and rejects a copying
prototype; there is no runtime release or new downstream wiring prerequisite.

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

The released **0.1.0a10** wheel at
`3684fe083c0ab5af3c74aa27dff169e5764489f5` adds subscription-admission
cancellation cleanup and CLI shutdown ownership before socket publication.
Its SHA-256 is `c9fecd77e3ea181d43447784824616232874cfc9ead12a30460d0682bdc3684d`.
Fresh installed acceptance passes 75 standalone and 108 native/SSH tests against
Tmux Observer a5 / Agent Observer a16, with no skips. It is selected on both
endpoints. The original private a10 wheel remains separate evidence; only its
unchanged Reader/Client/transport bytes are shared with long rotation soaks.

The **0.1.0a11** SDK checkpoint adds explicit pure profiles, preserves legacy
entry points, and retires all snapshot host tasks before returning cancellation.
See [package acceptance](evidence/2026-10-10-sdk-v1/README.md) and
[independent networking adoption](sdk-owner-handoff.md). It does not change the
a10 live selections or certify owner adapter extraction.

The completed [SDK maintenance plan](sdk-maintenance-plan.md) covers portable
owner conformance, compatible diagnostics, measured internal refinement and a
separate package checkpoint. Observer adoption remains independently schedulable.

That sequence is accepted in **a12**: installed owner conformance, explicit v2
SDK diagnostics and cached assessment, matched measurements selecting no core
optimization, and an immutable package. See the
[acceptance record](evidence/2026-10-11-sdk-maintenance/README.md),
[kit](conformance.md) and [diagnostics](sdk-diagnostics.md). The frozen runtime
SDK/wire boundary stays unchanged, and no live selection is made by this release.

The **a13** follow-up requires explicit passing conformance outcomes and exercises
publisher updates/restart through owned IPC, including remote nonce-proof binding.
See [follow-up acceptance](evidence/2026-10-11-conformance-followup/README.md).
This keeps the same SDK v1 and does not select live artifacts or migrate owners.

The [WSS roadmap](wss-roadmap.md) research loop is complete; see the
[study outcome](../studies/wss/outcome.md) and [promotion proposal](../studies/wss/promotion-proposal.md).
Authenticated poll/push and both profiles pass in isolated loopback fixtures.
The a14 source/private-wheel candidate promotes optional native WSS through the
[reviewed addendum](../contracts/wss-v1/contract.md) and lock revision 2. See
[WSS SDK/configuration](wss.md) and the [promotion plan](wss-promotion-plan.md).
The [promotion acceptance](evidence/2026-10-11-wss-promotion/README.md) binds the
a14 private wheel, installed cross-Python/native gates and exact exclusions.
The existing Read/Delivery and native schemas remain byte-identical. WSS owns
immutable mixed-backend selection, mTLS, bounded carrier IO and explicit local-file
job ownership. Source/private wheel acceptance is separate from release and real
fleet selection; current owner and live pins remain.

Tmux rejects stale control bindings and reserves one retiring local bridge
handler alongside its active Reader. Eight installed native Mesh tests pass;
independent owned fixtures cover successful delivery and gap revocation. Agent
has a compatible ASCII validator fast path. The
[artifact checkpoint](evidence/2026-10-10-hardening-artifacts/README.md) records
exact new Observer/picker packages, refresh attribution and headless resource
acceptance. The [operational study](evidence/2026-10-10-operational-hardening/README.md)
keeps private-input measurements and production-budget lifetime gates separate.
Paired live selection, recovery, rollback and reselection pass in the
[hardening adoption record](evidence/2026-10-10-hardening-adoption/README.md).
Final resource and installed SSH/Tmux checks pass; Agent cached delivery passes
separately, with Agent Plus migration excluded.

The 2026-10-10 adoption selected a10 for the public CLI/transport and Tmux
Observer 0.6.0a5 / Plus 0.12.0a5. Agent uses separate a16 reader and bridge
environments, each with SDK a10. SSH Plus retains its independent shared
authority SDK a6 root. Agent's 0.5.0a15 collector and 0.4.0a16 writer retain
their prior selections. Source, installed bytes, collector
incarnation and foreign managed checkout preservation are separate checks.
See the [coordinated adoption record](evidence/2026-10-10-fleet-adoption/README.md)
for dated gates and limits; the [reliability plan](reliability-and-measurement.md)
records proactive channel rotation, cancellation-safe cleanup and measured costs.
Earlier managed SDK roots remain available for paired rollback. Graphical input,
physical suspend and further consumer migrations remain separate acceptance
work. Production-budget rotation is accepted only by the explicit per-host
observations in each dated lifetime report.

The [changelog](../CHANGELOG.md) records version differences. The
[Agent SDK checkpoint](agent-integration.md) records the a4 source checks and
the historical exact-HEAD check limitation. The
[review evidence](evidence/handoff-review.json) binds the prior a2 pass to source,
tests, candidate package bytes and the unchanged contract lock. The
[operations pass](mesh-operations.md) and [lab evidence](evidence/mesh-lab.json)
describe a3 diagnostics, synthetic workloads and the optional pool proposal. Older evidence
files describe their own checkpoints; they do not certify changed source bytes.

The published a15 prerelease adds the [generic cached publisher and installed factory
seam](publisher-api.md). Observer owners can replace reference publication through
one explicit trusted Python map for local IPC, fixed SSH and optional WSS.
[Installed candidate acceptance](evidence/2026-10-11-publisher-factory/README.md)
passes both profiles over IPC/fixed SSH/WSS and a10 interoperability.
Native/resource/managed acceptance remains owner-specific; no live pins change.

The [coordinated performance/WSS assessment](performance-and-wss-plan.md) retains
SSH against Tmux a7/Agent a20/Mesh a15; its private Agent a21 candidate is not
promoted.
Both publisher factories are already deployed; shared launcher composition is
no longer a pending prerequisite. Ordinary transport selection remains SSH.

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

`Client` accepts a pure payload validator. SDK interface v1 additionally carries
an explicit bound codec in `Endpoint`, with `profile=` threaded through configured
IPC/SSH, Reader, reconstruction, validation and guards. Independent profiles need
no reference adapter inheritance or bound-method discovery. Existing constructors
retain the reviewed reference compatibility path. The
[SDK interface specification](sdk-api.md) defines the exact surface and gates.

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

Tmux's producer/coordinator integration and paired a10 selection are accepted in
the hardening adoption record above. Agent's independently selected a10 transport
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

Ordered native events, replay/status, digest-proof,
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
  in [SSH Plus evidence](https://github.com/byebyebryan/rofi-ssh-plus/blob/main/docs/evidence/2026-10-09-ssh-mesh-default.json).
- [Design review](design-review.md), transport studies and older package reports:
  dated design/candidate evidence, including deferred features.

## Owner operations and relocated deployment evidence

The [SDK independence review](sdk-independence-review.md) preserves the initial
design and negative probes. The accepted additive
[SDK interface v1](sdk-api.md) separates networking from explicit pure profiles.
SSH Plus is the direct authority client; Observer work is confined to networking
interfaces. Plus migrations and producer policy are outside this Mesh pass.

Agent's bridge/reader selection procedure is now owned by
[Agent Observer](https://github.com/byebyebryan/agent-observer/blob/main/docs/mesh-read-client.md).
Paired Tmux installed recovery and rollback are owned by
[Tmux Observer](https://github.com/byebyebryan/tmux-observer/blob/main/docs/managed-operations.md),
with a public Tmux Plus frontend verifier. Mesh retains generic transport
`doctor`/`probe`, frozen authority and its existing artifact gates.
The [SSH default adoption](https://github.com/byebyebryan/rofi-ssh-plus/blob/main/docs/evidence/2026-10-09-ssh-mesh-default.json)
and [SSH facade adoption](https://github.com/byebyebryan/rofi-ssh-plus/blob/main/docs/evidence/2026-10-09-ssh-mesh-facade.json)
records have moved byte-for-byte to their authority consumer. They remain dated
acceptance, not proof of later runtime changes.
