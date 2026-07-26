---
name: seed-index-scope
disable-model-invocation: true
description: Internal helper for /check-seed-index and /update-seed-index only. Holds the shared facts both need — which source paths each docs/seed/ index covers, how to compute a doc's staleness anchor from git, the entry grammar, and the CodeGraph caller caveat. Contains no procedure; the two commands own all behavior.
---

# seed-index-scope

Shared **facts** for the two seed-index commands. Deliberately contains no
logic — if this file starts saying "and then decide whether to…", that
behavior belongs in `/check-seed-index` or `/update-seed-index` instead.

Both commands read this file first. It exists so they can never disagree
about what's in scope; two anti-drift tools that drift apart are worse than
none.

## The four docs

| Doc | Covers | Scan mode |
|---|---|---|
| `docs/seed/FUNCTION_INDEX.md` | utility/service layer | glob — mechanical |
| `docs/seed/GLUE_INDEX_BACKEND.md` | orchestration layer | glob — mechanical |
| `docs/seed/GLUE_INDEX_FRONTEND.md` | routes + wiring components | glob for candidates, judgment on the delta |
| `docs/seed/CAPABILITY_MAP.md` | capability → owning module | **derived — never scanned directly** |

### `FUNCTION_INDEX.md`

In scope:

- `src/services/**/*.py`
- `src/utils/**/*.py`
- `src/brain.py`, `src/config.py`, `src/database.py`, `src/queue.py`, `src/templates.py`
- `web/lib/**/*.ts` (including `web/lib/hooks/`)

Out of scope: `src/processors/`, `src/api/`, `src/auth/`, `src/telegram/`,
`src/main.py`, `src/worker.py`, `src/__init__.py`, `web/components/`,
`web/app/`, `web/lib/mocks/`, and any `*.test.ts` / `test_*.py`.

### `GLUE_INDEX_BACKEND.md`

In scope:

- `src/processors/**/*.py`
- `src/api/**/*.py`
- `src/auth/**/*.py`
- `src/telegram/**/*.py`
- `src/main.py`, `src/worker.py`

Out of scope: everything `FUNCTION_INDEX.md` covers. Cross-reference that file
by name rather than re-describing a function it already documents.

> `src/*.py` is fully partitioned between these two docs — `brain`, `config`,
> `database`, `queue`, `templates` belong to FUNCTION_INDEX; `main`, `worker`
> to GLUE_INDEX_BACKEND; `__init__.py` to neither. A new file directly under
> `src/` belongs to one of them; decide which and say so.

### `GLUE_INDEX_FRONTEND.md`

Candidates: `web/app/**/*.tsx`, `web/app/**/route.ts`, `web/components/**/*.tsx`.

Of those, in scope are route pages/layouts and **wiring** components — the ones
that compose hooks + API data + child components into a working screen, or own
cross-domain handlers/navigation. Pure presentational leaves (icons, badges,
tooltips, static copy) are out.

That distinction is a judgment call, not a glob. Apply it **only to files in
the delta** — never re-judge the whole tree. When a new file is judged a leaf,
record it in the doc's existing `## Out of scope but touched by this survey`
section with a one-line reason, so the next run doesn't re-litigate it.

Excluded outright: `*.test.tsx`, `web/components/svg/`.

### `CAPABILITY_MAP.md`

Has no `####` entries — it's a 16-row hand-curated table of capability → owning
module. Never coverage-scanned. A row is warranted when a genuinely new
**capability** appears, which surfaces as a new `src/processors/*.py` or a new
router during the `GLUE_INDEX_BACKEND` scan. It updates as a *consequence* of
that scan, never on its own schedule.

## Staleness anchors

Each of the three scanned docs carries an explicit anchor line, directly under
its `**Last Updated:**` line:

```md
<!-- seed-index: coverage=<sha> drift=<sha> -->
```

Two anchors, because the two modes verify different things and must not lie
about each other:

- **`coverage`** — every in-scope file up to this sha has been checked for
  missing/orphaned entries. Bumped by any `/update-seed-index` run.
- **`drift`** — entry and finding *prose* has been verified against source up
  to this sha. Bumped **only** by `/update-seed-index --drift`.

A coverage-only run bumping `drift` would silently discard unverified
suspects, so it must not.

The anchors are **not** the `**Last Updated:**` line and must not be kept in
step with it. `Last Updated` records when the doc's *content* last changed; the
anchors record how far its content has been *verified*. A doc that was already
current and received only a stamp keeps its old date — dating it today because
a check ran is the false-freshness signal the anchors exist to replace.

