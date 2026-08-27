# Job/Link Tag Unification

**Date:** 2026-08-27
**Scope:** Fix the tag mismatch between job cards and the Links table for the three
content types where a job and its Brain link are really the same object.
**Trigger:** `link`-type job "UI SFX" showed `Tags 4` on its job card while the link
it produced (`uisfx.com`) showed no tags in the Links table — reached via `/ux-fix-loop`
→ `brand-lens` → `/mattpocock-skills:grill-with-docs`.

---

## 0. The problem (baseline, established during grilling)

`web/components/feed/job-card-tags.tsx` and `web/components/feed/links-table.tsx`'s
`LinkTagCluster` use two entirely independent tag-attachment scopes:

- **Job tags** — `useJobTags(jobId)` → `GET/POST/DELETE /api/jobs/{id}/tags[/{tag_id}]`
  (`src/api/jobs.py`), backed by the `job_tags` table.
- **Link tags** — `useLinkTags(linkId)` → `GET/POST/DELETE /api/brain/links/{id}/tags[/{tag_id}]`
  (`src/api/brain.py`), backed by `link_tags` (or equivalent) keyed to the `links` table.

Both render through the same shared `TagMenu` (`web/components/ui/tag-picker.tsx`), so
they look like one tagging system. They are not. A `links` row is a distinct graph node,
one per normalized URL, deduplicated across every job that ever surfaces that URL
(`CONTEXT.md` "Graph node" / rule 14 — "One Graph node per normalized URL"; `seen_count`
bumps on re-sighting, no second row is ever created). `source_job_id` on a `links` row is
provenance, not ownership (`CONTEXT.md` rule 15).

**Content-type cardinality** (established by reading each processor):

| content_type | links produced per job | ingest guarantee |
|---|---|---|
| `link` | exactly 1 | **verified** — `src/processors/link.py::run()` checks the row landed in `links` before marking the job `done`; raises otherwise |
| `article` | exactly 1 | fire-and-forget (`spawn_background`, `article.py:294-299`), gated on `settings.GOOGLE_DRIVE_FOLDER_BRAIN` being configured at all |
| `repo` | exactly 1 | fire-and-forget, same shape as `article` |
| `short` / `long` video, `photo`, `document` | zero-to-many | fire-and-forget, genuinely N:many (frame/description/vision-scraped links) |

Because `link`/`article`/`repo` are guaranteed (or intended) 1:1 with a single link, their
job-level tags and that link's tags are conceptually the same sticker on the same object,
just stored in two places. The N:many types have no single link to collapse onto — a
job-level tag there can't mean "this specific link."

---

## 1. Decision: scope of the merge

- **`link`, `article`, `repo` jobs:** merge. The job's tag control stops reading/writing
  `job_tags` and instead reads/writes the tags of the link it produced. One tag set.
- **`short`, `long`, `photo`, `document` jobs:** **no change.** Job tags and link tags stay
  two separately editable sets, with **no UI explanation** of the difference — this doc is
  the explanation. Do not add a tooltip, label, or badge to either surface for these types.
  (Considered and rejected: a hover tooltip is inaccessible on mobile with no fix that isn't
  itself new UI surface; an always-visible label adds permanent density to every row in a
  UI that already fights hard for compactness. Decision: the fix is documentation, not UI.)

**Non-negotiable boundary:** tags never flow from a carrier job (`short`/`long`/`photo`/
`document`) down to any link it surfaced. Tagging a reel only ever touches the reel's own
`job_tags`. This holds regardless of anything else in this doc.

---

## 2. Decision: mechanism — frontend-only redirect

`/api/jobs/{id}/tags` is **not modified** and keeps meaning exactly one thing — a job's own
`job_tags` — for every content type that still uses it (`short`/`long`/`photo`/`document`).
No conditional server-side branching inside that endpoint by `content_type`.

Instead:

1. The job read model gains a derived field — call it `link_id` — computed the same way
   `link.py`'s own verification step already does it: `chat_id` + `normalize_url(job.url)`
   joined against `links`. Only populated (attempted) for `content_type IN ('link', 'article', 'repo')`.
