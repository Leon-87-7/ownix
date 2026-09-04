---
name: rabbitloop
description: >
  Use when the user wants to fully optimize a GitHub PR against this repo's automated review
  gates — CodeRabbit, Codacy, and the frontend/backend mutation-testing checks — iterating until
  CodeRabbit reports zero actionable comments and every check-run gate concludes success.
  Triggers/waits for all gates, fixes all actionable findings, pushes, re-checks, and repeats.
license: MIT
compatibility: Requires git and gh (GitHub CLI) authenticated, and CodeRabbit and/or Codacy installed on the repo.
metadata:
  author: LeonEidelman
  version: "2.0"
allowed-tools: Bash(gh:*) Bash(git:*)
---

# Rabbitloop

Iteratively fix a GitHub PR until **every gate** passes: CodeRabbit reports zero actionable
comments (and zero unresolved threads), Codacy's check run concludes `success` with zero check-run
annotations, and both mutation-testing check runs (`frontend-mutation`, `backend-mutation`)
conclude `success`.

> **Four gates, one loop.** Each iteration triggers CodeRabbit, waits for all four gates, gathers
> every actionable finding across them, fixes them in one batch, then pushes once so a single push
> re-runs everything. The loop only exits when **all** gates pass. A gate not installed on this repo
> (detect by whether its bot/check ever appears) is skipped rather than blocking on it.

**How each gate signals:**

| Gate                | Source                                          | Completion signal                                          | Pass condition |
| ------------------- | ------------------------------------------------ | ---------------------------------------------------------- | -------------- |
| CodeRabbit          | `coderabbitai[bot]`                              | Commit status context `CodeRabbit`; PR review whose body starts `Actionable comments posted: N` | `Actionable comments posted: 0` and no unresolved inline threads |
| Codacy              | `codacy-production[bot]`                         | Check run `Codacy Static Code Analysis` completes; AI Reviewer posts a PR review whose body starts `### Pull Request Overview` | Check conclusion `success`, zero check-run annotations, and no unresolved inline threads — a `success` conclusion does not by itself mean zero annotations, see below |
| Mutation — frontend | check run `frontend-mutation` (workflow "Mutation Testing") | Check run completes (Stryker on `web/`)         | Check conclusion `success` — mutation score at or above Stryker's `break: 50` threshold (`web/stryker.config.mjs`), **not** zero survivors |
| Mutation — backend  | check run `backend-mutation` (workflow "Mutation Testing")  | Check run completes (cosmic-ray on `src/`)      | Check conclusion `success` — `cosmic-ray exec` finished without crashing; **there is no score threshold wired up for backend at all**, so this passes even with a high survival rate |

Codacy has **two channels** under the same bot: the static-analysis **check run** (the gate) and an
**AI Reviewer** that submits a PR review with risk-tagged inline comments (`🔴 HIGH RISK` /
`🟡 MEDIUM RISK`). The AI review has no actionable counter — its unresolved inline threads ARE the
findings.

> `mutation-testing.yml` itself is annotated `continue-on-error: true` / "informational only, not a
> required check" — a leftover from before this repo started gating on it. Rabbitloop treats both
> mutation jobs as **blocking gates** regardless: wait for them, fix surviving mutants, and don't
> exit or offer merge until both conclude `success`.

**CodeRabbit needs a manual trigger on this repo.** Its automatic review-on-push is disabled here
("Review skipped: manual review required for this OSS repository"), so post the trigger comment
**every iteration**, not just as a fallback — see step A.

