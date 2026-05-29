## What to build

Replace the stub message from #67 with a real **Gemini analysis** call. Send the bundle (metadata + preprocessed README + tree + manifests) to `gemini-2.5-flash` with a structured-output schema, persist the analysis in `jobs.template_analysis` (ADR-0008 JSON-blob precedent), and emit a summary Telegram message with the dual-audience teaser format + a `✍️ Freestyle` inline button.

Behavior:

- New constant `REPO_ANALYSIS_SCHEMA` in `processors/repo.py` (Pydantic model or response_schema dict — match the existing `enrichment.py` / `prd.py` pattern). Shape (spec **§Output schema**):

  ```python
  {
    "title": str,
    "tagline": str,
    "tech_stack": list[str],
    "for_developers": {
      "project_ideas": list[str],
      "when_to_use": str,
      "avoid_when": str,
    },
    "for_education": {
      "concepts_taught": list[str],
      "prerequisites": list[str],
      "curriculum_hooks": list[{"concept": str, "file_pointer": str | None, "why": str}],
    },
  }
  ```

- `_build_repo_prompt(bundle, freestyle_prompt: str | None = None, flags: dict | None = None) -> str` colocated in `processors/repo.py`. Follow the system frame + user payload outline in spec **§`_build_repo_prompt` outline**. The `freestyle_prompt`, when set, replaces the default extraction-focus block; `flags` carries `archived` / `no_readme` so the prompt can adjust its instructions (e.g. for `no_readme`, instruct Gemini to lean on tree + manifests).
- Call goes through the existing `src/services/gemini.generate` with `model="gemini-2.5-flash"`, structured-output enabled, schema = `REPO_ANALYSIS_SCHEMA`. Reuses the free→paid key fallback loop (no per-pipeline duplication).
- Result JSON stored in `jobs.template_analysis` (ADR-0008). Top-level fields also mirrored into existing `jobs` columns: `title` (the GitHub `owner/repo`), `ai_topic` ← `tagline`, `ai_objective` ← `for_developers.when_to_use`, `ai_action_points` ← `for_developers.project_ideas` JSON-encoded, `ai_tools` ← `tech_stack` JSON-encoded.
- Stub message replaced by the **summary message** (spec **§Summary message template**):

  ```
  📦 {owner}/{repo}
  {tagline}

  ⭐ {stars:,} | 🔀 {forks:,} | 💻 {language} | 📅 {N days ago}

  🛠 For developers
    {first project_idea, truncated to 80 chars}…

  🎓 For teaching
    {first concept from concepts_taught} • {first curriculum_hook.concept}…

  🔗 {repo_url}
  ```

  Followed by an inline keyboard with a single `✍️ Freestyle` button. The Freestyle button callback wires through the existing `awaiting_freestyle` `chat_state` machinery (re-uses #67's queue path — `/freestyle` slash command already accepts any `detect_pipeline`-valid URL).

- Document delivery, Sheets row, and brain ingest are **deliberately not in this slice** — they ship in #4/#5/#6 respectively, each parallel-eligible after this one.

Reference spec: **§Design Decisions** (#3, #4, #14, #15, #17, #26), **§Output schema**, **§`_build_repo_prompt` outline**, **§Summary message template**, **§Architecture → Data flow**, **§Build Order Phase 5**.

## Acceptance criteria

- [ ] `REPO_ANALYSIS_SCHEMA` defined with all spec fields; `for_education.curriculum_hooks` is an array of objects with `concept`, optional `file_pointer`, `why`.
- [ ] `_build_repo_prompt(bundle)` produces a prompt string containing: repo metadata block, file-tree block, manifest contents block, preprocessed README block, and the structured-extraction system frame.
- [ ] `_build_repo_prompt(bundle, freestyle_prompt="explain it to a Rust dev")` substitutes the user's instructions in place of the default extraction focus.
- [ ] `_build_repo_prompt(bundle, flags={"no_readme": True})` adjusts the prompt to instruct Gemini to lean on tree + manifests.
- [ ] `processors.repo.run` calls `gemini.generate` with `model="gemini-2.5-flash"` and the structured schema; the returned dict matches the schema (validated either by Pydantic or by manual assertion).
- [ ] `jobs.template_analysis` contains the full analysis JSON after a successful run; `jobs.title`, `jobs.ai_topic`, `jobs.ai_objective`, `jobs.ai_action_points`, `jobs.ai_tools` are populated as described.
- [ ] Summary Telegram message renders all the spec'd fields and includes the `✍️ Freestyle` inline button.
- [ ] Cache hit path: when `github_repo_bundle:` is hit, no GitHub call fires; Gemini still runs (re-running analysis on the same bundle is the normal `/freestyle` re-run path's hot path).
- [ ] Tests: schema definition shape; prompt builder for the three cases above; end-to-end `run` invocation with a mocked Gemini client.
- [ ] PR demo: paste a real repo URL on a chat connected to the bot; verify the summary message lands with all sections populated.

## Blocked by

- #67 — needs the bundle + cache path producing a real bundle to send to Gemini.
