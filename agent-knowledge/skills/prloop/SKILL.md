---
name: prloop
description: Commit, push, open a PR, run one inner Codex review pass, then run rabbitloop against it in one invocation.
disable-model-invocation: true
---

# prloop

Wrapper that runs your usual open-PR-then-optimize sequence in one invocation:

1. `commit-commands:commit-push-pr` — commit the current changes, push the branch, and open the PR.
2. `/codex:review --wait` — one inner Codex review pass against the PR before the gate loop starts.
   Read its output. For each finding, fix it unless it's a nitpick or a false positive — in that
   case note the reason and leave it. If anything was fixed, commit and push
   (`git commit -m "address inner codex review findings"` then `git push`) before moving on.
3. `rabbitloop` — run against the PR number step 1 just created, iterating until all gates pass.

Invoke step 1 and step 3 via the Skill tool. Run step 2's command directly (it's a slash command,
not a skill). Pass the PR number created in step 1 into step 3 as its input, so rabbitloop never has
to re-detect it from the current branch.

## Usage

User invokes `/prloop`. No arguments — it operates on the current branch's uncommitted
changes, same as `commit-push-pr` would on its own.
