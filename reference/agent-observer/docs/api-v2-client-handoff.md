# API 2 client handoff

Date: 2026-10-09. Codex on Snap/Starship and Claude on Snap are independently
accepted against [0.5.0a11](evidence/2026-10-09-runtime-only-retention/REPORT.md).
Normal read CLI links and user services select a11 through the separate operational
gate. The preceding a9 interactive and a6 Codex acceptance retain historical bounds.
The preceding a5 thirty-minute acceptance retains its historical artifact bounds.
The normal writer retains a16. This handoff does not
select a consumer or authorize provider policy, frontend, terminal-runtime or
networking changes.

## Bind to the contract

Use [API 2](api-v2.md), snapshot/watch wire 4 and
[service protocol 2](service-protocol-v2.md). Writer wire 2 is independent of the
pure read facade. The [manifest](../artifacts/observer-0.5.0a11.json) identifies the
accepted candidate; provider release numbers are diagnostic provenance, not
support allowlists. Do not carry forward wire-2/wire-3 readers or protocol-1
caches. Reject unsupported input and rebuild the consumer cache from a new view.

Python read clients use `agent_observer.public` for bounded parsing, semantic
validation, exact identity selection and ordering. Service clients use
`service_public` plus `service_client.frames`, or independently implement both
schema and semantic checks. Other-language clients can obtain schemas with
`schema --kind snapshot|watch` and `service schema --kind request|frame`.
Both API descriptors operate without a provider or service.

The [state-push guide](state-push-design.md) consolidates complete-view baselines,
idle expiry timers, selection and semantic comparison. Its
[installed/native study](evidence/2026-10-09-state-push-refinement/REPORT.md)
revalidates the accepted state stream without changing public versions. Native
occurrence events and Kitty/D-Bus notification integration are deferred; they are
not read-client dependencies.

The [Claude alignment review](claude-read-contract-review.md) settles API 2/wire 4/
protocol 2 for the interactive-only adapter. The independent a9 native/artifact
and scoped operational gates accept it; a11 adds independently proved finite
unsaved retention within the same contract. The
[synthetic mixed-provider fixture](../tests/fixtures/contract-v4/claude-interactive.json)
remains useful for parser, selection, partial-coverage and expiry conformance.
Consumer source/native/deployment acceptance remains separate.

## Required consumer behavior

- Key rows by the complete host/provider/namespace/native-kind/native-ID tuple.
  Codex `threadId` is the exact thread; `sessionTreeRootId` is independent metadata.
- Treat running/parked/unknown as normalized native evidence within declared
  scope and assumptions. Codex's daemon is its authority; Claude has its separate
  native predicate. Clients do not query provider registries or validate PIDs.
  No tmux, TUI PID, cwd, title, loaded-list absence or completion callback supplies
  client-side runtime authority.
- Handle parked phase null and unknown phase evidence. Blocked reasons are a
  bounded set containing approval, question or both. Default urgency is blocked,
  waiting, working, then unknown/parked, with conversation activity newest first.
- Preserve missing/stale activity clocks. Display age from the event clock and
  current display time; collection, cache delivery and Resume do not change age.
- `hasSavedHistory` differs from runtime and inventory. Hide only confirmed
  children; unknown kinds stay visible unless a separately explicit UI policy
  says otherwise. Query bounds/coverage and stale source errors stay visible.
- Consume one service view for cached pull and push. Warm-up null is not an empty
  roster; gap/resync, silence, lease expiry and incarnation changes require
  conservative invalidation and a fresh guard/view, never native event inference.
- Keep local Git/root/relative-path/project facts separate from logical identity.
  Project keys can group rows across hosts without merging session references.
- Own user intent, terminal/TUI lifetime, tmux/Kitty placement, routing and viewer
  association in the client. Observation supplies no attachment or worker fields.
- Accept unfamiliar valid diagnostic/limitation codes while keeping wire fields,
  versions and state enums strict. Do not depend on an exhaustive coverage claim
  or discard every known row merely because its source coverage is partial.

Claude supports interactive working, waiting and typed approval/question waits.
Healthy native registration scans and positive saved identity can report parked
when no authenticated live interactive incarnation or relevant unresolved
conflict remains. This is the declared `interactive_registration_assumed` scope,
with partial runtime coverage and explicit limitations. A live session whose
registration failed/disappeared may be missed or falsely parked after recovery.
Consumers preserve that qualification; they do not build their own provider census.

Normal exit, forced kill, saved Resume, same-process UUID switches, simultaneous
live contexts, conflicting phase and Observer cold start are independently proved
with Agent View on/off. Background execution/attachment is unsupported. The two
old stopped recap job histories remain unknown because their pending-work data
is missing. They are outside the user's forward interactive workflow; no legacy
background compatibility work is required. The setup-only SDK candidate now has
positive saved discovery, but
its cwd, kind and age remain unavailable. Generic dialogs, nested child history
and Claude turn outcomes remain unproved. Source coverage stays partial.

Partial runtime coverage can briefly retain a disappeared unsaved UUID as stale
unknown with `retained_after_gap`, even when a fresh direct read omits it. A11
retires it at the original runtime lease: 90 seconds on Snap and 60 on Starship
at the selected cadence. Partial samples, history enrichment and heartbeats
cannot slide that deadline. Direct sampled watch uses 60 seconds from collection
start and applies expiry at the next sample. Current rows and positive saved
identities survive, with original conversation age. Clients preserve uncertainty
until replacement/resync and treat omission as observation-memory retirement,
never a native end/parked event or action permission. The
[retention record](runtime-only-retention-follow-up.md) binds the policy and proof.

