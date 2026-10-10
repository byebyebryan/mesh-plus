# Changelog

## 0.1.0a2 (unreleased)

- Keep completed and failed subscription iterators exhausted after their terminal
  item, while retaining explicit subscription cleanup.
- Wake pending request callers on a valid request `ended` frame without closing
  sibling work.
- Add a shared standalone CI/local validation command and integration handoff.
- Keep disposable SSH key paths private independently of the validation
  environment location, preserving StrictModes in isolated wheel acceptance.
- Separate current readiness, historical checkpoints, candidate package evidence
  and deployed authority selection. The frozen contract is unchanged.

## 0.1.0a1 (2026-10-09)

- Freeze cached polling and pushed state over IPC and SSH stdio, including
  nonce proof, bounded delivery lifecycle and pure consumer validity checks.
- Publish the experimental wheel; SSH Plus selects its shared Host Mesh authority
  on Snap and Starship through an independently pinned chezmoi installation.
- Keep Observer transport migrations, ordered events/replay, WSS and the shared
  fleet broker behind independent acceptance gates.
