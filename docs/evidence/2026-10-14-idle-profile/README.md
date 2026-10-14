# Actual Tmux idle cost and Mesh follow-up

2026-10-14. Diagnostic study, not a runtime change, release or deployment.
The [owning Observer receipt](https://github.com/byebyebryan/tmux-observer/blob/ff6a163/docs/evidence/2026-10-14-idle-profile/README.md)
binds live package roots, raw samples, controlled installed-runtime fixtures,
function profiles, instrumentation exclusions and reproduction.

A three-minute Snap sample of deployed Observer a7 / Mesh a15 reports **3.730% of
one logical core** in the local owner/Fleet service cgroups: Fleet 2.632%, owner
and native commands 1.098%. The stable SSH client accumulates zero CPU ticks.
There are two local and four cached remote sessions; remote host CPU and bridge
processes outside those cgroups are excluded. An overlapping 212-second cached
receipt check records 105 accepted owner samples with no native view revision change.
Fleet's revision changes five times, so this is not completely static global state.

Four single 60-second disposable IPC/localhost SSH cases show a substantial idle
floor: an empty two-host Fleet uses local owner/native commands 0.967% plus Fleet
1.683%. Two-session and larger-roster measurements retain that floor; twelve
sessions per host add cost. Desktop association adds work. These are diagnostic
observations with serial-run noise, not causal percentage savings or whole-fleet
resource acceptance. An expanded two-session case separately measures remote bridge
0.533% and SSH client zero ticks. Transport byte volume is not the leading signal.

The headless one-minute instrumented Fleet run records 366 protocol validations,
86 Mesh response validations, 86 Observer owner projections, 82 native document
admissions and **zero Mesh current queries**. The Mesh event loop runs 5,190
iterations, while the Fleet loop checks prepared dependencies about 1,206 times;
those checks are not all full projection rebuilds. Profiles use process-wide
CPython 3.14 cProfile wall time and include setup/cleanup. Counts and nonblocking
hotspots are diagnostic; blocking/inclusive time is not a CPU-share breakdown.

The native owner performs 31 native and 31 attachment collections, with 124
bounded native command invocations across that profiled lifetime. The same owner,
collector and attachment collector bytes remain in the measured private a8 wheel.
A single private a8/a18 case passes installed current-state/cleanup checks but is
not matched upgrade-performance evidence. Mesh's `within_deadline` helper is
unchanged, including its 100 ms BOOTTIME recheck; Reader has another 100 ms wait.
Loop iterations are not OS wakeup counts, and epoll waiting is not CPU busy work.

## Proposed next experiments

1. **Mesh scheduling:** consolidate redundant deadline/watch polling and callbacks
   while preserving BOOTTIME expiry, started-frame/absolute deadlines, cancellation,
   silence, ownership and post-resume revocation. Establish exact wakeup/callback
   attribution and a longer matched comparison before changing runtime code.
2. **Receipt-only validation:** identify repeated work within one admitted operation
   versus deliberate independent boundaries. Reuse checked owned state only with
   explicit mutation, expiry and cross-thread lifetime rules. Do not bypass native
   admission or mechanically select PreparedReadGuard in a path with no current calls.
3. **Observer floor:** separately consider native command consolidation and stable
   desktop-input work. Slower collection is an explicit freshness tradeoff owned by
   Observer; Mesh cannot silently change it or infer emptiness from missing samples.

Existing SDK 1, optional preparation interface 1 and wire/lock revision 4 stay
unchanged. This finding adds no downstream migration prerequisite. There is no
reason from these measurements to prioritize WSS/TCP or a compact payload format.
Agent, Plus, SSH Plus, ordinary services and chezmoi were untouched. Correctness
and authority checks remain in force; no implementation prototype is promoted.

The Observer hosted source gate passes, but the integration gate repeats the
previous grouped-refresh `stale_scope` test failure with unchanged runtime/tests.
The owning receipt preserves the failed run and leaves the cause unresolved.
Investigate that race before implementing timer/scheduling changes; the profiling
branches are not a fully green integration promotion. Successful diagnostic
measurements and Mesh's passing design/hosted checks retain their separate scopes.
