# AGENTS.md

This repo’s shared agent instructions live in [CLAUDE.md](CLAUDE.md).

Before making changes, read and follow `CLAUDE.md`. The instructions in this
`AGENTS.md` file are Codex-specific additions or overrides.
for rules read and follow `.claude/rules/*.md`.

## RTK.md

The RTK.md file is located in this path: `C:\Users\leone\.claude\RTK.md`

# Shared agent knowledge

Project-specific skills live in `agent-knowledge/`. Rules are in
`.claude/rules/` and commands in `.claude/commands/`.

Before making changes, inspect these folders for relevant guidance.

## Skill discovery

When a task matches one of the skill folders in `agent-knowledge/`, read that skill’s `SKILL.md` first.

A skill folder should follow this shape:

```txt
agent-knowledge/
  skill-name/
    SKILL.md
    reference.md
    heuristics.md
    examples.md
```


<!-- headroom:memory-instructions -->
## Memory

Use the `headroom_memory` MCP server for persistent cross-session knowledge.

**Before** answering questions about prior decisions, conventions, project context,
architecture, user preferences, org info, codenames, debugging history, or anything
from past sessions — call `memory_search` first.

**After** making durable decisions, discovering conventions, or learning important
facts — call `memory_save` to persist them for future sessions.

Memory is your first source of truth for anything not visible in the current conversation.
