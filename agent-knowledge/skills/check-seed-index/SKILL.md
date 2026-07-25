---
name: check-seed-index
disable-model-invocation: true
description: Read-only staleness check for the four docs/seed/ indexes (FUNCTION_INDEX, GLUE_INDEX_BACKEND, GLUE_INDEX_FRONTEND, CAPABILITY_MAP) — reports coverage gaps, entries and findings that cite changed files, and nothing else. Writes no files. Use when explicitly invoked as /check-seed-index, or automatically from /pre-grill before trusting an index.
---

# check-seed-index

Answer one question: **can I trust these indexes right now?** Report, then stop.

**This skill never writes a file.** Not the docs, not a report file, not a
`Last Updated` bump. Fixing is `/update-seed-index`'s job. If you find yourself
reaching for Edit, you're in the wrong skill.

Read `seed-index-scope` first — it owns the scope table, the git anchor recipe,
and the entry grammar. Do not restate or re-derive those here.

## Workflow

1. **Compute the changed set** per doc, using the anchor recipe in the helper.
   If a doc's changed set is empty, it is current — say so in one line and skip
   the rest of its checks.

2. **Coverage gaps.** For each doc with a non-empty changed set:
   - Enumerate the function/component symbols defined in its in-scope paths.
   - Parse the doc's `#### ` entry headers.
   - Report **missing** (in source, not in doc) and **orphaned** (in doc, no
     longer in source).
   - For `GLUE_INDEX_FRONTEND`, a new file that is a presentational leaf is not
     a gap. Apply the judgment from the helper, and check the doc's
     `## Out of scope but touched by this survey` section first — if it's
     already listed there, it's a settled decision, not a finding.

3. **Suspect entries.** Any entry whose `**Called from:**` or body cites a file
   in the changed set. These may be fine — the file changed, the function may
   not have. Report the count and the files; do not re-read the functions.

4. **Suspect findings.** Same test against the numbered findings section. Report
   these **separately** from entries — a stale finding misleads harder than a
   stale entry, because it's a confident claim about a hazard.

5. **CAPABILITY_MAP.** Not scanned. Mention it only if the backend changed set
   contains a new `src/processors/*.py` or a new router, which implies a new
   capability row may be warranted.

## Output

Compact. This runs inside other skills; it must not bury its caller.

```
FUNCTION_INDEX        current (0 changed files)
GLUE_INDEX_BACKEND    ⚠ 1 missing, 0 orphaned | 4 suspect entries, 1 suspect finding
                        changed: src/api/jobs.py, src/processors/repo.py
GLUE_INDEX_FRONTEND   current (0 changed files)
CAPABILITY_MAP        new processor detected (src/processors/podcast.py) — row may be needed

→ /update-seed-index          fixes coverage
→ /update-seed-index --drift  also re-verifies the 4 suspects + 1 finding
```

All four current → collapse to a single line: `seed indexes current (through
<short-sha>).` Nothing more.

## When called from /pre-grill

Same checks, but stay quiet unless something is wrong. A clean result is one
line; a dirty one is the block above plus a note naming which briefs lean on the
affected doc. Never offer to fix it mid-`/pre-grill` — that would swap a
planning session for a docs session.

## Check

The parse is the fragile part — a changed heading format would silently yield
"everything is missing". Compare parsed entry counts against the baselines in
the helper (147 / 96 / 54). A wild mismatch means the parse broke, not that the
docs collapsed; report that instead of a fake gap list.
