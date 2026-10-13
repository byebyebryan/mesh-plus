# Controlled cached Mesh benchmark

Study-only tools for the [authorized plan](../../docs/controlled-performance-plan.md).
No packaged SDK or wire changes. No active sibling checkout, Agent imports,
ordinary Observer service, provider query, route writer or managed deployment.

Use a dedicated Python 3.13.7 environment with the immutable wheels and exact
dependency versions in [inputs.json](inputs.json). The runner fails if installed
runtime fingerprints, dependency versions or Python differ. Input acceptance is
explicit; do not rewrite the manifest to hide drift. Released Mesh a15 and Tmux
a7 wheels supply all runtime/profile code. A new wheel comparison needs a new
reviewed input manifest and separate acceptance.

```sh
rtk proxy /path/to/venv/bin/python -I -B studies/controlled/check.py
rtk proxy /path/to/venv/bin/python -I -B studies/controlled/run.py \
  --output /private/absolute/pilot --steps 8 --fanout 1 2 4
rtk proxy /path/to/venv/bin/python -I -B studies/controlled/run.py \
  --output /private/absolute/expired --steps 8 --expired
rtk proxy /path/to/venv/bin/python -I -B studies/controlled/matrix.py \
  --output /private/absolute/matrix --rows 32 --steps 40 --blocks 4
```

Output directories must be new and canonical. Private disposable fixtures under
the user's home keep OpenSSH StrictModes enabled. All listeners bind loopback or
private Unix sockets. Native fixture frames stay in memory and never enter public
measurement reports; certificates/keys and sockets disappear with their owned
directory. SSH uses an owned daemon and forced command, not operational SSH config.

Every carrier uses a generic CachedPublisher, the released pure Tmux profile and
the same fixture native cached-source interface. Fixture acquisition is a separate
process. IPC/WSS share one publisher process across upstream clients; SSH has one
publisher per client. That topology difference is part of the result, not a
carrier-only speed claim or downstream prepared-service acceptance.

Poll means persistent Client + Reader.read_host/compose + ReadGuard, with one
nonce proof per trace step. It is not cold CLI polling. Push uses Reader.watch,
settles its two baseline proofs, then requires one pushed replacement and proof
per step per reader. The controller advances only after all consumers admit the
previous step. The 50 ms minimum interval permits backpressure; slow cases take
longer rather than dropping updates. It is not an ordinary collection/proof cadence.

Original source receipts never advance. Current traces must remain positively
valid for the whole bounded case; natural expiry fails that case. Expired traces
admit the stored records but never grant current rows. Cases validate independent
expected identities/names/revisions and unchanged source receipts.

Four-position ABBA blocks fail unless normalized trace hashes, proof/push/native
acquisition counts and consumer admission counts match exactly. Application JSON
bytes remove the LF framing difference only in evidence. Nonces, native clocks
and receipt/proof expiry checks remain real in runtime admission.

CPU uses own ticks and PID birth before/after and every fourth step. Fixture,
publisher, reader/driver, SSH roles and sampler are separate. Reader/driver includes
control and sampler RPC overhead; fixture work is excluded from the primary Mesh
total but reported. Short cells have tick quantization and sampled memory can miss
peaks. No privileged inaccessible PSS is invented. TLS/key setup and imports are
outside the measured phase. Event-loop/module caches in the matrix driver persist;
clients, profiles, cache owners, publishers and carrier resources are fresh per case.

`check.py` covers ordered traces, normalized comparisons, non-renewing expired
proofs, failed/mismatched block rejection, plus the portable downstream pure Tmux
networking suite. It requires no running tmux server or Observer collection.
The pinned certificate test helper supplies disposable mTLS material; its digest
and the reused accounting helpers are included in each execution input record.

`attribute.py --output /private/new.json` profiles the pure admission pipeline
without carrier/source I/O. `summarize.py --root /private/matrix --output /report`
requires the complete 192-case matrix and rechecks exact-work blocks. It stores
raw metadata in deterministic gzip with input/report digests.

`check-copy.py` and `copy_hypothesis.py` retain a rejected module-local cloning
experiment. Its ownership cases pass, but four pipeline CPU blocks are flat or
slower. It is not packaged, installed or used by the carrier benchmark. See the
[assessment](../../docs/evidence/2026-10-12-controlled-performance/README.md).

Interrupted/failed pilot directories are retained locally as discarded attempts.
They cannot certify performance. Loopback comparisons and synthetic fixed work do
not replace ordinary fleet resource, operational rotation or suspend acceptance.
