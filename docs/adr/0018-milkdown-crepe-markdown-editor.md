---
adr: "0018"
title: Dashboard editor is Milkdown/Crepe (markdown-native WYSIWYG)
status: accepted
date: 2026-05-31
---

## Context

Context blobs and job notes are edited in the dashboard and stored as
**markdown** — the storage, the [[Space export]], and the NotebookLM/gdoc/
pdf targets all assume markdown end-to-end. The editor choice has to hold
that contract *and* not exclude non-technical users (the product is
single-user now, multi-tenant SaaS-light later). The original plan named
TipTap, whose document model is HTML/JSON, not markdown.

Two requirements pull in tension: **markdown as the source of truth** (no
lossy round-trip into the export) and **no markdown syntax shown to
non-technical users** (a raw `**bold**` textarea excludes them).

## Decision

Use **Milkdown via `@milkdown/crepe`** — a markdown-native WYSIWYG. The
human sees a Google-Docs-like surface (toolbar, slash menu, inline
formatting, no syntax); the editor stores clean markdown (ProseMirror +
Remark). Typora-style input rules also let power users *type or paste*
markdown and have it render, so the contract holds in both directions. One
`'use client'` `MarkdownEditor.tsx` (Crepe + the `markdownUpdated` listener,
debounced save) is reused for both blobs and notes.

## Consequences

- **Pro:** Inclusion from day one — non-technical users never meet markdown
  syntax — while the stored bytes remain markdown, so there is no
  serialization seam between a note and the artifact fed to NotebookLM.
- **Pro:** Crepe is batteries-included (toolbar/slash/GFM), so build cost is
  a small component, not a hand-built editor.
- **Con:** Crepe's chrome is less customizable than a bespoke toolbar; if
  that's ever needed, drop to the headless `@milkdown/kit` path without
  changing the storage contract.
- **Con:** Milkdown touches DOM APIs — must be a client component, init in
  `useEffect`, `destroy()` on unmount (Next.js SSR), and StrictMode double-
  mount needs the cleanup to be correct.

## Considered Alternatives

- **Raw-markdown editor (`@uiw/react-md-editor`).** Best contract fidelity
  and lowest effort, but exposes markdown syntax — excludes non-technical
  users. Rejected on the inclusion requirement.
- **HTML/JSON-native WYSIWYG (TipTap, Lexical, Plate, BlockNote).** Rejected:
  markdown is only a lossy import/export; typed `**bold**` is treated as
  literal text and the round-trip into the export degrades.
- **MDXEditor.** Markdown-capable WYSIWYG, but ~851 kB gzipped, drags in
  MDX/JSX we never use, and has documented inline-rendering issues. Rejected
  on weight and surface.
