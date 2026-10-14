# Compatible admission simplification study

[Plan](../../docs/simplification-plan.md) and
[assessment](../../docs/evidence/2026-10-13-simplification/README.md) bind source,
wheel and installed-copy evidence separately. These tools are not packaged APIs.

Create separate baseline/candidate wheel environments with the exact versions in
the assessment. Baseline source is `c4ec7ca`; candidate runtime is `30af2aa`.
Neither artifact replaces the published a15 release. Store wheels under
`ARTIFACTS/baseline` and `ARTIFACTS/candidate`, with corresponding
`baseline-env`/`candidate-env` Python environments. Both wheels declare a16;
their hashes and runtime fingerprints distinguish them. An independent
`standalone-env` must have no Observer packages or native-input .pth file.

Snapshot the selected installed Tmux a7 pure package read-only into a private
input directory, recording all file hashes as `tmux-installed-input.json`.
A .pth in the two measurement environments selects that fixed copy. This is
installed-copy provenance; do not describe it as an immutable wheel download.
Preserve prior artifact directories and use new private outputs for every trial.

```sh
rtk proxy .venv/bin/python studies/simplification/compare.py --artifacts /private/ARTIFACTS --output /private/new-pilot --pilot
rtk proxy .venv/bin/python studies/simplification/compare.py --artifacts /private/ARTIFACTS --output /private/new-matrix
rtk proxy .venv/bin/python studies/simplification/repeat_single.py --artifacts /private/ARTIFACTS --output /private/new-repeat.json
rtk proxy /private/ARTIFACTS/candidate-env/bin/python -I -B studies/simplification/native.py
rtk proxy /private/ARTIFACTS/candidate-env/bin/python -I -B studies/controlled/check.py
rtk proxy /private/ARTIFACTS/standalone-env/bin/python scripts/check.py --wss
rtk proxy /private/ARTIFACTS/standalone-env/bin/python scripts/check-conformance-wheel.py --ssh --report /private/new-conformance.json
```

`compare.py` serializes 40 ABBA blocks / 160 fresh processes and checks artifact
fingerprint stability and equal public work, identities and acquisition counts.
Counters run in one separate untimed operation; `measure.py` installs direct
owner record_host callbacks before timing. No classifier counter/cProfile runs
inside the decision timing. Do not run other local gates while timing.

The pure pipeline performs real CachedPublisher/native facade admission,
Bridge/Client callback boundaries, Reader/ReadGuard and consumer current checks.
It deliberately omits carrier/source I/O and is not native polling or push
performance. Original receipt counters/expiry remain unchanged. Each positive
case must fit the original lease; expiry causes a failed expected-row oracle,
not implicit lease extension. Heartbeat/error cells validate control paths only.
Actual owned Tmux source-loss/push correctness is a separate native check.

`repeat_single.py` repeats the one-host pipeline with longer cells to examine a
short-matrix regression outlier. Full result archives must retain every ABBA
position, input/runtime/harness hashes, failed attempts and exclusions. CPU is
process_time_ns; wall time is perf_counter_ns. Peak RSS includes setup and does
not qualify steady PSS or transient memory guarantees. Expected-row checks are
inside the measured CPU scope; there is no independent controller process.

Native acceptance owns a disposable TMUX_TMPDIR/default-server namespace,
owner, IPC listener and Reader subscriptions. It never targets operational tmux,
Agent services, route-health writers, desktop policy, actions or managed pins.
IPC remote-proof bindings are synthetic and distinct from normal SSH routes.
SDK external conformance additionally owns disposable SSH endpoints. Explicit
source/native/installed/CI acceptance remains necessary before any release.
