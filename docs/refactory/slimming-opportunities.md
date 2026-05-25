# Slimming / Deepening Opportunities

Source-of-truth notes from a CodeGraph-driven architecture pass (2026-05-25). Goal: **fewer functions, fewer files** by collapsing shallow modules and duplicated implementations into deeper ones.

Terms follow the project's domain model (`CONTEXT.md` — Job, Template, Second Brain, GeminiClient) and the architecture vocabulary from the `improve-codebase-architecture` skill (module, shallow/deep, seam, deletion test, locality, leverage).

**Method:** mapped the 33 `src/` Python modules via `codegraph_files`, then read the duplicated patterns with `codegraph_explore`. Findings below are verbatim from on-disk source.

Ranked by surface area removed.

---

## 1. Collapse the Gemini service triplet into one deep module ⭐ highest leverage

**Files:** `src/services/gemini_client.py`, `src/services/gemini.py`, `src/services/gemini_photo.py`, and `src/brain.py::_embed_sync`

**Problem:** The free→paid key fallback loop —

```python
for key in [free, paid]:
    if not key: continue
    try:
        result = await asyncio.to_thread(_call_sync, ...)
        return result
    except Exception:
        log.warning(...)
raise <Unavailable>
```

— is copy-pasted **four times**:

| Copy | Function | File |
|---|---|---|
| text | `GeminiClient.generate` | `gemini_client.py` |
| video Vision | `call_gemini_vision` | `gemini.py` |
| photo Vision | `call_gemini_photo_links` | `gemini_photo.py` |
| embeddings | `_embed_sync` (sync key loop) | `brain.py` |

Additional duplication in the same cluster:
- `_extract_json` is **byte-identical** in `gemini.py` (L34–38) and `gemini_photo.py` (L80–84).
- `resolve_tool_urls` — a *text* call — lives in the "vision" file (`gemini.py`) and re-implements JSON-fence stripping inline (L98–100) instead of using the `_extract_json` defined right above it.

CONTEXT.md's `GeminiClient` glossary entry explicitly scoped the client to text and left "Vision and embedding calls… their own loops." **That decision is the source of the duplication.**

**Solution:** One `gemini` module owning a single fallback loop, one `_call_sync(parts, *, model, schema, config)`, one `_extract_json`. Text / video-vision / photo-vision / embed become thin wrappers that assemble `parts` and pass model + schema. ADR-0006's key-iteration policy then lives in exactly one place.

**Benefits:**
- *Leverage* — all retry/threading sits behind a small interface (`generate` / `generate_vision` / `embed`).
- *Locality* — changing the fallback policy (add a key, change logging) touches one function, not four.
- *Tests* — the "both keys fail" path needs one test instead of three (`GeminiUnavailableError` / `RuntimeError` is currently raised in three separate places).

> ⚠️ **Reopens a documented decision.** The CONTEXT.md glossary states vision/embedding keep their own loops. Worth reopening because four copies is real friction, not theoretical. Does **not** contradict ADR-0006 (free→paid policy) — it honors it by putting the policy in one place.

---

## 2. Two template-matching tables → one

**Files:** `src/validation.py`, `src/processors/long_video.py::detect_template`, `src/templates.py`

**Problem:** "Score text against per-template keyword sets, pick the best" exists **twice with two different tables**:
- `TEMPLATE_INDICATORS` in `validation.py` → drives `validate_template_choice` (mismatch warnings for explicit-command jobs).
- `PROMPT_TEMPLATES[*].trigger_patterns` in `templates.py` → drives `long_video.detect_template` (auto-routing for plain-URL jobs).

Two sources of truth for the same concept — *which Template fits a transcript* — that can silently diverge.

**Solution:** Let the Template module (`templates.py`) own the single keyword table; fold both `detect_template` and `validate_template_choice` into scoring functions that read it. This absorbs `validation.py` entirely → **one fewer file**.

**Benefits:**
- *Locality* — adding a "review" keyword updates routing and validation together.
- *Leverage* — Template becomes the one place that knows how text maps to a template.

> Bonus: also resolves the `validation.py` vs `utils/validators.py` near-homonym naming hazard for free (the former disappears).

---

## 3. Deduplicate the Job-ID generator

**Files:** `src/database.py::generate_job_id`, `src/brain.py::generate_link_id`

**Byte-identical** except the docstring — both emit `YYYYMMDD_HHMMSS_XXXX`:

```python
def generate_job_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2).upper()
    return f"{ts}_{suffix}"
```

**Deletion test:** removing either just redirects to the other — pure duplication, no complexity concentrated. → One `generate_id()`.

---

## 4. Fold `build_links_message` into `build_enriched_links_message`

**File:** `src/utils/markdown.py`

Both emit the identical envelope:

```
🔗 Links Found:
{labeled}

---

🔗 Quick Links:
{bare}
```

`build_enriched_links_message` is a strict superset — its `others` branch already handles links with no `_enriched` data. Delete the simpler one, repoint callers. One message format, one place to change the envelope.

---

## 5. Shared `EMBEDDING_DIM`

**Files:** `src/brain.py`, `src/processors/enrichment.py` — `EMBEDDING_DIM = 768` defined in both. Define once, import. (Resolves on its own if #1 lands and embeddings move into the gemini module.)

---

## Not worth touching

- **`webhook.py`** — biggest file (50 symbols) but CONTEXT documents its dispatch-table design (`_CALLBACK_TABLE` / `_SLASH_TABLE`) as deliberate. It's *deep*, not bloated.
- **`prd.py::run_prd`** — already a good consolidation (the "PRD skeleton" with `run_auto` / `run_intent` as thin wrappers).

---

## Suggested sequencing

| Priority | Item | Effort | Risk | Removes |
|---|---|---|---|---|
| 1 | #2 template tables | medium | low | 1 file, 1 keyword-table duplication |
| 2 | #1 Gemini triplet | high | medium (reopens a decision) | ~3 fallback loops, 1 dup `_extract_json`, → 1 module |
| — | #3 ID gen | trivial | none | 1 function |
| — | #4 markdown | trivial | none | 1 function |
| — | #5 EMBEDDING_DIM | trivial | none | 1 constant dup |

#1 and #2 are the real "fewer files / fewer functions" wins. #3–#5 are quick, low-risk cleanups that batch into a single pass.

**Next step:** pick a candidate to grill — design the deepened interface, decide what sits behind the seam, and confirm which tests survive. If #1 is chosen, also decide whether to record the CONTEXT.md "own loops" reversal as an ADR.
