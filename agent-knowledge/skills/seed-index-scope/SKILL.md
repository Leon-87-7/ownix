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

## Staleness anchor

A doc's own last commit is the anchor — not its `**Last Updated:**` line, which
is prose a human can forget to bump.

```bash
SHA=$(git log -1 --format=%H -- docs/seed/<DOC>.md)
git diff --name-only "$SHA"..HEAD -- <the doc's in-scope paths>
```

The result is the **changed set**: every in-scope source file touched since the
doc was last written. Everything both commands do keys off it.

## Entry grammar

Each indexed function is exactly four lines. Detection parses this; correction
writes it. Neither may vary it.

```md
#### `function_name(key_args) -> ReturnType`
**Does:** Plain English, 1-2 sentences. What it does, not how.
**Called from:** `caller` in `path/to/file.py`, … — or "Not called elsewhere yet".
**Usage:** one realistic call line
```

Current counts, for a sanity check that parsing worked: FUNCTION_INDEX 147,
GLUE_INDEX_BACKEND 96, GLUE_INDEX_FRONTEND 54.

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
