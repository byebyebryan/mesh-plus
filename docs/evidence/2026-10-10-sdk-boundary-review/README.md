# SDK boundary review evidence

Review baseline: Mesh `172647523f3b5901f519612b6e1f6f059f43ac74`, package
0.1.0a10, Python 3.14.8. This is evidence for the
[SDK independence proposal](../../sdk-independence-review.md), not deployment or
acceptance of an implemented new SDK. All experiment sockets/publishers are
disposable private fixtures. No native collection or installed service change
is performed by these experiments.

| Check | Result and limit |
| --- | --- |
| Current generic Delivery, `probe.py` | Pass: real private IPC request/proof/subscription using a plain validator, Observer imports blocked, watch closed and no loop diagnostics. The synthetic payload deliberately does not certify native profile semantics. |
| Current Reader callable codec | Expected rejection before request: `client.codec.__self__` is unavailable. The proposal is motivated by this explicit coupling, not a framing defect. |
| Current configured profile injection | Expected rejection: no `profile` keyword exists. No alternate SDK is substituted. |
| Projection model, `model.py` | Four validated local/remote cases across both profiles roundtrip exact owner fields/records and original receipts. Four effective-selection comparisons at current and fully expired times match the existing selector. |
| Canonical core gate | Pass: 75 tests, zero skips/failures/errors, design/Delivery oracles and lint; 18 normative inputs and 20 packaged schemas unchanged. The environment includes the two Observer packages, so this is not a package-absence claim. The separate blocked-import probe covers its stated generic seam. |
| Current SSH regressions | Pass: 82 tests with Mesh selected and the selected interpreter also first on PATH for source entrypoint subprocesses. No Plus peer gate is required. |
| Earlier SSH regression attempt | Negative retained: 82 tests with two source-entrypoint failures when the parent interpreter was selected but PATH still chose a different Python. Logs remain private and hashed. |
| Historical extraction guard | Rejected before tests: current Mesh authority includes its previously reviewed bounded captured-byte seam, while original SSH legacy/a6 authority bytes remain separate. Its literal equality check was not bypassed or converted into acceptance. |

The projection model delegates native validation to current reviewed producer
facades. It verifies a feasible pure boundary and some eligibility equivalence;
it does not run the future injected Reader/ReadGuard or the full adversarial
conformance matrix. Those are implementation acceptance gates in the proposal.

`validation.json` records exact current inputs, commands, hashes and exclusions.
`report.json` and `model-report.json` bind their respective experiment source
digests. `checksums.json` indexes the public review files except itself. Full
test logs remain under `/tmp/mesh-sdk-boundary-review` and are hashed; raw native
frames are not added to this record.

Reproduce these design probes from a reviewed source checkout, using its selected
Mesh/Observer environment:

```sh
rtk proxy /absolute/selected/python probe.py /absolute/private/probe-report.json
rtk proxy /absolute/selected/python model.py /absolute/private/model-report.json
```

The model currently records the baseline `/home/bryan/code/mesh-plus` fixture
path explicitly. Relocation requires changing that design-only input and recording
a fresh digest; this is not a published SDK tool with a portable CLI guarantee.
