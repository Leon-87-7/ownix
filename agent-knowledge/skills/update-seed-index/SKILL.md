---
name: update-seed-index
disable-model-invocation: true
description: Repairs the four docs/seed/ indexes after /check-seed-index reports drift — adds entries for new in-scope functions, removes orphaned ones, and with --drift also re-verifies entries and findings that cite changed files. Previews every change and waits for confirmation before writing. Use only when explicitly invoked as /update-seed-index.
---

# update-seed-index

Fix what `/check-seed-index` found. Coverage by default; prose only on demand.

Read `seed-index-scope` first for the scope table, git anchor, and entry
grammar. **Its CodeGraph caveat is binding here** — you are writing
`**Called from:**` lines, which is exactly where CodeGraph lies in this repo.
Grep-verify every caller by bare function name before writing it.

## Two modes

**Default — coverage only.** Add entries for in-scope functions with no entry;
remove entries whose function is gone. Touches nothing else. Cheap, and it's
the common case.

**`--drift` — coverage plus prose.** Additionally re-read every suspect entry
and finding, and correct the ones that are actually wrong. This is the
expensive mode; it re-does a slice of the original survey. Fire it deliberately.

## Workflow

1. **Run the `/check-seed-index` checks** to get the current delta. Never work
   from a stale report pasted into the conversation — recompute.

2. **Draft the changes** without writing anything yet.

   *New entries:* read the function, write the four-line grammar. `**Does:**` is
   plain English about purpose, not a paraphrase of the body. `**Called from:**`
   is grep-verified. `**Usage:**` is one realistic call line.

   *Orphaned entries:* confirm the function is genuinely gone (renamed, moved,
   or deleted) before proposing removal. A move means re-home the entry, which
   may mean moving it between FUNCTION_INDEX and GLUE_INDEX_BACKEND — check the
   `src/*.py` partition rule in the helper.

   *Frontend leaves:* a new presentational component gets a one-line entry in
   `## Out of scope but touched by this survey`, not an index entry.

   *Under `--drift`:* for each suspect, re-read the function and compare against
   its entry. **Report "verified, no change" explicitly** — a suspect that
   turned out fine is a real result and stops it being re-checked next run.

3. **Findings — propose, never rewrite.** A finding is an argument you made
   about the code, not inventory. Under `--drift`, if a finding no longer holds,
   quote it, say why it's now false, and propose replacement text. Wait for
   explicit approval on **each** one. A tool that silently rewrites your
   arguments makes the ones it left alone untrustworthy too.

4. **CAPABILITY_MAP.** Only touch it if the backend pass found a genuinely new
   capability. Derive the row from the new processor/router — capability,
   owning module, depends-on, entry point, docs. One new pipeline, one new row.

5. **Preview and gate.** Show the full delta grouped by doc — entries added,
   removed, re-homed; findings proposed; the CAPABILITY_MAP row. Then stop and
   wait. No writes before confirmation, no partial application.

6. **Write, then bump.** Apply the approved changes, update each touched doc's
   `**Last Updated:**` line to today, and leave the docs uncommitted for review.
   Do not commit; the user decides where these land.

## Rules

- **Never invent a caller.** If grep finds nothing, write "Not called elsewhere
  yet" — that's a finding worth having, not a gap to paper over.
- **Match the surrounding voice.** These docs are terse and concrete. A new
  entry should be indistinguishable from its neighbors.
- **Don't renumber findings.** They're referenced by number from other docs and
  from chat. Replace text in place; append new ones at the end.
- **Don't rewrite an entry you weren't asked to touch.** Default mode adds and
  removes. Improving prose is `--drift`'s job, and only for flagged suspects.

## Check

After writing, re-run the `/check-seed-index` coverage pass. It must come back
clean for every doc you touched — same parse, same scope, zero remaining gaps.
If it still reports a gap you thought you fixed, the entry didn't match the
grammar; fix the entry, not the check.
