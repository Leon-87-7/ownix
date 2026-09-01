---
name: prloop
description: Commit, push, open a PR, then immediately run rabbitloop against it in one invocation.
disable-model-invocation: true
---

# prloop

Wrapper that runs your usual open-PR-then-optimize sequence in one invocation:

1. `commit-commands:commit-push-pr` — commit the current changes, push the branch, and open the PR.
2. `rabbitloop` — run against the PR number step 1 just created, iterating until all gates pass.

Invoke each skill sequentially via the Skill tool. Pass the PR number created in step 1 into step 2
as its input, so rabbitloop never has to re-detect it from the current branch.

## Usage

User invokes `/prloop`. No arguments — it operates on the current branch's uncommitted
changes, same as `commit-push-pr` would on its own.