2. For those three content types, `JobCardTags` (`web/components/feed/job-card-tags.tsx`)
   and the job-detail page's `TagMenu` (`web/app/(dashboard)/jobs/[id]/page.tsx:1193`) call
   `useLinkTags(link_id)` directly instead of `useJobTags(job_id)`, once `link_id` resolves.

This mirrors an existing pattern (the frontend already branches per-`content_type` for field
sets — `SHORT_FIELDS` vs `ENRICHMENT_FIELDS` in `job-detail-utils`, per `GLUE_INDEX_FRONTEND.md`)
rather than inventing server-side polymorphism on a shared endpoint.

---

## 3. Decision: the sweep-and-switch rule (replaces backfill, replaces "disable while waiting")

One rule handles every edge case raised during grilling — no separate migration script,
no disabled-button state:

> **Whenever a `link`/`article`/`repo` job's tag control loads: if `link_id` resolves AND
> the job still has rows in `job_tags`, union those tag attachments onto the link's tags
> (never removing tags already on the link), delete the now-redundant `job_tags` rows for
> that job, then render/edit exclusively through the link's tags from that point on.**

This single check, run on load, covers every case surfaced in grilling:

- **Pre-existing job tags** (e.g. "UI SFX"'s 4 tags, already set before this ships): swept
  onto the link the next time that job's tag control loads. No standalone backfill migration
  needed — this makes it happen lazily instead.
- **`article`/`repo` jobs whose link hasn't landed yet** (fire-and-forget still in flight, or
  `GOOGLE_DRIVE_FOLDER_BRAIN` unset): `link_id` doesn't resolve yet, so the tag control falls
  back to behaving exactly like the N:many types — a normal, fully-editable `job_tags` button,
  not disabled. Once the link later appears (next time the job is viewed), the sweep rule
  fires and any tags added during the wait move over automatically.
- **A link that already existed before this job was created** (e.g. a Reels video mentioned
  a repo URL and it entered Brain via that video's N:many link extraction; the user later
  submits the same URL through the dedicated `repo` pipeline): `link_id` resolves immediately
  (the link already exists — "one node per URL" dedup). There's nothing to sweep (the new
  `repo` job has no `job_tags` yet), so the tag control just shows the link's existing tags
  straight away. This is correct, not a bug: the tags belong to the URL, not to whichever
  pipeline happened to create the row first. The originating carrier job (the reel) is never
  touched and never had its own tags altered.

**Out of scope / explicitly rejected:** no timeout constant, no polling, no disabled state.
The 30-second figure floated during grilling was a strawman for "how long do we wait" — the
actual answer is "there is no wait; the button just works normally on `job_tags` until a
link exists, then transparently switches." No client-side timer is needed.

---

## 4. What does NOT change

- `job_tags` table and `/api/jobs/{id}/tags` endpoints: unchanged, still the only tag store
  for `short`/`long`/`photo`/`document` jobs.
- `link_tags` (Brain link tags) and `/api/brain/links/{id}/tags`: unchanged.
- No new tables, no schema migration, no `PRAGMA user_version` bump. The sweep rule is a
  runtime read-time operation (SELECT existing `job_tags` for the job → INSERT OR IGNORE
  into the link's tag store → DELETE the swept `job_tags` rows), not a DDL change.
- No UI change of any kind for `short`/`long`/`photo`/`document` jobs.

---

## 5. Suggested vertical slices (for `/to-issue-kanban` to refine)

1. **Backend:** add derived `link_id` to the job read model for `content_type IN
   ('link','article','repo')` (`src/api/jobs.py` — reuse the `normalize_url` + `chat_id`
   join already proven in `src/processors/link.py`).
2. **Backend:** implement the sweep-and-switch operation (read `job_tags` for the job →
   union onto the link's tags → delete swept `job_tags` rows), triggered on job-tag-read
   for the three merged content types.
3. **Frontend:** `JobCardTags` and the job-detail `TagMenu` call site switch to
   `useLinkTags(link_id)` when `content_type IN ('link','article','repo')` and `link_id`
   is present; fall back to today's `useJobTags(jobId)` behavior when it isn't.
4. **Tests:** cover (a) merge for a job with pre-existing `job_tags` and an already-existing
   link, (b) merge for a job whose link doesn't exist yet (falls back to job tags, no
   crash), (c) no cross-contamination — a `short`/`long`/`photo`/`document` job's tags never
   touch any link it surfaced.
