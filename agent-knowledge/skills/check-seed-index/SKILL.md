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

1. **Parse each doc first, before looking at git at all.** Apply the
   parse-sanity rule from the helper. A doc that parses to zero entries is
   broken regardless of whether any source changed — report that and move on to
   the next doc. Checking git first would let a malformed index committed
   without source changes pass as "current".

2. **Compute the changed sets** per doc from its `coverage` and `drift`
   anchors (recipe in the helper). If both are empty, the doc is current — say
   so in one line and skip the rest of its checks. Its parse already passed in
   step 1.

3. **Coverage gaps**, against the `coverage` changed set:
   - Enumerate the function/component symbols defined in its in-scope paths.
   - Report **missing** (in source, not in doc) and **orphaned** (in doc, no
     longer in source).
   - For `GLUE_INDEX_FRONTEND`, a new file that is a presentational leaf is not
     a gap. Apply the judgment from the helper, and check the doc's
     `## Out of scope but touched by this survey` section first — if it's
     already listed there, it's a settled decision, not a finding.

4. **Suspect entries**, against the `drift` changed set. Any entry whose
   `**Called from:**` or body cites a file in it. These may be fine — the file
   changed, the function may not have. Report the count and the files; do not
   re-read the functions.

5. **Suspect findings.** Same test against the numbered findings section. Report
   these **separately** from entries — a stale finding misleads harder than a
   stale entry, because it's a confident claim about a hazard.

6. **CAPABILITY_MAP.** Not scanned. Mention it only when the backend scan turns
   up an **added** processor or router — not a modified one:

   ```bash
   git diff --name-only --diff-filter=A <coverage-sha> -- src/processors/ src/api/
   ```

   Editing an existing processor doesn't create a capability. Without the
   `--diff-filter=A`, routine edits would nag for a new row on every run, and a
   warning that cries wolf gets ignored when it's finally right.

## Output

Compact. This runs inside other skills; it must not bury its caller.

```text
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
"everything is missing". Apply the parse-sanity rule from the helper: a doc that
parses to zero entries has a broken parse, not a collapsed doc. Report that
instead of a fake gap list.
