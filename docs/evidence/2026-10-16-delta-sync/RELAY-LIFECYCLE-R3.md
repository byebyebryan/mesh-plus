# A1 lifecycle clarification handoff

This planning-only revision responds to root's acknowledged review of `m94`:
the byte-only role and r2 arithmetic fit, while watch/reuse deadline scope and
bridgeId setup/reconnect ownership need explicit contracts. This is not A1
closure, exact Observer agreement or runtime acceptance.

Owning host/worktree is **starship:/home/bryan/code/mesh-plus**, branch
`mesh-delta-sync-20261016`. Review these **two documents together**:

- Unchanged [r2 API](../../delta-sync-relay-api-r2.md), SHA256
  `8616bfba7c05dcf8982e431309bcd0bdf354c91bc023fdf0fcf85dcbe4c7abdd`,
  27,392 bytes, source checkpoint `e68b264`.
- [r3 lifecycle clarification](../../delta-sync-relay-lifecycle-r3.md), SHA256
  `eb5c217c544bbe10766c7c0f32d574294412c6f6230c7ad6b95a2a57483c0c9f`,
  12,316 bytes. It explicitly replaces r2's channel-wide acquisition deadline
  and channel operation signatures; all other r2 requirements remain.

The source session/ref protocol is unchanged. The channel can outlive an
acquisition; one immutable deadline capsule owns each attempt and its requests.
Watch startup and long-lived transport have separate resource timers, while
the original Reader fifteen-second budget and two-second nonce proof remain
hard bounds. Factory-minted bridge_id is learned through a fresh nonce-echoed,
authenticated same-channel hello before the Reader binds setup. Reconnect
always changes channelEpoch; a new factory also changes bridgeId. Neither
identity exchange nor reusing a native root creates admission/current authority.

Validation for this docs-only clarification: selected Python 3.14.8 lock check
passes 33 locked inputs/25 identical packaged schemas; offline design gate
passes 116 checks. `git diff` shows no changes to src/contracts/tests/scripts/
pyproject. The canonical 276 core/no-skips, 169 delivery and Ruff pass at
`e68b264` remains evidence for its unchanged runtime, not tests of this proposed
lifecycle. No runtime tests are added that merely restate these planning rules.
Root's independent two-version replay of r2 arithmetic remains scoped to that
unchanged artifact. Real lifecycle/resource/error/transport cases are pending.

Root A1rev2 remains `665f6ca` / SHA256
`6eaa408376f91bb7c5e4276812927fd2bfce2445412fb02a211bea22a5e52aef`;
G0 appendix `a376bc84...`, common cache-input contract `7f7751ec...` and LOCK
`11736752...` remain unchanged. No package allocation, new wheel, native source
adoption, sibling edit or rollout. Dense CPU, packed recovery, populated full
delivery, complete intake/output accounting, RSS and installed end-to-end
qualification remain open. Exact Observer review of the r2+r3 tuple and root
A1 acceptance record still precede dependent relay implementation.
