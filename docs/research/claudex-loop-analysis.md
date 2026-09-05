# claudex-loop: what it is, and overlap with this repo's loop skills

No existing `docs/research/` convention was found in this repo (checked `docs/research/`, `docs/adr/`,
`docs/agents/` — only ADRs and agent runbooks exist, no prior research-note pattern), so this note
was saved at `docs/research/claudex-loop-analysis.md` per the fallback instruction.

Source: https://github.com/chaseai-yt/claudex-loop (public, MIT, 1615 stars, formerly named
`crucible` / `grill-me-codex` — old URLs and marketplace source redirect). All claims below cite the
exact file fetched via `gh api repos/chaseai-yt/claudex-loop/contents/<path>`.

## 1. What claudex-loop actually is

It is a **Claude Code plugin** containing three **Agent Skills** (SKILL.md-based), not a standalone
CLI. Structure, from the repo tree (`gh api .../git/trees/HEAD?recursive=1`):

```
.claude-plugin/plugin.json        # plugin manifest
.claude-plugin/marketplace.json   # marketplace listing
skills/claudex-loop/SKILL.md      # main 4-phase skill (22.5 KB) + ADR-FORMAT.md, CONTEXT-FORMAT.md
skills/codex-review/SKILL.md      # standalone Phase-2-only skill (10 KB)
skills/codex-build/SKILL.md       # standalone Phase-3-only skill (10 KB)
legacy/grill-me-codex/, legacy/grill-with-docs-codex/   # predecessor skills, kept for compat
```
Source: `gh api repos/chaseai-yt/claudex-loop/git/trees/f8c111d...?recursive=1`.

**What it automates:** a four-phase "plan hardening" workflow that runs *before* any code is
written, using two rival AI models so neither grades its own work:

- **Phase 0 — RECON** (Claude alone): scouts the codebase (brownfield) or researches prior
  art/stack/pitfalls (greenfield), ends with an "Assumptions Ledger" the user confirms in one batch.
- **Phase 1 — INTERROGATE** (Claude ↔ user): a "Decision Map" splits open decisions into
  load-bearing (asked one at a time, each with why-it-matters/recommendation/what-breaks-if-wrong)
  vs. cosmetic (batched); produces a locked `PLAN.md`.
- **Phase 2 — REVIEW** (Claude ↔ OpenAI Codex): Codex adversarially reviews `PLAN.md` in a
  **read-only sandbox**, replying `VERDICT: APPROVED` or `VERDICT: REVISE`; Claude arbitrates,
  revises, and resumes the **same Codex session** (`codex exec resume $THREAD_ID`) so Codex
  remembers its own prior findings, up to `MAX_ROUNDS` (default 5).
- **Phase 3 — BUILD** (optional): the user picks who builds. If Codex builds, it gets full write
  access and Claude reads the whole diff + runs the proof test. If Claude builds, a *fresh*
  read-only Codex session cross-inspects the diff afterward (on by default).

Source (workflow + phase descriptions): `skills/claudex-loop/SKILL.md` lines 1–130 (frontmatter and
Phase 0/1 body) and the Phase 2 section (`## PHASE 2 — REVIEW`); also summarized in `README.md`
("The four phases" table) and in `.claude-plugin/plugin.json`'s `description` field.

Two artifacts are produced every run: `PLAN.md` (the plan) and `PLAN-REVIEW-LOG.md` (the
round-by-round argument transcript). Source: `README.md`, "Two artifacts every run" line.

## 2. Scope / frontmatter of its SKILL.md files

### `skills/claudex-loop/SKILL.md` (main skill)
```yaml
name: claudex-loop
description: Four-phase plan hardening (renamed from /crucible 2026-08-16; old triggers still
  work) — supersedes /grill-me-codex and /grill-with-docs-codex. PHASE 0 RECON — ... PHASE 1
  INTERROGATE — ... PHASE 2 REVIEW — the locked plan goes to PLAN.md and OpenAI Codex adversarially
  reviews it in a read-only sandbox (VERDICT: APPROVED/REVISE); Claude revises and re-submits to
  the SAME Codex session until APPROVED or MAX_ROUNDS, then you sign off before any code. PHASE 3
  BUILD (optional) — ... Use when the user says "/claudex-loop", "claudex this", "run the claudex
  loop", "/crucible" (legacy), "put this through the crucible", "crucible this plan", "grill me
  then have codex review", "stress-test this plan before we build", or is about to build something
  high-stakes (auth, schema, concurrency, migrations, payments, greenfield architecture) and wants
  alignment AND a cross-model sanity check first. Locked plan needing only the Codex loop →
  /codex-review. Reviewing already-written code → /codex:review. NOT for trivial changes.
```
Source: `skills/claudex-loop/SKILL.md` lines 1–4 (fetched via
`gh api repos/chaseai-yt/claudex-loop/contents/skills/claudex-loop/SKILL.md`).

Notably, this description **fully summarizes the workflow** (all four phases spelled out) rather
than only stating trigger conditions — the opposite of the "description = when-to-use only, never a
workflow summary" rule taught in this environment's own `superpowers:writing-skills` skill (see
`C:\Users\leone\.claude\plugins\cache\claude-plugins-official\superpowers\6.3.0\skills\writing-skills\SKILL.md`
lines 150–158, "Skill Discovery Optimization" section: *"The description should ONLY describe
triggering conditions. Do NOT summarize the skill's process or workflow... an agent may follow the
description instead of reading the full skill content"*). The claudex-loop author appears to have
made the opposite tradeoff deliberately, packing near-1000 characters of phase detail plus explicit
disambiguation lines against its own siblings and its own legacy names.

