# Mesh Plus migration and acceptance

## Delivery sequence

| Stage | Deliverable | Exit criterion |
| --- | --- | --- |
| D0 | Base read/bridge schemas, example profiles, migration design | Structural and semantic conformance, lossless domain projection, hostile cases and review resolved |
| D1 | Pure delivery sessions plus IPC/persistent SSH backends consuming SSH Plus authority | Request/push/cancel/credit parity; dependency isolation; route marker and timeout/failure tests; no runtime selection |
| D2 | Tmux adapter extraction behind existing coordinator | Owner/native passivity unchanged; Fleet 1 and Session v1 compatibility, independent desktop receipts and GUI behavior |
| D3 | Agent adapter against a newly frozen current producer tuple | Both-provider partial/expiry/identity cases; cached-only bridge proof; no obsolete Agent Plus dependency |
| D4 | Host authority transfer with SSH Plus compatibility facade | Host Mesh fixture parity, unchanged revisions/history and rollback |
| D5 | Candidate packaging and scoped operations | Exact artifacts, source/installed bytes, service lifetime/recovery/resource and rollback proof |
| D6 | Deferred consumers and supported local-service wrapper | Each UI/device/action client independently accepted; connection sharing, independent expiry and replay interests proved before multi-client selection |

D2 and D3 have separate producer gates. They may proceed against different
domain versions while sharing Mesh Read 1. D4 can follow either proven adapter;
it does not block D1 because the existing authority is usable. Agent Plus is a
later consumer checkpoint. Active Agent producer changes trigger baseline review,
not automatic changes to a frozen Tmux artifact.

No stage silently promotes native, graphical or deployment acceptance from
synthetic fixtures. Release/commit/push and operational selection require their
own requested scope; this design pass produces no selected runtime.

## Design validation matrix

The [transport validation plan](transport-validation.md) adds protocol/backend,
ordered subscriptions, digest-proof and local-service gates. WSS and producer
event delivery remain independent implementation checkpoints. They need not
block initial IPC/SSH state delivery or force Agent Plus to catch up early.

| Case | Required outcome |
| --- | --- |
| One local host and several hosts | Same profile parser and session row shape |
| Native ID collision across hosts/namespaces | Distinct complete references |
| Unknown host, duplicate host selection, excess capacity | Request rejection before dispatch |
| Complete-empty owner | Ready delivery, non-null owner metadata, zero records |
| Warming owner | Ready delivery, warming source, null owner snapshot |
| DNS/refusal/timeout before reached marker | Classified route failure, independent sibling success |
| Auth/host-key rejection | Visible policy failure, no unreachable health report |
| Missing tool/source failure after marker | Reached route, unavailable source, no repeated domain call |
| Malformed/oversized/incompatible owner | One host excluded; bounded typed diagnostic |
| Partial Claude coverage, healthy Codex | Preserve partial qualification and known scoped positives |
| Runtime refresh with expired history | Never renew metadata/activity; invalidate conservatively per provider |
| Delayed push or repeated heartbeat | No source lease extension |
| Wrong/replayed nonce or payload digest | Reject proof before publication |
| Different local/remote BOOTTIME origins | Same conservative RTT calculation; no absolute-clock subtraction |
| Proof validation or fragmented delivery exceeds deadline | Reject even if bytes began in time |
| Reader suspend, source restart or catalog replacement | Expire/revoke positives and reject old epochs |
| Owner sequences from separate probe connections | Compare each native stream independently |
| Gap and reconnect | Historical/unknown until full scoped resync plus proof |
| Unsaved Agent historical rows | No new/sliding retention window; conservatively omit without public retirement receipt |
| Healthy but domain-incomplete response | Mesh delivery can be complete while source coverage is partial |
| Action timeout after possible dispatch | No replay, fallback or assumed effect; existing action boundary retained |
| Aggregate limit | Explicit capacity outcome; no silent truncation or 1 MiB Tmux limit applied to Agent |
| Independent desktop contexts | Share owner delivery only; never share viewer authority |

## Runtime proofs following implementation

Use owned disposable sessions and endpoints. Compare installed public owner
results against independent native evidence, preserving ordinary sessions,
provider settings/hooks, history and running services. A live Mesh read must not
change attachment counts, create a server/provider, trigger native collection on
subscribe, mutate provider data or hold a session alive.

Prove both-host SSH disconnect/reconnect, owner crash/restart, source expiry,
reader restart, route replacement and actual rollback/reselection in serialized
endpoint order. Physical suspend and GUI/device behavior need real acceptance,
not fake-clock evidence. Measure owned SSH children, network bytes, CPU and RSS
at one/many readers, warm-up, unavailable hosts and slow consumers.

Tmux GUI gates cover remembered selection/context, independent Open/Attached,
refresh ticket completion, frozen confirmation and expired positives. Agent
consumer gates cover current producer schema, uncertainty, age/order, confirmed
child filtering and deliberately separate writer/TTY selection. A native read
gate does not certify Resume, focus or close.

## Baseline drift

`docs/evidence/source-baselines.json` records full checkout heads, clean state and
hashes of the files used in design validation. `reference/` contains frozen
contract schemas/fixtures for reproducibility. Checks validate those copies and
can optionally compare current source hashes without editing other repositories.
If a producer evolves, retain this evidence as a dated design result and review
the changed contract before implementation. Do not call the old baseline current.
