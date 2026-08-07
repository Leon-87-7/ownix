---
adr: "0046"
title: Links outlive jobs — deleting a job no longer deletes its links
status: accepted
date: 2026-08-07
---

## Context

`delete_job` (`src/database.py:2353`) removes a job and then, in the same transaction,
de-indexes every link that job contributed:

```sql
DELETE FROM jobs WHERE id = ?          -- five child tables cascade
DELETE FROM links WHERE source_job = ? -- manual, links carries no FK
```

ADR-0042 introduced that second statement so a deleted job could not stay searchable in
the [[Second Brain]] through its extracted links. At the time the ratio made it invisible:
a `link` job owns exactly one link, an `article` job a handful.

That assumption no longer holds. A [[Long video]] job already owns every URL
`extract_description_links` pulled from its description, and the [[Bookmark import]] added
in the batch-links grill owns one link per bookmark — 318 in the reference export
(`bookmarks_8_6_26.html`). Deleting one [[Job card]] would silently destroy 318 Brain
nodes with their embeddings, [[Link tag]]s, graph edges and Obsidian `.md` files. There is
no soft-delete, no trash tier and no undo (ADR-0042), and `links-table.tsx` is single-select
(`selectedLinkId` drives a preview panel, not a checkbox column), so rebuilding by hand
means 318 separate deletes.

The cascade also created an asymmetry with no defensible basis. The same 318 URLs pasted as
a [[Batch link paste]] become 318 independent jobs, where deleting one card costs one link.
Uploaded as a file they become one card, where deleting it costs all of them. Same URLs,
same Brain, opposite blast radius — decided entirely by how they arrived.

Finally, the statement is the last place in the codebase reading `source_job` as ownership.
ADR-0043 already ruled the other way: "`chat_id` carries ownership; `source_job` degrades to
the Obsidian backlink it always really was."

## Decision

**`delete_job` does not touch `links`.** A job is a work record; the links it produced are
knowledge that outlives it. `source_job` is left dangling as pure provenance.

Removing links is a separate, explicit act:

- one at a time via `DELETE /api/brain/links/{link_id}` — which already exists
  (`src/api/brain.py:90` → `database.delete_link`, `:2203`), is already viewer-scoped, and
  already cascades `link_tags`;
- all of a job's at once via an **opt-in** `DELETE /api/jobs/{job_id}?with_links=1`, surfaced
  as a checkbox on the delete confirm that names the count ("also remove the 318 links this
  import added").

The opt-in flag runs the identical SQL the cascade used to run. The change is which way the
default points.

This applies to all seven pipelines, not only the high-N ones.

## Considered options

- **Keep the cascade, add a confirmation dialog naming the count.** Rejected: it makes the
  destructive path the default and defends it with a modal. The user's own framing — links
  should be standalone rows regardless of how they arrived — is a statement about ownership,
  not about warning copy.
- **Keep the cascade for `link` jobs only,** where job and link are strictly 1:1 and the card
  arguably *is* the link. Rejected: it rebuilds the exact asymmetry this ADR removes, since
  the same URL would cost you the link or not depending on whether it arrived through **Ingest
  Link** or through a bookmark file. The alternative it buys is one extra click on the 1:1
  case, against a special rule in the delete path forever.
- **Soft-delete links when their job is deleted** (set `archived = 1`, the column already
  exists at `database.py:190`). Rejected as the worst of both: the links vanish from the Links
  table and graph exactly as if deleted, so the user experiences the data loss anyway, while
  the rows stay behind to be reasoned about in every query.

## Consequences

- **Dangling `source_job` becomes the normal case, not an anomaly.** ADR-0043 already decided
  to adopt rather than delete the 137 existing orphans, and its backfill `COALESCE`s ownership
  from `jobs` with an Operator fallback for exactly this shape. The two decisions agree.
- **`_get_source_job_info` (`brain.py:519`) increasingly returns nothing**, so the "source"
  backlink in newly written Obsidian `.md` files is often absent. It was always best-effort.
- **Deleting a job stops being a way to clean up after a mistake.** Submit a video, regret it,
  delete the card — the description links stay in the Brain until removed deliberately. This is
  the intended trade: the Brain is the product, the job is the receipt.
- **ADR-0042's stated rationale is narrowed, not overturned.** Its concern — a deleted job
  remaining searchable through its links — is now handled by making that removal explicit
  rather than implicit. Its async purge half (Drive docs, GCS objects, Sheets rows) is
  untouched.
- **`database.delete_link`'s ownership derivation is unaffected today** but simplifies once
  ADR-0043 lands: its `COALESCE`-through-`source_job` becomes a direct `chat_id = ?`, after
  which no link operation reads `source_job` at all.
- **Pre-existing bug, surfaced not fixed:** neither the old cascade nor `delete_link` removes
  the link's Drive `.md` node, so Brain Drive files orphan on every deletion path
  (`# ponytail:` comment already at `database.py:2213`).