**CodeRabbit is capped at 1 included review/hour on this repo's plan.** Trigger once per
iteration, not more — a second trigger before the hour is up comes back `Review rate limited`
with zero findings, burning the wait for nothing. If that happens, don't re-trigger; wait out the
remainder of the hour (check the prior review's `submitted_at` to know how much is left), or fix
and push everything else this iteration and pick CodeRabbit back up once the window resets.

## Inputs

- **PR number** (optional): If not provided, detect the PR for the current branch.

## Instructions

### 1. Identify the PR

```bash
gh pr view --json number,headRefName -q '{number: .number, branch: .headRefName}'
```

Switch to the PR branch if not already on it.

### 2. Loop

Repeat the following cycle. **Max 5 iterations** to avoid runaway loops.

#### A. Trigger reviews

Push the latest changes (if any):

```bash
git push
```

Codacy and the two mutation-testing jobs auto-run on push. **CodeRabbit does not** — auto-review is
disabled on this repo, so trigger it explicitly every iteration, pushed or not:

```bash
gh pr comment <PR_NUMBER> --body "@coderabbitai review"
```

#### B. Wait for all gates

Get the head SHA once per iteration:

```bash
HEAD_SHA=$(gh pr view <PR_NUMBER> --json headRefOid -q .headRefOid)
```

**Check-run gates** (Codacy + both mutation jobs) — poll each by name until it completes:

```bash
for NAME in "Codacy Static Code Analysis" \
            "frontend-mutation" \
            "backend-mutation"; do
  while true; do
    RUN=$(gh api "repos/{owner}/{repo}/commits/$HEAD_SHA/check-runs" \
      --jq ".check_runs[] | select(.name == \"$NAME\")")
    STATUS=$(echo "$RUN" | jq -r '.status // empty')
    if [ "$STATUS" = "completed" ]; then
      echo "$NAME: $(echo "$RUN" | jq -r '.conclusion')"
      break
    fi
    echo "Waiting for $NAME... (status: ${STATUS:-not started})"
    sleep 10
  done
done
```

**CodeRabbit** — poll the commit status until it leaves `pending`, then read its latest review:

```bash
while true; do
  CR_STATE=$(gh api "repos/{owner}/{repo}/commits/$HEAD_SHA/status" \
    --jq '.statuses[] | select(.context == "CodeRabbit") | .state')
  if [ -n "$CR_STATE" ] && [ "$CR_STATE" != "pending" ]; then
    echo "CodeRabbit: $CR_STATE"
    break
  fi
  echo "Waiting for CodeRabbit... (state: ${CR_STATE:-not started})"
  sleep 10
done
```

If a gate never appears after a reasonable wait (~3–4 min), treat it as not installed and skip it
for the rest of the loop.

#### C. Fetch findings

**CodeRabbit summary** — latest review body starts with `Actionable comments posted: N`:

```bash
gh api "repos/{owner}/{repo}/pulls/<PR_NUMBER>/reviews" \
  --jq '[.[] | select(.user.login | test("coderabbit"; "i"))] | last | .body'
```

Parse `Actionable comments posted: N`. Ignore CodeRabbit's collapsible boilerplate
(`🤖 Prompt for AI Agents`, `🪄 Autofix`, review-info blocks) — they are not findings.

**Codacy check run** — the output names the issues/complexity/clones it flagged:

```bash
gh api "repos/{owner}/{repo}/commits/$HEAD_SHA/check-runs" \
  --jq '.check_runs[] | select(.app.slug == "codacy-production") | .output | {title, summary}'
```

A `success` conclusion titled "Your pull request is up to standards!" tolerates *complexity/clone*
deltas in the summary — those are informational regardless of conclusion. It does **not** mean
there are no real findings: Codacy's own severity threshold for failing the check is higher than
"this is a real issue," so a security/quality finding (SQL injection, hardcoded secret, etc.) can
sit under a `success` conclusion. Always also pull the check run's annotations, which carry the
per-line findings the summary only counts:

```bash
RUN_ID=$(gh api "repos/{owner}/{repo}/commits/$HEAD_SHA/check-runs" \
  --jq '[.check_runs[] | select(.app.slug == "codacy-production" and .name == "Codacy Static Code Analysis")] | if length == 1 then .[0].id else "" end')
if [ -z "$RUN_ID" ]; then
  echo "Codacy annotation run id ambiguous or missing — do not assume zero annotations; block the loop until resolved."
else
  gh api "repos/{owner}/{repo}/check-runs/$RUN_ID/annotations" \
    --jq '.[] | {path, line: .start_line, level: .annotation_level, message}'
fi
```

Treat every annotation as an actionable finding — fix it in this iteration's batch — regardless of
the check run's overall conclusion color. A failing conclusion additionally means the summary text
itself names gate-breaking issues on top of whatever the annotations list.

**Codacy AI Reviewer** — latest `codacy-production[bot]` PR review; the body is a prose
`### Pull Request Overview` (no counter — the inline threads are the findings):

```bash
gh api "repos/{owner}/{repo}/pulls/<PR_NUMBER>/reviews" \
  --jq '[.[] | select(.user.login | test("codacy"; "i"))] | last | .body'
```

The AI review may land a few minutes after the check run; if the bot has reviewed this PR before
but no review covers the latest push yet, wait for it (or use the review UI's "Run reviewer"
trigger — there is no comment trigger). Each of its inline comments opens with a risk tag
(`🔴 HIGH RISK` / `🟡 MEDIUM RISK`); treat them all as actionable unless clearly a false positive.

**Inline comments from both** — one call covers the two bots:

```bash
gh api --paginate "repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments" \
  --jq '.[] | select(.user.login | test("coderabbit|codacy"; "i")) | {user: .user.login, path, line, body}'
```

**Mutation testing** — download the uploaded report regardless of pass or fail (the check-run
output itself has no body):

```bash
RUN_ID=$(gh api "repos/{owner}/{repo}/actions/runs?head_sha=$HEAD_SHA" \
  --jq '.workflow_runs[] | select(.name == "Mutation Testing") | .id' | head -1)
gh run download "$RUN_ID" -n cosmic-ray-report -D /tmp/cosmic-ray   # backend
gh run download "$RUN_ID" -n stryker-report -D /tmp/stryker         # frontend
```

On a **failing** run, read `/tmp/cosmic-ray/cosmic-ray-report.txt` and `/tmp/stryker/stryker-run.log`
for mutants marked survived/not-killed — each surviving mutant is a finding: the code path it
touches has no test that would catch that mutation.

On **any** run, pass or fail, pull out the score — same two lines the CI job itself parses (see
`weekly-mutation-history` in `.github/workflows/mutation-testing.yml`), so the numbers agree with
what gets recorded in history:

```bash
# backend: last lines of cosmic-ray-report.txt are `total jobs: N` / `surviving mutants: N (P%)`
BE_TOTAL=$(grep -oP 'total jobs: \K\d+' /tmp/cosmic-ray/cosmic-ray-report.txt)
BE_SURVIVED=$(grep -oP 'surviving mutants: \K\d+' /tmp/cosmic-ray/cosmic-ray-report.txt)
# frontend: clear-text score table's "All files" row in stryker-run.log
FE_LINE=$(grep -m1 '^All files' /tmp/stryker/stryker-run.log)
FE_SCORE=$(echo "$FE_LINE" | awk -F'|' '{gsub(/ /,"",$2); print $2}')
```

**Baseline comparison (informational only — this never blocks the loop or the exit conditions
below; it only shapes what the final report says).** Fetch the last row of the weekly baseline:

```bash
# grep for a leading ISO date, not just `^|` — that also matches the header and separator rows,
# and tail -1 would silently pick the separator row when no weekly snapshot has landed yet.
BASELINE=$(git show origin/main:docs/ops/mutation-score-history.md | grep -P '^\| \d{4}-\d{2}-\d{2} ' | tail -1)
```

Empty `$BASELINE` means no weekly snapshot has run yet — report the PR's own scores with no
baseline comparison at all rather than diffing against nothing.

That row's `total` is a **full, unfiltered** scan of the configured scope (see the file's own
header). This PR's `cosmic-ray-report.txt` total usually isn't — `cr-filter-git` narrows a PR run
to only mutants on changed lines, so its total is often a small subset of the baseline's. Compare
totals before comparing scores:

