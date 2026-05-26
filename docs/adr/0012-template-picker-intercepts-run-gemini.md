---
adr: "0012"
title: Template picker keyboard intercepts "Run Gemini" instead of immediate enqueue
status: accepted
date: 2026-05-27
---

## Context

Before this decision, tapping "✨ Run Gemini" in the enrichment confirmation gate
immediately enqueued the `enrichment` task using the auto-detected template. Users
had no way to choose a different template at that moment — they had to abandon the
job and resubmit via a slash command (e.g. `/method <url>`).

Adding a `/freestyle` command (user-supplied Gemini prompt) made the one-tap-to-enqueue
path untenable: there is now a sixth option that requires a text reply before the
worker can run, so the callback can no longer jump straight to the queue.

## Decision

The `gemini_yes` callback no longer enqueues enrichment directly. Instead it sends a
**template picker keyboard**: five named templates (summary, method, technical, review,
narrative) plus "✍️ Freestyle" as inline buttons (3×2 layout). Picking a named template
collapses the keyboard to "You chose {template}" and enqueues `{"task":"enrichment"}`.
Picking Freestyle arms `chat_state(mode="awaiting_freestyle")` and sends a ForceReply;
the user's reply is stored in `jobs.freestyle_prompt` before enrichment is enqueued.

`/freestyle <url>` is also a first-class slash command (works on both short and long
URLs) for symmetry with the existing `/method`, `/technical`, etc. commands.

## Rationale

The main alternative was adding per-template buttons directly to the original
confirmation keyboard. That was rejected because six buttons plus "No Thanks" and
"Build Spec" would be visually noisy, and the Freestyle option still requires a
text-reply step that a flat keyboard cannot express.

A slash-command-only approach (no picker, just `/freestyle`) was also considered but
discarded: users who have already seen the confirmation keyboard should not need to
remember and type a second command to change the template.

## Consequences

- `_cb_gemini_yes` becomes `_cb_pick_template` (shows picker); new callbacks
  `template_pick` and `template_freestyle` handle the picker selections.
- New `chat_state` mode: `awaiting_freestyle` (same 10-minute expiry as `awaiting_intent`).
- New DB column: `jobs.freestyle_prompt TEXT` — stores the user-supplied prompt text.
- Enrichment worker reads `freestyle_prompt`; when non-null it substitutes the value
  in place of the template's `extra_instructions`.
- Explicit-command jobs (submitted via any slash command, including `/freestyle`) bypass
  the confirmation gate entirely — the auto-enqueue path is unchanged.
