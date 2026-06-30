---
name: grill-with-search-docs
description: Grilling session that challenges your plan against the existing domain model and the *current* docs of any third-party tool it depends on — probing context7 first and falling back to web search whenever a challenge hinges on how an external API/SDK/library actually behaves. Sharpens terminology and updates documentation (CONTEXT.md, ADRs) inline as decisions crystallise. Use when a plan leans on third-party integrations (greenfield or existing) and you want it stress-tested against real, up-to-date tool behavior rather than stale memory.
---

<what-to-do>

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring the codebase, explore the codebase instead. If a challenge hinges on how a third-party tool actually behaves — what an external API, SDK, or library can or can't do — you MUST ground yourself in current docs before pressing the point (see "Ground third-party challenges in current docs" below).

</what-to-do>

<supporting-info>

## Domain awareness

During codebase exploration, also look for existing documentation:

### File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Ground third-party challenges in current docs

When you're about to challenge a point that depends on a third-party tool's real behavior — greenfield or already integrated — do not grill from memory or from existing code paths, both of which go stale. This is a hard rule, not a suggestion.

1. **Probe context7 first** (`ctx7` CLI / context7 MCP) for the specific capability in question.
2. **Fall back to web search** if context7 has no match *or* returns docs that don't cover the specific capability being challenged.
3. Fire **lazily** — only at the moment a specific claim hinges on the tool, not the instant a tool name is mentioned.
4. When a verified fact *drives a design decision*, capture it in the relevant **ADR's Context/Consequences** — never in `CONTEXT.md` (that stays domain vocabulary only).

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

Don't couple `CONTEXT.md` to implementation details. Only include terms that are meaningful to domain experts.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).

</supporting-info>