- Backend total (`BE_TOTAL` above) matches the baseline row's backend total → it was an unfiltered
  run (e.g. the PR touched no cosmic-ray source files, so `cr-filter-git` was skipped — see the
  `source-changed` step in the workflow). Only then is `BE_SURVIVED`/`BE_TOTAL` diffable against the
  baseline's backend killed/total: report **regression** if survival rate rose, **improvement** if
  it fell, otherwise flat.
- Backend total is smaller → this was a filtered, partial run. Report the PR's own numbers in the
  final report, but do **not** claim a regression or improvement against the baseline — a smaller
  denominator makes the comparison meaningless.
- Frontend's score is always comparable: Stryker's incremental mode still reports the full
  configured `mutate` scope's score in its summary table even when most mutants were skipped via
  the incremental cache, so `FE_SCORE` diffs directly against the baseline row's frontend score.

#### D. Check exit conditions

Stop the loop if **any** of these are true:

- **All** gates pass: CodeRabbit reports **`Actionable comments posted: 0`** with **zero unresolved
  inline threads**; the Codacy check concluded **`success`** with **zero check-run annotations**
  and **zero unresolved inline threads** — the conclusion color alone is not sufficient, an
  annotation is a real finding regardless of it; both mutation check runs concluded **`success`** —
  per their own CI-defined pass condition (§ How each gate signals): frontend at/above Stryker's
  `break: 50` floor, backend just `cosmic-ray exec` finishing without crashing, regardless of
  survivors. (Skip whichever gate is not installed — an absent gate does not block the exit.)
