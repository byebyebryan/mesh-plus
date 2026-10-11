# WSS promotion review and implementation plan

2026-10-11. The owner selected finishing WSS as an optional supported backend
after reviewing the study and the direct TLS alternative. This pass implements
the additive proposal in `studies/wss/promotion-proposal.md`; it does not select
real-host artifacts or change existing SDK defaults.

## Reviewed decisions

- Preserve every existing Read/Delivery and native schema byte, protocol ID,
  SDK v1 signature and Host Mesh authority implementation. Add WSS carriage and
  configuration through a separate normative addendum and lock revision 2.
- Keep the listener native-only, direct TLS, fixed cached publisher, mTLS and
  exact fingerprint/host/source/profile authorization. No browser, proxy,
  redirect, compression, fallback, collection or action capability.
- Retain one selection-level credential set and the explicit authorization
  triple `[hostId, sourceId, profile]`. One canonical remote host occurs at most
  once in a registry. New factory composition selects WSS for registered hosts
  and existing IPC/SSH for other selected hosts; never fallback after failure.
- Keep legacy Host Mesh revisions/SSH token derivation unchanged. WSS selection
  revisions bind the captured catalog revision, ordered registry and public
  trust material. Private keys revoke authority on replacement but do not enter
  public tokens. Test mixed fleets, including setup failure provenance.
- Configuration files must reside on an owner-controlled local filesystem.
  Retain at most one daemon read job per configuration owner, revoke timed-out
  callers, reject replacements until that job retires, and report unretired jobs
  on close. A blocked kernel filesystem call has no hard interruption guarantee.
- Bound aggregate carrier setup to 15 seconds, send to 2 seconds including
  encoding/validation, and channel shutdown to 3 seconds including graceful
  close and abort. Deadlines use BOOTTIME and are checked after synchronous work;
  Python validation is not preempted while executing.

## Implementation review refinement

CI exposed OpenSSL date-signing fixture portability; use the portable `openssl ca`
interface with a private disposable database. The first correction omitted its
required output-directory setting; smoke and full gates must pass before the
final handoff. No runtime schema or credential policy was relaxed.

Review also found default asyncio hostname resolution could leave an executor
thread behind a cancelled setup. Add an owned standard-library DNS helper,
three-second lookup and TCP/TLS budgets inside the existing fifteen-second total,
verified original hostnames, and cancellation/timeout retirement tests. Numeric
addresses bypass DNS. This compatible refinement does not inherit the study's
cold-setup measurements.

## Sequence and acceptance

1. Review/lock the additive configuration contract; prove old schema digests
   unchanged and preserve all other exclusions.
2. Promote the carrier, owned configuration snapshots and optional SDK factory;
   close budget/accounting gaps and validate carrier/native/mixed regressions.
3. Add listener/read/watch/probe/doctor CLI and optional packaging. Verify no-extra
   imports, fresh wheel resources, supported Python versions and canonical gates.
4. Commit exact source/private-wheel inputs and handoff. Real fleet selection,
   network loss, physical suspend and rollback remain an operational gate; no
   sibling checkout, chezmoi or live service changes occur in this pass.

The prior study remains dated evidence against a13. New runtime acceptance must
reference the promoted bytes rather than inherit those reports.
