# Observer API 2

Date: 2026-10-09. Prerelease producer contract. The Codex a3 packaged/native gate
is [accepted on both hosts](evidence/2026-10-08-codex-authority-acceptance/REPORT.md).
The [a4 saved-evidence repair](evidence/2026-10-08-codex-evidence-repair/REPORT.md)
precedes the [a5 core completion](evidence/2026-10-08-codex-observation-completion/REPORT.md)
with the same API/wires. The [a6 successor](evidence/2026-10-08-codex-observation-gaps/REPORT.md)
removes redundant publication after separate installed/native and scoped
operational acceptance. The following
[a9 Claude gate](evidence/2026-10-08-claude-interactive-observer/REPORT.md) preserves these
interfaces and adds passive Claude discovery/monitoring on Snap. The
[a11 retention gate](evidence/2026-10-09-runtime-only-retention/REPORT.md) preserves
the same interfaces and bounds disappeared unsaved memory; normal read
CLI/services select a11. The writer remains independently selected at a16.
This document supersedes
[API 1](api-v1.md) for new read clients. No old-wire converter is supplied.

The [Claude contract alignment review](claude-read-contract-review.md) settles
the shared read contract for interactive Claude implementation and independent
client development. API 2, snapshot/watch wire 4 and service protocol 2 fit the
accepted scoped-registration design without new wire fields or enum values.
The a9 gate separately accepts native behavior and operational selection;
interface conformance alone does not establish those facts.

## Interfaces and ownership

The [ownership specification and source audit](observation-boundaries.md)
clarify core/model/adapter/engine, local service, mesh and read-client boundaries.
The implemented internal extraction preserves this contract. Native refresh hints,
read push and user-facing notification delivery are separate concerns; this
read API supplies no terminal/window matching or public attention-event stream.

| Interface | Version | Entry point |
| --- | --- | --- |
| Pure read API | 2 | `agent_observer.public`, `agent-observer api` |
| Snapshot / sampled watch | 4 / 4 | `snapshot`, `watch`, bundled JSON Schemas |
| Cached pull / push | service protocol 2 | `agent-observer service snapshot/watch/status` |
| Explicit local New / Resume | separate writer wire 2 | `agent-observer-write prepare/execute/enter` |

The pure read facade exports validators, selectors and schema descriptors only.
It does not import collecting or action modules. Collection authenticates an
existing provider endpoint or provider-owned session registration; it neither
starts a provider nor reads terminal attachment or tmux state. Codex history is
read through its daemon; Claude history projects bounded native transcript/SDK
metadata without retaining conversation contents. The reusable core engine owns
reconciliation and evidence leases; the service hosts collection helpers and
read fan-out. Clients own provider actions,
TUI lifetime, terminal placement and viewers. Networking is a separate component.

The implemented providers are Codex and Claude. Claude observation is accepted
on Snap through its independent native gate; new Claude write selection still
returns `unsupported_provider`.
Provider support binds required contracts, with versions/hashes as diagnostics
and executable/incarnation guards.

## Discovery and monitoring

Identity is the exact scoped tuple `hostScope/provider/namespace/nativeIdKind/nativeId`.
Codex `nativeIds.threadId` equals the identity's thread ID.
`nativeIds.sessionTreeRootId` is independent tree metadata and does not merge rows
or prove a child. Native classification gives `kind=user/child/unknown`; default
list hides only positively classified children. Unknown kinds remain visible.

Each row contains title, recorded cwd, workspace/project facts, creation time,
conversation activity and latest turn outcome. `hasSavedHistory` reports positive
saved identity independently of runtime state. `inventory` records saved-catalog
evidence or runtime-only membership; it does not classify lifecycle or grant action authority.
There are no common worker, terminal attachment, client binding or Claude-job fields.

Shared row meanings are provider-independent:

