# Private controller/carrier source qualification

Runtime: **`a482abbd463d23ebf66f23c60e4e95a521c19cc6`**, comprising initial
controller `828cf0c`, buffered-clock retirement `6daba40` and detached-header
error cleanup `a482abb`. Actual source fixture: immutable Observer
**`e3441d017b94ee27f4dfccb5f1f3f30612435adf`**. This is a bounded G1 source
checkpoint. It does not qualify a configured route, producer, package or rollout.

The [implementation/API guide](../../delta-sync-controller-g1.md) describes the
public factories, serve entry, ownership/limit table, terminal receipts and
restrictive head deadline. [checkpoint.json](checkpoint.json) binds source,
protected contract inputs, exact agreement bytes, runners, logs and results.
The source files are independently checked against their declared Git blobs.

| Check | Result and scope |
| --- | --- |
| Canonical Python 3.14.8 gate | 383 tests, zero failures/errors/skips; lock 33 inputs / 25 identical packaged schemas, design 116, delivery 169 and Ruff pass. No `--native`, `--check-sources` or wheel check. |
| Focused Python 3.14.8 and 3.11.17 | 64 methods each: 14 carrier, 14 controller and 36 existing relay checks. GC disabled throughout; retained errors, physical-pin cleanup and final counters checked. These overlap the canonical suite. |
| Actual Observer composition on both Pythons | Two parameterized methods / **24 scenarios each**: Unix IPC or real two-pipe stdio × expanded/compact × full/active × 0/1/4 transactions. No failures/errors/skips. |
| Initial `828cf0c` plus final two-method regression overlay | Five expected failures each Python: four clock-provenance subcases and one held-copy-error case; zero errors/skips. Final source passes both methods within the focused gate. This is a before/after source regression, not an RSS or cap-overrun claim. |

The real-source cases use disposable native Runtime sockets and synthetic
ServiceState data with collection disabled. The actual owning source,
structural codec, generic controller/relay and independent Reader run on their
supported APIs. Each case compares original native baseline, transactions,
whitespace-padded complete and head fragments. Material passes Reader full
admission and two distinct fresh actual source/relay head proofs produce exact
native DTO exports. Native complete and controller results reject as proof.
Physical wire counters equal bytes actually sent/received; completed-line
counters are sampled after the sender resumes from drain.

The trusted test caller supplies request binding/authentication and explicit
matching codecs. The Reader nonce helper and owning native fixture retirement
are private test scaffolding, disclosed in the runner. Client buffers, fixture
captures/oracles and separate owner/Reader/relay ledgers are outside an aggregate
resource measurement. Reported relay accounted peaks are diagnostic only.

The focused checks additionally cover strict raw framing/duplicates/Unicode,
exact parser limits, prepayment refusal before allocation/input, fixed range
pressure, coalesced and fragmented first-byte floors, paused pending input,
pending hellos in the 16-client limit, setup/output-lock expiry, exact capsule
IDs, busy denial, watch independence, cancellation receipts and expiry,
restrictive head scanner overrun without proof output, original recovery before
failed/source, sibling isolation, actual blocked writer credit and deterministic
GC-disabled close. Scope/clock invalidation rejects buffered tails, minted
headers and new output without another read. Header copy failures clear payload
and hook traceback frames before independently retained caller credit returns.

## Exact contract basis

- Mesh controller R2 `33cb57c98ca3062f139ea1fd0c68b15bd5abd8d6`, SHA256
  `89b24a9f3191bcded303d33c8b2ed973335b703811185abf1186848fbd562f48`.
- Mesh completion R3 `5d8cb484f8eba9fb6ca8dce9421410434cedf37d`, SHA256
  `42375477c46c097ede85b3bbbe5cda5f03a89823fdd7358e1078064a0c34e1c2`.
- Observer same-byte owning agreement `d6364d1c3441b07436ca1e32789994aa2448be85`,
  guide SHA256 `29bfb22e1259165148ac09e0f1f82e5d6ee8ac808e688422e7e76785f57bbd32`,
  receipt SHA256 `341584bc02f2d79ee3ef1395d9a98d10d16f08bba97a1bf0d374dfa603373564`.
- Coordinator R2+R3 clear record `92b97d825cc2c1f8c3bbd1ad17b046e328e3eec9`.

The R1/R2 arithmetic and original completion checks retain their earlier source
tuples; no arithmetic rerun is attributed to this runtime. Native Agent complete
remains <=16,384 bytes; whole nested Mesh control <=65,536 including LF. The
transaction quota remains <=4 / 8 MiB, with zero only exact base==target and
original correlated complete. All use the same original 32/64 MiB caps and
2-second head / 15-second acquisition restrictions. G0, LOCK, old schemas,
authority, material publisher and selected a7/a23 bytes remain unchanged.

## Reproduce

Export the two Mesh commits and Observer e3441d0 into separate fresh directories;
do not import a mutable sibling checkout. With the reviewed Python environments:

```sh
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-controller/qualify.py \
  --mesh /absolute/export/a482abb \
  --before-mesh /absolute/export/828cf0c \
  --observer /absolute/export/e3441d0 \
  --python311 /absolute/environment311/bin/python \
  --output /absolute/new/results
```

The [qualifier](qualify.py) records all commands and refuses to overwrite results.
The [actual-source runner](verify_observer_controller.py) can run separately with
`--mesh`, `--observer`, `--output` and `--log`. The frozen [final results](results/qualification.json)
and logs preserve the exact immutable runs. Draft fixture/prototype diagnostics
are listed separately in the checkpoint; they are not fail-before production or
final acceptance evidence.

## Remaining gates

Ordinary authenticated/selected Reader integration, actual compact watch and
cancellation stress, populated native providers, fixed SSH, aggregate 32/64
resource accounting, RSS/plateau, whole-pipeline CPU, dense 2,000-row delivery,
delivered cold/recovery and immutable installed-pair qualification remain open.
Observer's reported owner CPU ceiling failures remain failures; no CPU comparison
was performed here. No version/schema/encoding allocation, wheel, source pairing
promotion, sibling edits, service/provider action or rollout occurred.
