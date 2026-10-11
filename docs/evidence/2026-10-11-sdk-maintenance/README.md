# SDK maintenance package acceptance

2026-10-11 checkpoint implementing M0–M3 of the
[reviewed maintenance plan](../../sdk-maintenance-plan.md). Release a12 supplies
owner conformance and diagnostics; the matched performance study selected no
core optimization. This record does not select or deploy live artifacts.

- [Package manifest](package.json): source
  `b46a66d60fc236ba5daaa427e13e2ec7120d31d6`, wheel SHA-256
  `32b94130a3a4b22d105539b9c5a861adb7160791c5f15a4b8875814303972d10`,
  106,314 bytes and 49 source-identical runtime/schema/resource members.
- [Validation](validation.json): isolated installed wheel passes 100 standalone
  tests on Python 3.11 without Observer packages and 136 native/SSH tests on
  Python 3.14 with pinned Tmux a5 / Agent a16; no skips. Canonical gates pass
  lock/schema parity, 116 Read checks, 169 Delivery checks and lint. Source CI
  passes standalone/fault gates on 3.11/3.13. SSH Plus's 82 regressions pass.
- [External conformance](conformance-wheel.json): six installed suites, 31 cases,
  90 fixed semantic evaluation points and two deliberately broken external
  profiles detected, from a temporary working directory without checkout imports
  or Observer packages. IPC route binding and actual owned SSH are separate cases.
- [Differential comparison](differential.json): 12 frozen cases and 36 effective
  selections equal a separately installed a11 with the same native wheels.
- [Synthetic fault lab](faults.json): source isolation, deadlines, cancellation,
  publisher restart, reconnect, push acquisition and cleanup pass. The fault-only
  lab emits its report to stdout; that JSON was captured explicitly.
- [Matched measurements](profile-comparison.json): 64 fresh-process ABBA runs,
  both domains/carriers, idle, four-reader updates, 256-row updates and observed
  revoke/recover. All retired connections and cleanup counters are clean.

The conformance kit's independent oracle checks native projections and source
receipts as well as effective rows. Adding a stale unsaved runtime case exposed
the original corpus's inability to catch permissive eligibility; the negative
profile now fails. The kit rejects mixed domains, duplicate cases, unrelated
exceptions and skipped mandatory cases. Its interface signature fixture is
separate from the unchanged normative wire lock.

Diagnostics v1 retain acquisition semantics. Explicit v2 reports SDK facts and
one cached evidence sample; a current empty inventory differs from expired or
warming evidence. Assessment never reports route health, retires its Reader and
guard on completion/cancellation, and rejects qualification completed after its
deadline. Dedicated repeated-cancellation and late-validation regressions pass.

The performance profiles both use the same reviewed native validators and
identical fixture workloads. Costs vary by scenario; two samples per profile
are descriptive, not stable tail latency or a production ranking. No
cross-call validation cache, weaker admission or speculative pooling is enabled.
Reader, Client, channel, bridge, profile/core view and authority bytes remain
identical to a11.

The matrix records runtime digests at completion. Its measured core/harness bytes
stayed fixed while unrelated conformance/diagnostic review proceeded. A later
cleanup refinement in `testing/ssh_carrier.py` is excluded from those measurements:
the matrix uses the separate recorded `tests/ssh_fixture.py`. The final installed
wheel gates separately accept the new packaged carrier. Worker CPU excludes SSH
publisher descendants; tree sampling can miss peaks. Other host workloads were
not controlled. Framed bytes are not encrypted NIC traffic.

See [owner conformance](../../conformance.md) and
[SDK diagnostics](../../sdk-diagnostics.md) for usage. Reproduce with the immutable
wheel installed in dedicated environments:

```sh
rtk proxy /path/to/core-python scripts/check.py
rtk proxy /path/to/core-python scripts/check-conformance-wheel.py --ssh
rtk proxy /path/to/native-python scripts/check.py --native
rtk proxy /path/to/native-python scripts/check-sdk-compat.py --baseline-python /path/to/pinned-a11-python
rtk proxy /path/to/native-python scripts/check-authority-compat.py --ssh-plus /path/to/rofi-ssh-plus --backend mesh-plus --baseline bounded-read-v1
rtk proxy /path/to/native-python scripts/compare-reader-profiles.py --seconds 5 --report /tmp/profile-comparison.json
```

Frozen schemas/lock and authority bytes are unchanged. Native wheels and package
hashes are exact inputs, not evidence of owner extraction. No sibling checkout
gate, provider collection, WAN, GUI, physical suspend, production-budget soak,
managed selection or deployment was performed. Neither Observer nor chezmoi was
edited. All evidence belongs to Mesh; old release artifacts remain immutable.
