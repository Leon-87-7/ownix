---
name: grilling
disable-model-invocation: true
description: Interview the user relentlessly about a plan or design. Use when the user wants to stress-test a plan before building, or uses any 'grill' trigger phrases.
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

If a question can be answered by exploring the codebase, explore the codebase instead. Start in `docs/seed/` — `CAPABILITY_MAP.md` (which module owns a capability), `FUNCTION_INDEX.md` (which helper already exists), `GLUE_INDEX_BACKEND.md` / `GLUE_INDEX_FRONTEND.md` (where it wires in) — before reading source. If the plan proposes building something already listed there, that is your next question, not a task.
