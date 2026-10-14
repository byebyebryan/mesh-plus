# Idle work simplification plan

2026-10-14. Status: reviewed investigation and proposed execution sequence.
Runtime implementation has not started; the current request is planning first.

## Decision and evidence limits

Optimize unchanged-work paths while preserving current observation cadence and
freshness. Retain SDK 1, preparation interface 1, lock revision 4 and all accepted
wire/schema bytes. Keep SSH and existing serialization. Preserve provider-neutral
Mesh transport and Observer-owned native/domain/desktop interpretation.

[Mesh findings](evidence/2026-10-14-idle-profile/README.md) link the
[owning Observer evidence](https://github.com/byebyebryan/tmux-observer/blob/ff6a163/docs/evidence/2026-10-14-idle-profile/README.md).
Live a7/a15 local cgroups measured 3.730% of one core over three minutes; the
empty-roster fixture still measured local owner plus Fleet 2.650%. These scopes
exclude remote host/bridge costs where stated. Profile counts and wall-time
hotspots are not CPU attribution, kernel wakeup counts or proven removable work.
The 60-second serial fixture runs do not establish upgrade savings/regressions.

Source baselines are Mesh main `3b7582d` and Observer main `7e14d79`; diagnostic
branches are Mesh `bad8af8` and Observer `ff6a163`. Observer CI at `ff6a163` passes
(run 38527040823), following the preserved grouped-refresh failure at `aed331e`
(run 38526645393). A green subsequent run does not resolve that race.
Mesh's diagnostic checkpoint `bad8af8` passes (run 38527143127).

Three corrections to the initial optimization sketch matter:

- Attachment collection already receives the accepted owner roster as its opening
  generation/reference bracket. Its remaining client/PID/closing checks are not
  automatically redundant; there is no free second-roster collection to remove.
- Fleet already caches its prepared projection. Frequent `project_changed` calls
  are dependency checks, not equally frequent full rebuilds.
- Independent Reader, guard and native public boundaries deliberately validate
  mutable inputs. Validation counts alone do not license skipping those checks.
  Fleet never calls Mesh current(), so PreparedReadGuard is not the shortcut.

## Sequence and decision gates

| Stage | Owner | Concrete deliverable | Gate |
| --- | --- | --- | --- |
| S0 | Mesh/Tmux diagnosis | Classified refresh race and deterministic causal trace | Correct success and revocation scenarios established |
| S1 | Mesh measurement | Callback/deadline/validation attribution with pinned inputs | Name the actual repeated work and its cost |
| S2 | Mesh | One isolated deadline scheduling prototype | Fewer callbacks plus repeatable CPU reduction, unchanged guarantees |
| S3 | Tmux Observer | Exact unchanged-host native-document reuse prototype | Cache hits remove admissions without changing validity or ownership |
| S4 | Tmux Observer, conditional | One native command consolidation prototype | Fewer launches with identical consistency/passivity coverage |
| S5 | Integration | New private tuple, installed gates and final measurements | Independent review before release or managed selection |

S0 blocks merging changes that affect control or deadline scheduling. S1 can run
alongside S0 because it is bounded instrumentation, not a behavior change. S2 and
S3 can be developed independently against fixed package inputs after classification;
qualify each separately before combining them. S4 proceeds only if remaining owner
cost justifies its complexity. Stop after a failed value gate rather than growing
a general scheduler/cache framework to rescue a weak result.

## S0: explain the refresh association failure

Instrument the disposable grouped-refresh test, not production services. Capture
bounded ordered events: Reader ID, delivery epoch/status/error, native scope and
publisher, publication/queue admission, control creation/send/reply/poll bindings,
ticket transitions and original attempted/accepted counters. Do not capture
terminal contents, environments or credentials. Clock comparison stays inside the
owned same-clock fixture; do not subtract remote-host timestamps.

Determine whether a legitimate gap/rebind invalidates the control, a false runtime
rebind occurs, or the success fixture's acknowledgement permits a race. The current
barrier acknowledges subscription consumption; that alone is not proof that all
later native/projection/control associations are established.

Deliver deterministic cases for unchanged-scope success, control reply before
Mesh-confirmed post-request acquisition, genuine gap during refresh, publisher
replacement and delivery-epoch replacement. Success requires the original valid
binding and the existing post-request source confirmation; genuine revocation must
still fail. Fix only the owning defect after its cause is established. Do not
remove the binding comparison, expand production budgets or increase fixture
cutoffs merely to obtain green CI. Retain the original failed acceptance record.

## S1/S2: fewer Mesh scheduling callbacks

Measure synchronous event-loop turns, timeout callbacks, live waiting operations,
actual frames/bytes, proof/cached acquisition counts and validation calls. Async
coroutine resumption counts are not operation counts. Separate counters/profiling
from uninstrumented CPU runs. Keep a no-change baseline for attribution overhead.
Reader host waits and `within_deadline` independently recheck BOOTTIME at up to
100 ms; establish their contribution before committing to a scheduler abstraction.

The first design candidate is one **owned expiry checker per active event loop**,
not one repeatedly awakened waiter per operation. Waiters wake on IO completion
or their own expiry; do not broadcast a pulse that wakes every waiter every tick.
Retain at least the current BOOTTIME recheck responsiveness. Registration, removal,
last-waiter shutdown and loop teardown must have explicit ownership, bounded
storage and no surviving background task. Avoid implicit process-global services
or a public lifecycle API merely to share a timer.

Compare that small prototype with the existing helper. A native BOOTTIME timerfd
is a secondary option if measured callback overhead warrants it. Linux timerfd
can be monitored through select/poll/epoll and CLOCK_BOOTTIME includes suspension;
Python's native timerfd APIs start at 3.13. Mesh supports Python 3.11+, so this
option needs an explicitly tested fallback without raising the minimum version.
Do not add ctypes/C bindings or another dependency solely to avoid that fallback.

[Python event-loop clocks](https://docs.python.org/3.14/library/asyncio-eventloop.html#scheduling-delayed-callbacks)
use the loop's monotonic clock. Replacing current BOOTTIME checks with an ordinary
long asyncio timeout is not proof of equivalent suspend behavior. See
[Python timerfd support](https://docs.python.org/3.14/library/os.html#timer-file-descriptors)
and the [Linux timerfd interface](https://man7.org/linux/man-pages/man2/timerfd_create.2.html).
These references establish mechanisms, not a measured recommendation to select one.

Add focused clock-jump/pending-IO tests before promotion: BOOTTIME advances while
the loop clock does not; completion and deadline occur together; validation ends
late; caller is repeatedly cancelled; pending subscription reads survive an
ordinary proof boundary but close on final retirement; and new leases cannot hide
gap/rotation revocation. Existing retained-view expiry tests are not sufficient
proof of pending-operation timer correctness. Keep original setup/proof/frame/
silence and catalog budgets. Test minimum Python and the deployed Python version.

## S3: narrow native-document reuse in Observer

Start with exact unchanged-host reuse, not a broad fact/receipt cache. A full Fleet
replacement includes every host even when only one host advanced. After ordinary
Mesh guard admission, Observer may be rebuilding an identical native document for
an unaffected host. Count the actual exact-match hit rate first.

A hit requires the same native source/publisher/clock and delivery binding, a
bounded supported plain-JSON input, and exact equality of the entire reconstructed
native frame with a privately retained, previously validated frame. Version,
viewRevision, accepted counter or identity alone is not an equality proof. Changed
header, receipt, rows, metadata, generation, scope or binding takes the normal
full native admission path. No input aliases or public mutable exports survive
inside the cached representation. Prefer the already-retained owned frame and
its checked sizes; any extra storage is bounded to one entry per host and counts
against existing retained-memory accounting. No old generations accumulate.
Fall back rather than guessing about exotic
Python values or unsupported ownership.

Even on a hit, always update/recheck current Mesh delivery status, receipt/proof
binding, queue-consumed expiry, source counter ordering, historical/warming state,
control association and memory accounting. Native document reuse grants no new
validity. Gap, disconnect, capacity failure and rebind retire the optimization.
Require full output equality against the legacy path over the same captured
frames/clock, including deliberate input mutation and same-revision changed data.

Only if this narrow path wins should a larger internal separation of immutable
facts and changing receipt headers be designed. That would need its own proof of
content equality, lifetime, resource bounds and semantics. No new checked-frame
public API or consumer migration is a prerequisite for this first experiment.

## S4: native commands, only if still worthwhile

The existing two-second owner cycle uses the roster as the attachment opening
bracket, then reads/rechecks native clients, PID births, identities and generation.
Explore whether the owner closing batch and attachment opening-client read can
share a passive tmux command process. This is a hypothesis, not an accepted
three-command implementation or a promised proportional CPU saving.

Keep separate output/sample coverage, original conservative sample start, the
single absolute acquisition budget, final generation/session checks and both
client/PID-incarnation comparisons. Test detach/switch, PID reuse, server restart,
empty/no-server transitions, malformed output, command capacity and legacy tmux
fallback. No hooks, control-mode attachment, server/session creation or action
semantics enter the producer path. Public collect() and wire response shapes stay.
Drop this candidate if sharing requires substantially more state or weakens the
independent association result for a small measured benefit.

## Measurement and acceptance

Use exact committed runtime inputs, the same Python/dependency versions and fixed
cadence/leases/proof intervals. Preserve old artifacts and counter logs. Record
host power state and interfering activity rather than silently tuning the host.

- Screen each candidate separately with ABBA ordering at 120 seconds per case for
  empty and two-session-per-host headless fleets. Match foreground requests, source
  cadence, acquisition outcomes and native facts; allow only window-edge counter
  differences explained by phase. Counters remain out of timing runs.
- For a promising candidate, predeclare two ABBA blocks per primary case at 300
  seconds per run. Report block spread and absolute CPU percentage points. A
  repeatable 20% Fleet-CPU reduction is an initial target, not a promised result;
  require the saving to exceed baseline variability. An inconclusive result stops
  promotion rather than triggering unbounded reruns.
- Qualify desktop-on small rosters, 12-session rosters, a bounded active-update
  workload, zero/one/multiple downstream readers, explicit refresh, and failure/
  recovery separately. Preserve existing warm-RPC/update/resource limits and reject
  a meaningful active-workload regression. Do not save CPU by dropping samples,
  delaying discovery or processing fewer required frames.
- Report owner self/child, Fleet/local bridge, SSH and remote bridge CPU separately;
  distinguish cgroup memory, sampled RSS/PSS and peaks. Keep SSH server/helper and
  tmux-server exclusions explicit; do not call partial accounting whole-fleet CPU.
- Run canonical Mesh core/optional WSS, exact installed Tmux integration, contract/
  schema checks and isolated wheel verification. Simulated suspend tests establish
  their stated scope; physical suspend needs separate acceptance before that claim.

## API, packaging and scope

S0-S3 target implementation changes with unchanged public signatures, wire bytes,
source cadence and callback semantics. A prototype needing a normative contract
change stops for separate review; do not regenerate the lock to accommodate it.
Tmux's worker also enforces an exact Mesh package version. A new Mesh candidate
therefore needs a separately reviewed matching Tmux pin/metadata/CI checkpoint;
stable SDK 1 does not mean arbitrary package versions are auto-accepted. Keep that
small compatibility update distinct from API rewiring and from live adoption.
Allocate new private runtime versions at build time, synchronizing distribution
metadata and runtime banners; never overwrite a previous wheel or reattribute
its acceptance. Diagnostic/doc changes alone need no runtime release.

Agent development, Plus frontends, SSH Plus authority, chezmoi, release publication
and deployment are excluded. Agent pure-profile compatibility remains covered by
Mesh's portable tests without changing the developing Agent checkout. A slower
polling/quiet mode is a separate explicit latency/freshness decision, considered
only after transparent work reduction; empty fleets must still discover sessions.
