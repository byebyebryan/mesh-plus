# Owner profile conformance

The opt-in `mesh_plus.testing` interface v1 is separate from SDK interface v1
and the frozen wire contract. It uses standard-library unittest suites, trusted
caller-supplied factories and installed package resources. No plugin discovery,
provider collection or desktop dependency is introduced.

```python
from mesh_plus.testing import profile_suite, run_suite

report = run_suite(profile_suite(make_profile, domain="agent"), domain="agent")
assert report["ok"], report
```

`make_profile(domain)` returns the owner's reviewed pure `StateProfile`. Each
case gets a fresh instance. `profile_cases(domain)` supplies the curated baseline:
six Tmux and seven Agent cases, including the reviewed stale unsaved runtime
case. It covers 90 evaluation points, with exact native state, identities,
receipt facts and effective rows.
Expectations were fixed with released a11 and pinned native facades; they are not
computed using the tested profile. It excludes reserved WSS/events studies.

Owners can pass `cases=` containing independently prepared `ProfileCase` values:
`case_id`, `domain`, `response`, `native` and `states` keyed by host, ordered
`identities`, and `selections` containing `now_ms` and expected `rows`. Each native
state has the fields of `NativeState`, with JSON arrays for records and receipts.
Case IDs use lowercase letters, digits, underscores or hyphens. Empty suites
and evaluation lists are rejected. Validate owner fixture provenance separately;
do not derive the expected oracle by invoking the profile being tested.

`run_suite(suite, domain=...)` runs synchronously outside an active async runner.
It returns `mesh-plus.conformance.v1`, interface/SDK versions, fixed descriptor,
corpus digest, stable case IDs, counts and `ok`. Every selected case must have an
explicit passing outcome. Failures, unrelated exceptions, skips, expected failures
and unexpected successes cannot certify the suite. Failed subtests are recorded
under their parent case without parameters or messages. It excludes payloads and
exception messages.
For local tracebacks, run the same suite with `unittest.TextTestRunner` instead.

The bundled `mesh_plus.testing.sample.Profile` is an independent fixture
implementation, not a production native validator. Passing it proves the kit
and transport boundary; it does not certify arbitrary provider semantics.
Owner-native validation remains mandatory. The kit is never imported by ordinary
Mesh entry points and leaves `mesh_plus.api` signatures/exports unchanged.

`network_suite(make_profile, domain=...)` adds ten owned IPC/remote-proof
lifecycle cases per domain. Its route connector test uses IPC and does not claim
SSH carriage. Optional `publisher_factory(domain, host, source, profile)` returns
a disposable fixture publisher with the sample publisher's `frame`,
`state_profile`, cached `wrap()`, a `changes` notification queue and watcher-count surface plus the normal Bridge
methods. This is a test scenario, not a requirement on production adapters.
The default scenario is Mesh-owned and accepts the owner's profile without
inheritance. Update/restart scenarios mutate a copied native frame and notify
`changes`, then observe delivery through Bridge, IPC, Reader and ReadGuard. Both
local and remote-proof bindings run. Updates must arrive before the long periodic
proof interval, preserve original receipts and keep the connection epoch.
Publisher restart must visibly revoke rows, reconnect and deliver an accepted
resync with a newer epoch. These cases use IPC; actual SSH carriage remains the
separate suite below.

For actual carriage, explicitly import `ssh_suite` from `mesh_plus.testing.ssh`.
It owns a localhost daemon, private keys, forced fixture command and repeated
poll/watch connections; it needs Linux/OpenSSH and a non-root user. Missing tools
fail visibly. The remote fixture uses the independent sample projection; the
client uses the injected owner profile. It does not test an owner's native
publisher deployment. Both the IPC and SSH suite can be passed to `run_suite`;
do not mix domains in one report. Custom pure case input digests are included.

## Optional WSS acceptance

The existing portable kit certifies its listed profile and IPC/SSH scenarios; it
does not implicitly certify a new carrier. The a14 optional WSS backend has a
separate strict installed gate, `scripts/check-wss.py --installed --native`, with
carrier authentication, mixed-fleet selection and lifecycle cases. See
[WSS operations](wss.md). Neither gate selects live artifacts or certifies WAN,
physical suspend or provider collection.

