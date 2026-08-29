# Long-video screenshot capture's trigger mirrors Mini-PRD's lock+background pattern, not /checklists' synchronous pattern

This codebase has two existing shapes for an on-demand, job-scoped Gemini action: `/checklists` (single fast inline Gemini call, no lock, synchronous request/response — see `src/processors/checklists.py`) and Mini-PRD (`prd.py`'s atomic `{slot}_status` lock column via `_acquire_prd_lock` + `spawn_background`, client polls for completion).

Screenshot capture is much closer to Mini-PRD in cost, not to checklists: it downloads up to a 90-minute video, runs ffmpeg scene detection, calls Gemini Vision, and does N Drive uploads. Holding a synchronous HTTP request open for that (the checklists shape) risks real timeouts, and a double-click without a lock would waste a full video download rather than one cheap Gemini call.

It uses a `screenshots_status` lock column (same conditional-`UPDATE ... WHERE status IS NULL OR status IN ('error','done')` shape as `_acquire_prd_lock`) plus `spawn_background`; the job-detail button polls rather than awaiting a response inline.

`/checklists` is the newer and more visible precedent for "add another on-demand job action," so it's the one a future engineer will likely reach for first. Check the cost profile before copying it — its no-lock, synchronous shape is only safe for genuinely cheap, single-call work.