Claude write selection remains unsupported by the new writer; the a16 writer is
selected independently and read acceptance grants no new action capability.
Parked never grants automatic resume, stop, approval or attachment permission.
Agent View settings and ordinary sessions were not changed by a11 selection.
Runtime refreshes authenticate saved identities without rerunning the history
SDK. Conversation metadata has a separate lease, and process liveness cannot
refresh its age. Native file hints can prompt earlier reads; a forced kill with
no file event falls back to the configured runtime cadence (30 seconds on Snap),
plus bounded collection time. Push distributes the accepted view, not every
native transition.

## Inspect the observation service

Use the selected read CLI for ordinary discovery and monitoring:

```sh
agent-observer api
agent-observer service api
agent-observer service list --host-scope snap
agent-observer service watch --host-scope snap --count 3
agent-observer list --host-scope snap --provider claude
```

The managed publisher is already running on each host. Cached pull and push use
the same view at `/run/user/1000/agent-observer/read.sock`. No subscriber starts
the publisher or falls back to direct native collection. For an independent
direct read, invoke `list` or `snapshot` without the `service` prefix. Direct
reads collect metadata anew and can take longer than cached reads.

For explicit artifact checks, use its immutable prefix:

```sh
candidate_prefix=/home/bryan/.local/share/agent-observer/0.5.0a11-b1b755c8df0d4676
"$candidate_prefix/bin/agent-observer" api
"$candidate_prefix/bin/agent-observer" list --host-scope snap --provider codex
"$candidate_prefix/bin/agent-observer" snapshot --host-scope snap --provider codex \
  --workspace-config /home/bryan/.config/agent-observer/workspace.json
"$candidate_prefix/bin/agent-observer" watch --host-scope snap --provider codex --count 2
```

Run on the owning host, replacing host scope with `starship` there. A direct read
does not start an unavailable daemon. For cached development, explicitly start
an owned foreground Observer publisher in another terminal:

```sh
"$candidate_prefix/bin/agent-observer-service" serve --host-scope snap \
  --provider codex --socket /run/user/1000/observer-api2-dev/read.sock \
  --workspace-config /home/bryan/.config/agent-observer/workspace.json
"$candidate_prefix/bin/agent-observer" service api
"$candidate_prefix/bin/agent-observer" service list --host-scope snap \
  --socket /run/user/1000/observer-api2-dev/read.sock
"$candidate_prefix/bin/agent-observer" service watch --host-scope snap \
  --socket /run/user/1000/observer-api2-dev/read.sock --count 3
```

The immediate endpoint directory must be canonical, same-user and private;
the publisher creates it if absent. Use the owning UID's runtime path. Stop this
explicit publisher with Ctrl-C; it owns only Observer work. Never pair a protocol-2
client with a historical protocol-1 endpoint. Subscriber reads do not autostart
a service or fall back to direct collection.

## Actions and acceptance boundaries

Actions and attachment are deferred from the completed observation scope. The
normal `agent-observer-write` still selects the historical a16 artifact and is
not this API-2 read handoff. A future action client must select and validate its
own accepted writer tuple; it must not infer writer compatibility from the
reader's version or link.

The separate API-2 writer prepares and revalidates an explicit local TTY handoff with
`effect=none`; only `enter` performs native New/Resume. New identity is pending
until native discovery. Exact Resume validates the requested reference through
native `thread/read` and metadata-only `thread/turns/list`, independently of
listing caps. An explicitly non-ephemeral summary and readable stored history
are required; failed/unsupported reads return `resume_saved_history_unproved`.
Missing activity alone does not reject saved identity. Consumer attachment/runtime
ownership remains external; remote routing belongs to the owning host/client.

The earlier [a4 writer acceptance](evidence/2026-10-08-codex-evidence-repair/REPORT.md)
accepts initialized saved/live Resume, repeated native entry and equal-ID fork
targeting. This observation pass adds no writer capability or selection gate.
Blank runtime-only Resume and distinct thread/tree-root TUI entry
are not accepted; blank runtime-only Resume fails with
`resume_saved_history_unproved` and distinct-ID entry fails with
`session_tree_entry_unproved`. Positive empty-history responses have controlled
coverage; native empty-saved TTY entry remains unaccepted. Offline
Resume is unavailable until an explicit action restores the provider runtime.
Do not convert observed running/parked state into automatic action permission.

Each consumer validates its own parsing/caches, ordering/age, uncertainty, exact
references and action routing against the unchanged candidate, then performs
its own graphical/device/terminal acceptance. A producer defect reopens an
Observer-only checkpoint. Agent Plus and Tmux Plus development remain separate;
there are no downstream repository edits in this handoff. Future terminal
observation/attachment can integrate tmux-observer through the client boundary.
The [a11 acceptance report](evidence/2026-10-09-runtime-only-retention/REPORT.md)
records the current separate Observer read/service operational gate.

An independent read-client pass may now implement schema/semantic validation,
exact-reference selection, age/attention presentation, mixed-provider views and
cached pull/push with gap/resync/lease handling. Use the accepted a11 artifact for
current behavior and the synthetic fixture for interface conformance. The
[Claude wrap-up](claude-observation-wrap-up.md) records supported scope, completed
gates and independent follow-ups. Actual New/Resume/attach, cross-host
clock/transport handling and user-facing completion
notifications require their separate contracts/proofs. Do not couple that client
pass to simultaneous Observer adapter edits or select a future artifact early.
