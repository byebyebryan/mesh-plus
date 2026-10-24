# Maintained source and research checkouts

Use the published repository's `main` branch for ordinary development and current
supported documentation. Research branches/worktrees are retained for their own
experiments and are not the current maintenance starting point.

In the maintainer's multi-worktree environment, the conventional checkout directory
may remain on a research branch. Inspect `git status --short --branch` and
`git worktree list` before editing. Create an isolated worktree from current
`origin/main` when needed; preserve existing branches, dirty work and recovery refs.

The release asset's build source, qualification commit and later documentation
head can differ. Follow immutable release provenance rather than rebuilding or
relabeling an old artifact from today's source tip.
