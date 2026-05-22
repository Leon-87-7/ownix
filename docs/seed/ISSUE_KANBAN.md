# Issue Kanban

> Read-only snapshot — authoritative state lives on [GitHub Issues](https://github.com/Leon-87-7/vig/issues).  
> Update this file whenever an issue moves columns.

---

## Done

|                                               # | Title                                                                         | Area        | Notes                       |
| ----------------------------------------------: | ----------------------------------------------------------------------------- | ----------- | --------------------------- |
| [#1](https://github.com/Leon-87-7/vig/issues/1) | Scaffold + URL echo — FastAPI + worker + Redis + SQLite + task-envelope queue | Infra       | Closed on GH                |
| [#2](https://github.com/Leon-87-7/vig/issues/2) | Short video pipeline (Frames → Gemini Vision → Drive → Sheets → Telegram)     | Short Video | Merged; GH issue still open |
| [#3](https://github.com/Leon-87-7/vig/issues/3) | Long video Phase 1 — transcript + metadata + description links + buttons      | Long Video  | Merged; GH issue still open |
| [#4](https://github.com/Leon-87-7/vig/issues/4) | Long video Phase 2 — Gemini enrichment + URL-resolution prompt                | Long Video  | Merged; GH issue still open |
| [#5](https://github.com/Leon-87-7/vig/issues/5) | Second Brain — brain.py module (ingest, search, rebuild, refresh worker)      | Brain       | Merged; GH issue still open |
| [#8](https://github.com/Leon-87-7/vig/issues/8) | Short Sheet brain backfill — one-off script to seed brain corpus              | Brain / Short | Merged; GH issue still open |
| [#9](https://github.com/Leon-87-7/vig/issues/9) | Long Sheet brain backfill + resolve_tool_urls helper + URL Resolution Prompt  | Brain / Long  | Merged; GH issue still open |
| [#11](https://github.com/Leon-87-7/vig/issues/11) | Photo link extraction — Gemini Vision OCR on uploaded screenshots           | Photo / Brain | Merged; GH issue still open |
| [#6](https://github.com/Leon-87-7/vig/issues/6) | Mini-PRD auto slot — tail-call enqueue, Flash, JSON schema, Drive + Sheets + brain | Mini-PRD | Merged; GH issue still open |
| [#7](https://github.com/Leon-87-7/vig/issues/7) | Mini-PRD intent slot + /spec command + chat_state routing                          | Mini-PRD | Merged; GH issue still open |
| [#13](https://github.com/Leon-87-7/vig/issues/13) | Add retry button on Gemini enrichment failures                                     | Long Video    | Merged; GH issue still open |
| [#15](https://github.com/Leon-87-7/vig/issues/15) | feat: extend transcript sidecar to support TikTok/Instagram via yt-dlp            | Short Video   | Merged; closed on GH        |

---

## Ready for Agent

Ordered by unblocked-first, then dependency chain.

|                                                 # | Title                                                                              | Area          | Depends On          |
| ------------------------------------------------: | ---------------------------------------------------------------------------------- | ------------- | ------------------- |
| (none)                                            |                                                                                    |               |                     |

---

## Ready for Human

|                                                 # | Title                                                | Area | Notes                                    |
| ------------------------------------------------: | ---------------------------------------------------- | ---- | ---------------------------------------- |
| [#10](https://github.com/Leon-87-7/vig/issues/10) | BotFather command registration + ops runbook updates | Ops  | Manual config in BotFather; no code path |

---

## Dependency Map

```
#1 Scaffold ✓
├── #2 Short pipeline ✓
│   └── #8 Short brain backfill ✓
├── #3 Long Phase 1 ✓
│   ├── #4 Long Phase 2 ✓
│   └── #9 Long brain backfill ✓
└── #5 Second Brain ✓
    ├── #8 ✓
    ├── #9 ✓
    ├── #11 Photo link extraction ✓
    ├── #6 Mini-PRD auto ✓
    │   └── #7 Mini-PRD intent ✓
    │       └── #13 Enrichment retry button ✓
    └── (feeds #4 via URL-resolution)

#10 BotFather (standalone, any time)
#15 Transcript sidecar TikTok/Instagram ✓
```