| Runtime | Phase | Meaning within the source's declared scope |
| --- | --- | --- |
| running | working | Current native runtime; agent is doing work |
| running | blocked | Current native runtime; typed approval/question input is required |
| running | waiting | Current native runtime; agent awaits the next prompt |
| running | unknown | Runtime is established; work phase is not |
| parked | null | Positive saved identity and the adapter's reviewed predicate establish no current runtime, subject to declared assumptions |
| unknown | unknown | Runtime is unavailable, ambiguous, unsupported or stale; saved identity may still exist |

The Codex adapter supplies these meanings through its owning daemon:

| Current Codex native status | Runtime | Phase | Blocked reasons |
| --- | --- | --- | --- |
| active, empty valid flags | running | working | empty |
| active, known wait flags | running | blocked | approval, question, or both |
| idle | running | waiting | empty |
| systemError | running | unknown | empty; finite native runtime error reason |
| notLoaded plus readable saved identity | parked | null | empty |
| missing/conflicting/stale/unsupported state | unknown | unknown | empty |

Runtime and phase are evidence records: value, source, health, observedAt,
reason and clock; stale records may keep lastKnownValue. Known phase requires
current running evidence from the same native sample. Parked requires positive
saved identity and phase null. A parked sample that expires becomes runtime
unknown and phase unknown, preserving its original clock and last-known parked
fact. Missing loaded membership and terminal exit alone never establish parked.
Unknown wait flags preserve known active runtime but leave phase unknown.

Each adapter owns its native predicate; clients consume the normalized facts and
declared limitations. They do not repeat daemon queries or native PID checks.
The installed Claude adapter uses authenticated interactive registrations and
status. Parked requires positive saved identity plus a
healthy bounded native scan with no matching live incarnation or relevant
unresolved conflict, under the accepted registration assumption. Normal
exit, crash, Resume, UUID switches, duplicate contexts and cold start have native
proof with Agent View on/off. Failed/lost live registration can cause
false parked, including after source recovery; declare that limitation. Native
PID/birth checks remain private authentication, never public attachment handles.

Conversation activity has its own native clock and health. Collection, rename,
Resume, enrichment and lease renewal never move it. Empty conversations have no
activity clock. Human age is computed when displayed; stale age uses lastKnownAt
and stays visibly stale. Read ordering is blocked, waiting, working, then
unknown/parked, with newest conversation activity within each group.

## Scope, bounds and failure

Each source declares namespace/config selector, authenticated runtime diagnostics,
capabilities, independent saved/runtime coverage, errors, limitations and nullable
`discovery` query metadata. Codex discovery declares database-only catalog mode,
all ten source kinds within the native non-archived catalog, 1000 catalog rows,
up to 512 loaded/runtime rows by default,
1000 parked-history rows, 64 pages, 2 MiB native message bound and whether parked
conversation clocks are collected. Exact writer preflight declares its one-row
query separately. Unavailable source placeholders may have discovery null.

Runtime coverage scope is `daemon_threads` for Codex. Catalog and complementary
loaded inventory are sampled independently. Every positively running candidate
is protected before parked-history limits. Bounds, unreadable summaries and
unknown status make coverage partial; healthy sibling facts remain current.
Database-only placeholders without a readable summary remain unresolved.
Direct reads with an unavailable daemon return no current rows and finite source
failure; they never fall back to a private store. Existing watch/service rows may
remain stale under bounded retention.

Claude keeps runtime scope `provider_sessions`. The installed interactive adapter's
runtime coverage is `partial`, with reason `interactive_registration_assumed`
and limitations `interactive_runtime_only`, `native_registration_assumed`,
`unregistered_interactive_runtime_unproved` and `background_runtime_unsupported`.
These describe supported interactive observation rather than all Claude runtime
contexts. A healthy bounded scan within that scope may support a parked fact;
partial all-context coverage does not itself invalidate positive row evidence.
Detected read faults, bounds, ambiguity and expiry still prevent an affected
negative assertion. Source health, coverage and per-row evidence are separate.

Capabilities declare usable evidence dimensions within the configured context;
they are not exhaustive membership or action permission. Clients preserve
unknown/stale facts and source coverage even when some dimensions are supported.
Current scoped parked rows, unsupported contexts and stale unknown rows use the
same shared fields; consumers handle those facts without provider-specific inference.
Background runtime remains unsupported. Old background histories are outside the
user's forward interactive workflow and require no legacy compatibility repair.

