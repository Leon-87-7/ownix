# Project-local skills

Explicit-invoke skills bundled with this repo. They sync the project's
`ISSUE_KANBAN.md` board with GitHub Issues.

| Skill | What it does | External prerequisite |
| --- | --- | --- |
| `/to-issue-kanban` | `/to-issues` + append new issues to the board | **Yes** — needs `to-issues` (see below) |
| `/triage-kanban` | `/triage` + move the issue's row to its new column | **Yes** — needs `triage` (see below) |
| `/update-kanban` | On-demand board↔GitHub reconcile + open/closed PR section | **None** — fully self-contained |
| `kanban-sync.md` | Shared board-writing helper (not a skill; called by all three) | — |

## Prerequisite for the two wrappers

`/to-issue-kanban` and `/triage-kanban` are thin wrappers over two
**third-party** skills by Matt Pocock, which are **not** vendored into this
repo. They must be installed **globally** on the machine for the wrappers to run:

- `to-issues` — https://github.com/mattpocock/skills/tree/main/skills/engineering/to-issues
- `triage` — https://github.com/mattpocock/skills/tree/main/skills/engineering/triage

Install them so they resolve at `~/.agents/skills/{to-issues,triage}/SKILL.md`
(the path the wrappers delegate to). Without them, the wrappers fail at their
"run the source flow" step.

`/update-kanban` has no source flow, so it works on a fresh clone with nothing
else installed.
