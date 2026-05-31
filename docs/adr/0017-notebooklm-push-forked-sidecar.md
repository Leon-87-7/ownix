---
adr: "0017"
title: NotebookLM push via a forked, unofficial notebooklm-py in a feature-flagged sidecar
status: accepted
date: 2026-05-31
---

## Context

A core purpose of the dashboard is "build context for NotebookLM exports."
A [[Space export]] can produce a downloadable doc (md/txt/Google Doc/PDF),
but the richer goal is to push a space *straight into* NotebookLM — curated
URLs as sources, context blobs as a steering prompt.

NotebookLM has no consumer API. Two integration paths exist: the official
**NotebookLM Enterprise API** (`notebooks.sources.batchCreate`, on Google
Cloud, paid/Workspace-tier), and **`teng-lin/notebooklm-py`** (MIT) — an
unofficial tool driving consumer NotebookLM via Playwright browser
automation + a logged-in Google session cookie.

## Decision

Build "Push to NotebookLM" on a **forked and pinned** copy of
`notebooklm-py`, quarantined in its **own sidecar container** (mirroring the
`vig-transcript` pattern) behind a **feature flag**, authenticated with a
**dedicated throwaway Google account**. It is **out of MVP scope** — a
fast-follow. The MVP ships doc export only; the export composition is
designed to double as the push payload so the sidecar slots in without data-
model changes. The official Enterprise API is the documented escape hatch
if the product ever goes commercial.

## Consequences

- **Pro:** Free, and does exactly what we need (batch-add sources, set a
  steering persona/prompt) against the *consumer* NotebookLM the user
  already has.
- **Pro:** Sidecar isolation keeps Chromium's ~400 MB, the stateful browser
  session, the Google-session secret, and the unofficial-API fragility out
  of `vig-api`. If it breaks or gets blocked, the core service is untouched.
- **Con:** Built on undocumented endpoints that "can change without notice";
  pinning a fork is mandatory so an upstream release or yank can't break the
  deploy.
- **Con:** Automating consumer NotebookLM is ToS-gray — the driving Google
  account risks rate-limiting or suspension, hence a dedicated throwaway
  account, never the user's primary.

## Considered Alternatives

- **Official NotebookLM Enterprise API.** Rejected for now: enterprise-tier
  (Google Cloud, paid/Workspace) — overkill and over-cost for a single-user
  personal tool. Retained as the migration target if usage ever justifies
  it.
- **Fold the push into the core API (no sidecar).** Rejected: drags
  Chromium + the Google session secret + a fragile dependency into the lean
  FastAPI image and couples core availability to an unofficial tool.
- **Use `notebooklm-py` unforked, as a normal dependency.** Rejected:
  depending on undocumented behavior from a fast-moving package that drives
  a browser with your Google cookies is an unacceptable supply-chain risk.