### `skills/codex-review/SKILL.md` and `skills/codex-build/SKILL.md`
Standalone entry points for just Phase 2 or just Phase 3 — for a plan that's already locked (skip
recon/interrogate) or a plan ready to build. The main skill's own frontmatter explicitly
disambiguates: *"Locked plan needing only the Codex loop → /codex-review. Reviewing already-written
code → /codex:review."* Source: `skills/claudex-loop/SKILL.md` line 3 (final sentence), and
filenames from the repo tree.

### Install/trigger mechanics
Plugin install gives namespaced skill IDs (`/claudex-loop:claudex-loop`,
`/claudex-loop:codex-review`, `/claudex-loop:codex-build`), but intent-based triggering ("claudex
this plan", legacy "crucible this plan") fires regardless of namespace. Manual install copies the
three `skills/*` folders directly into `~/.claude/skills/`, giving bare names `/claudex-loop`,
`/codex-review`, `/codex-build`. Source: `README.md`, "Install" section.

## 3. Loop mechanism — comparison with this repo's loop skills

| | claudex-loop (Phase 2) | `rabbitloop` (this repo) | `prloop` (this repo) | `ralph-loop` (plugin) |
|---|---|---|---|---|
| **What it loops against** | A pre-code `PLAN.md`, reviewed by **OpenAI Codex** (cross-provider adversary) | An **already-open GitHub PR**, reviewed by **CodeRabbit + Codacy + CI mutation-test gates** | Wraps commit→push→PR→one inner Codex pass→`rabbitloop` in one shot | Any long-running task; re-feeds the **same prompt** back to the model each time it tries to exit |
| **Loop condition** | Resume same Codex `thread_id` each round until `VERDICT: APPROVED` or `MAX_ROUNDS` (default 5) | Poll gate status, fix actionable findings, push, re-check, repeat until CodeRabbit shows zero actionable comments AND all check-runs succeed | Not itself a loop — one inner Codex pass, then delegates the real loop to `rabbitloop` | Iterate until a user-defined `--completion-promise` string is truthfully emitted, or `--max-iterations` |
| **Stage of work** | **Pre-implementation** (plan hardening, no code written until sign-off) | **Post-implementation, pre-merge** (code already exists as a PR) | Bridges the two: opens the PR, then hands off to rabbitloop | Task-agnostic, no fixed stage |
| **Sandbox/safety model** | Codex forced `read-only` every round via `-c sandbox_mode="read-only"` on resume (resume doesn't accept `-s`); Phase 3 build flips to full write access with a clean-tree + human-diff-read gate | `Bash(gh:*) Bash(git:*)` allowlisted; operates on a live PR/repo, not sandboxed | Delegates to rabbitloop for the gate loop | No sandbox restriction described in the command frontmatter |
| **Frontmatter style** | Long, workflow-summarizing description (see §2) | Short, "Use when..." trigger-only description, closer to the SKILL.md convention | `disable-model-invocation: true` — explicit-invoke only, no auto-trigger description needed | Slash-command (`.md` under `commands/`), not a SKILL.md at all — no auto-invocation description |

**Verdict on overlap:** claudex-loop and this repo's `rabbitloop`/`prloop` do **not** compete for the
same trigger surface — they operate on different objects (an unwritten plan vs. an already-opened
PR) and against different reviewers (Codex vs. CodeRabbit/Codacy/CI). There is no duplicate
"when to use" collision today. The nearest genuine relative is `ralph-loop` (also a bounded
retry-until-condition loop over a Bash-driven CLI harness), but ralph-loop is prompt-agnostic and
task-shaped, not plan/PR-shaped, and is a slash command rather than an auto-triggered skill, so it
doesn't collide either.

The one real risk if `claudex-loop` were ever installed into this repo is at the **Phase 3 optional
build** boundary: its own frontmatter already anticipates this and explicitly hands off to
"Reviewing already-written code → `/codex:review`" rather than re-implementing a PR-gate loop — i.e.
the author designed it to stop before the point where `rabbitloop`/`prloop` begin. If this repo were
to adopt claudex-loop, the natural chain would be `claudex-loop` (plan) → normal implementation →
`prloop`/`rabbitloop` (PR gates), with no phase doing the other's job.

## Sources consulted
- `gh api repos/chaseai-yt/claudex-loop` (repo metadata/description)
- `gh api repos/chaseai-yt/claudex-loop/git/trees/HEAD?recursive=1` (file tree)
- `gh api repos/chaseai-yt/claudex-loop/contents/README.md`
- `gh api repos/chaseai-yt/claudex-loop/contents/.claude-plugin/plugin.json`
- `gh api repos/chaseai-yt/claudex-loop/contents/.claude-plugin/marketplace.json`
- `gh api repos/chaseai-yt/claudex-loop/contents/skills/claudex-loop/SKILL.md`
- `gh api repos/chaseai-yt/claudex-loop/contents/skills/codex-review/SKILL.md` (tree listing only; frontmatter not fully read, size 10088 bytes per tree)
- `gh api repos/chaseai-yt/claudex-loop/contents/skills/codex-build/SKILL.md` (tree listing only; frontmatter not fully read, size 10129 bytes per tree)
- This repo: `agent-knowledge/skills/rabbitloop/SKILL.md`, `agent-knowledge/skills/prloop/SKILL.md`
- `C:\Users\leone\.claude\plugins\cache\claude-plugins-official\ralph-loop\1.0.0\commands\ralph-loop.md`
- `C:\Users\leone\.claude\plugins\cache\claude-plugins-official\superpowers\6.3.0\skills\writing-skills\SKILL.md` (for the SDO/description-writing contrast in §2)