- Max iterations reached (report current state).

Do **not** exit while any gate's check run is still non-`success`, still carries an annotation
(Codacy), or still has unresolved threads (CodeRabbit/Codacy) — e.g. a green Codacy check and zero
CodeRabbit comments don't matter
if `frontend-mutation` is still below the break threshold. But once a mutation check run itself
concludes `success`, it counts — don't keep looping on it because survivors remain; survivor counts
only feed the informational baseline comparison above, never this exit check.

#### E. Fix actionable comments

Gather the unresolved findings from **all four** gates into one list, then for each:

1. Read the file and understand the comment (or surviving mutant) in context.
2. Determine if it's actionable (code change needed) or informational/nitpick/false positive.
3. If actionable, make the fix — for a surviving mutant, that means adding or strengthening a test
   that fails against the mutated code, not touching the source.
4. If informational or a false positive, note it (with a brief reason) but still resolve the thread.

Fix everything in a single batch before pushing, so one push re-runs every gate at once.

#### F. Resolve threads

Both bots' inline comments are GitHub review threads, so one resolve flow handles both — when
listing threads, match `author.login` against `coderabbit` **or** `codacy`. (As a shortcut, posting
`@coderabbitai resolve` as a PR comment tells CodeRabbit to resolve all of its own threads at once;
still resolve Codacy's via GraphQL.)

Fetch unresolved review threads:

```bash
gh api graphql -f query='
query($cursor: String) {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes { body path author { login } }
          }
        }
      }
    }
  }
}'
```

Resolve addressed threads:

```bash
gh api graphql -f query='
mutation {
  t1: resolveReviewThread(input: {threadId: "ID1"}) { thread { isResolved } }
  t2: resolveReviewThread(input: {threadId: "ID2"}) { thread { isResolved } }
}'
```

#### G. Commit and push

```bash
git add -A
git commit -m "address review feedback (rabbitloop iteration N)"
git push
```

Then go back to step **A**.

### 3. Report

After exiting the loop, summarize:

| Field                    | Value                                        |
| ------------------------ | --------------------------------------------- |
| Iterations               | N                                             |
| CodeRabbit actionable    | N remaining (or n/a if not installed)         |
| Codacy check             | success / failure (or n/a if not installed)   |
| Mutation — frontend      | success / failure, score N% vs. baseline N% (regression / improvement / flat / not comparable) |
| Mutation — backend       | success / failure, score N% vs. baseline N% (regression / improvement / flat / not comparable) |
| Comments resolved        | N                                             |
| Remaining comments       | N (if any)                                    |

If the loop exited due to max iterations, list any remaining unresolved comments (noting which
gate raised each) and suggest next steps. The score/baseline comparison is reporting only — a
regression there does not stop the loop or withhold the merge offer below; both mutation gates
already conclude on their own CI-defined pass condition (§ How each gate signals), and this just
adds the trend on top of that.

### 4. Offer to merge on a full pass

If the loop exited because **all four gates** passed (not max-iterations) and any CI/status checks
are green, proactively ask the user whether to merge — don't just report and stop. This is the one
case worth interrupting for: 0-actionable CodeRabbit + green Codacy + green mutation checks + green
CI is the signal the user is waiting on.

- `gh pr merge <PR_NUMBER> --squash --delete-branch` (or the user's preferred merge strategy) once
  confirmed.

Still honor any standing merge policy (e.g. extra confirmation before merging into `main`/`master`)
— this prompt satisfies "ask before merging," it doesn't bypass a stricter main-branch rule layered
on top.

## Output format

```
Rabbitloop complete.
  Iterations:      2
  CodeRabbit:      0 actionable
  Codacy:          success
  Mutation (fe):   success — 82.10% (baseline 78.57%, improvement)
  Mutation (be):   success — 53.10% (not comparable — filtered run, 40/612 mutants tested)
  Resolved:        7 comments
  Remaining:       0
```

If not fully resolved:

```
Rabbitloop stopped after 5 iterations.
  CodeRabbit:      2 actionable
  Codacy:          failure
  Mutation (fe):   success — 61.20% (baseline 78.57%, regression)
  Mutation (be):   failure
  Resolved:        12 comments
  Remaining:       3

Remaining issues:
  - [coderabbit] src/db.ts:112 — "Missing index on user_id column"
  - [codacy]     src/auth.ts:45 — "Avoid deeply nested control flow"
```