Partial coverage may retain a disappeared unsaved runtime-only identity as stale
unknown, with original clocks and `retained_after_gap`, while a direct read omits
it. A11 retires this memory at the original accepted runtime lease: 90 seconds
on Snap and 60 on Starship at the selected cadence. Partial samples, metadata
refresh, heartbeats and delivery cannot slide that deadline. Direct sampled watch
uses a fixed 60-second bound from collection start, applied at the next sample.
Current rows and positive saved identities are protected; exact fresh
reappearance establishes new evidence. Retirement is omission of stale memory,
never a parked/ended assertion or action authority. The
[shared-core retention record](runtime-only-retention-follow-up.md) binds the
policy, bounds and native acceptance. Row/byte limits remain independent.

Wire object fields, versions and enum values are closed and strictly validated.
Evidence `source`/`reason`, coverage reasons, errors and limitation codes use the
bounded code syntax rather than a closed enum. Clients tolerate unfamiliar valid
codes, preserve them for diagnostics and branch on state/health/coverage fields.
Adding a diagnostic code does not change runtime meaning or authorize a new
predicate. New wire fields/enums or incompatible shared semantics require a
versioned contract and clean rejection; no silent extension or converter.

## Pull and push

Direct snapshots and sampled watch use the same projection as service workers.
The fast runtime cycle and slower history/enrichment cycle have independent
receipts. Codex's fast cycle also samples saved-thread daemon state. Claude's
interactive adapter refreshes disposition for positively saved UUIDs without
rerunning the whole history SDK scan. Native runtime evidence obtained during
metadata work is accepted under the short runtime lease and sample ordering
rules; metadata-only refresh cannot renew state.

A history sample that also contains current runtime evidence updates both
receipts before one published view. Their leases remain independent. View
revision counts publications, not native events; genuine coalescing still
requires gap/resync handling.

Cached snapshot and watch share one published view. [Protocol 2](service-protocol-v2.md) preserves service
identity, monotonic view revision, per-connection sequence, clock domain and
component leases. Heartbeats do not renew collection facts. Gaps, expiry and
incarnation changes preserve uncertainty and old clocks; clients reconnect and
request a resync rather than infer missed events. Push is sampled read fan-out,
not lossless native event replay or a notification-completion guarantee.

## Writer boundary and client migration

Writer preparation is passive and returns an explicit TTY handoff. `execute`
revalidates and still reports `prepared/effect=none`; only `enter` replaces the
foreground process with native Codex New/Resume. New identity is pending until
native discovery. Exact Resume uses uncapped `thread/read` and passes threadId,
never a catalog position, title, cwd guess or tree-root substitution. It guards
cwd/config, executable/settings and owning incarnation between preparation and
entry. Saved/live disposition changes alone do not invalidate exact identity.
The [saved-evidence repair](codex-evidence-repair-plan.md) additionally requires
an explicitly non-ephemeral summary and successful metadata-only stored-history
pagination before Resume preparation/revalidation. Empty history is allowed;
unproved persistence fails with `resume_saved_history_unproved`. Native path,
title, cwd and an activity clock do not substitute for this proof.
A distinct thread/tree-root TUI route returns `session_tree_entry_unproved`
until its native action target is independently accepted.

The [client handoff](api-v2-client-handoff.md) identifies the explicit installed
candidate and separate consumer/selection gates. Clients must rebuild against
wire 4/protocol 2, treat parked phase as null,
consume blockedReasons as a set, distinguish saved existence from running state,
and own attachment/action validation. Agent Plus implementation and managed
consumer selection are separate gates. Tmux Plus is unchanged.

Read-client implementation can begin against this settled contract and synthetic
conformance examples, using the independently accepted a11 producer.
Native claims and consumer rollout use an accepted producer artifact; planned
behavior in a fixture is not deployed behavior. Attachment/actions and public
notification events remain separate contracts. API 2 remains prerelease; this
review settles this pass, not an indefinite promise that future APIs cannot change.