### Computing a changed set

```bash
# coverage scan
git diff --name-only <coverage-sha> -- <the doc's in-scope paths>

# suspect scan
git diff --name-only <drift-sha> -- <the doc's in-scope paths>
```

Note there is **no `..HEAD`**. `git diff <sha> -- <paths>` compares the sha
against the *working tree*, so uncommitted edits are included. Uncommitted work
is exactly when someone is about to consult the index, so it must count.

### Why not `git log -1 -- <doc>`

Deriving the anchor from the doc's own last commit looks simpler and is wrong
in both directions:

- **It moves on edits that verify nothing.** Fix a typo in `FUNCTION_INDEX.md`
  and the anchor jumps to now — every un-indexed source change made before that
  typo fix becomes permanently invisible. The doc silently certifies work
  nobody did.
- **It can't distinguish the two modes**, so a cheap coverage run would claim
  the same freshness as a full drift pass.

An explicit stamp, written only by the skill that did the work, is the only
version that means what it says.

### Missing anchor

A doc with no anchor line has never been through `/update-seed-index`. Treat it
as anchored at the doc's first commit — scan everything, and stamp both anchors
on the first run.

## Entry grammar

**Two shapes, not one.** Every entry opens with `#### ` at line start followed
by the symbol in backticks — that heading is what the parser counts, and it is
the only part common to all three docs. The label lines differ by doc.

**`FUNCTION_INDEX.md` and `GLUE_INDEX_FRONTEND.md`** — three labels. Write all
three on a new entry; a few existing ones merge several symbols under one
heading and share labels:

```md
#### `function_name(key_args) -> ReturnType`
**Does:** Plain English, 1-2 sentences. What it does, not how.
**Called from:** `caller` in `path/to/file.py`, … — or "Not called elsewhere yet".
**Usage:** one realistic call line
```

**`GLUE_INDEX_BACKEND.md`** — `**Does:**` plus *one* of `**Called from:**` (for
helpers) or `**Entry point:**` (for routes, naming what actually triggers them).
`**Usage:**` is rare and optional. The heading carries the route and file
inline:

```md
#### `handler_name` — `GET /api/thing/{id}` — `src/api/thing.py`
**Does:** Plain English, 1-2 sentences.
**Entry point:** what actually calls this route.
```

Measured on the current docs, so this describes them rather than prescribing at
them: `Usage` appears on 147/147 FUNCTION_INDEX entries and 54/54
GLUE_INDEX_FRONTEND entries, but only 8/98 in GLUE_INDEX_BACKEND — which
carries `Entry point` on 43. Writing the three-label shape into the backend
index would leave new entries inconsistent with ~90 neighbours.

Those counts drift as entries are added and are here to show the *contrast*
between the two shapes, not as a checksum. Nothing verifies them; don't treat a
mismatch as a defect, and re-measure before quoting them.

The grammar is load-bearing: the parser keys on `#### ` at line start and on the
bolded labels. A blank line inside an entry, a missing `**Does:**`, or a wrapped
`#### ` heading parses wrong and surfaces as a phantom gap. Conformance means
matching **that doc's** shape — never reformat one index to match another's.

**Parse sanity:** a doc parsing to **zero** entries means the grammar changed
and the parse broke — not that the doc collapsed. Say that, rather than
reporting every function as missing.

No expected entry counts are recorded here, deliberately. Counts change every
time `/update-seed-index` adds or removes an entry, so a hardcoded baseline
would false-alarm on the tool's own successful repairs and need bumping after
every run. Zero-vs-nonzero is the only threshold that maintains itself.

## Findings sections

Each of the three indexes opens with a numbered findings section
(`## Read this first — what's actually hiding`, `## Read this first — surprising
findings`, `## Surprises / notable findings`). Those items are **arguments about
the code, not inventory** — they cite files, so the changed set flags them the
same way it flags entries, but they are never mechanically rewritten.

## CodeGraph caller caveat

**CodeGraph systematically under-reports callers in this repo.** It misses the
`import module; module.func()` call style and lazy in-function imports, both of
which are common here. The original survey hit this repeatedly — `transcript.py`,
`pdf_intake.py`, `filter_vision_links`, `build_transcript_markdown`,
`append_short_row` / `append_long_row`, `notify_invite` and `fetch_public_image`
all showed false "zero callers".

So: **never write a `**Called from:**` line, and never call a function dead, on
CodeGraph evidence alone.** Grep-verify by bare function name across `src/` and
`web/` first. This caveat lives here rather than in the correction skill because
anything else reading these indexes needs it too.
