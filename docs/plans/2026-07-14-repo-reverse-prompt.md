# Repo Reverse Prompt Segment

## Goal

Add a repo-pipeline segment that can reverse engineer a public GitHub repository into a synthetic AI-coding prompt: the kind of prompt someone might have used to create the repo with an AI coding assistant.

This should not become a standalone GitReverse-style web app. Ownix already has the repo ingestion, GitHub bundle fetch, LLM analysis, dashboard rendering, Telegram bot intake, Sheets, and Brain integration. The feature should reuse that pipeline and add a new trigger/mode.

## Thought Path

The starting prompt describes building a simple Next.js app that accepts a GitHub URL or `owner/repo`, fetches metadata/tree/README through the GitHub API, and calls OpenRouter to generate a final prompt.

In Ownix, the relevant backend already exists:

- `src/services/github.py::fetch_repo_bundle()` fetches repo metadata, README, recursive tree, manifests, subproject READMEs, preprocesses README content, and caches the bundle in Redis.
- `src/processors/repo.py::run()` already owns the repo job flow: fetch GitHub bundle, build a repo context prompt, call text generation, persist `template_analysis`, render Markdown, send Telegram output, append Sheets, and ingest to Brain.
- `web/components/feed/submit-job.tsx` already owns the dashboard submit modal and keyboard launcher.
- `src/telegram/webhook.py` already routes GitHub URLs into repo jobs.
- `src/services/gemini.py::generate()` is the current text-generation seam, and `docs/TASK.md` already notes that OpenRouter/Groq should sit behind the same text-only generation seam as a second provider. Vision, photo, audio, and embeddings stay Gemini.

So the implementation should be additive: one new repo mode, one shared parser, one bot command, and one dashboard command path.

## Core Decisions

1. Keep `content_type = "repo"`.

   Reverse engineering a repo is still a repo job. A new content type would duplicate feed filters, badges, thumbnail handling, job detail fields, Sheets routing, and worker dispatch.

2. Represent reverse prompt as a repo mode.

   Preferred first implementation:

   ```text
   template = "repo_reverse_prompt"
   ```

   This reuses the existing `jobs.template` column and avoids a schema migration. `repo.py` treats this value as a reserved internal repo mode. Normal video/article templates still do not apply to repo jobs.

3. Store the synthetic prompt inside `template_analysis`.

   Shape:

   ```json
   {
     "title": "...",
     "tagline": "...",
     "tech_stack": [],
     "key_components": [],
     "for_developers": {},
     "for_education": {},
     "synthetic_prompt": "Build a..."
   }
   ```

   The dashboard already renders arbitrary nested JSON in `template_analysis`, so this gets a visible dashboard result without a DB migration.

4. Add OpenRouter through the shared text-generation interface.

   Do not hardwire OpenRouter only into `repo.py`. Add a small OpenRouter adapter and put it behind the text-generation seam so repo reverse prompt generation benefits from the broader Gemini resilience plan.

   Text fallback target:

   ```text
   Gemini free -> Gemini paid -> OpenRouter
   ```

   Vision/photo/audio/embeddings remain Gemini for this slice.

5. Use `r owner/repo` as the command for repo analysis plus reverse prompt.

   Normal repo URL submission can remain normal repo analysis. The explicit `r` command means "reverse engineer this GitHub repo."

## Backend Plan

### 1. Shared Repo Reference Parser

Add a helper in `src/utils/validators.py`, for example:

```python
def normalize_repo_reference(value: str) -> str:
    ...
```

It should accept:

```text
owner/repo
https://github.com/owner/repo
https://github.com/owner/repo/tree/main
https://github.com/owner/repo/blob/main/README.md
```

It should return:

```text
https://github.com/owner/repo
```

It should reject:

```text
https://example.com/foo
github.com
github.com/owner
gist.github.com/owner/id
github.mycompany.com/owner/repo
```

Keep existing reserved GitHub path behavior consistent with `detect_pipeline()`.

### 2. Job Creation API

Update `src/api/jobs.py::JobCreateRequest` and `create_job()`.

Rules:

- `template = "repo_reverse_prompt"` is allowed only for GitHub repo refs.
- When reverse mode is present, canonicalize `owner/repo` and full GitHub URLs through `normalize_repo_reference()`.
- Non-reverse repo submissions keep the current behavior: repo jobs ignore normal video/article templates.
- If reverse mode receives a non-GitHub URL, return a 422 with:

```text
R command is for reverse engineering a Github repo, try again
```

### 3. Repo Processor

Extend `src/processors/repo.py`.

Add:

- `REPO_REVERSE_PROMPT_SCHEMA`
- `_build_repo_reverse_prompt(bundle: dict, analysis: dict) -> str`
- `_generate_reverse_prompt(bundle: dict, analysis: dict) -> str`

Flow:

```text
fetch_repo_bundle
run existing structured repo analysis
if template == "repo_reverse_prompt":
    build reverse prompt context from bundle + analysis
    call text-generation seam
    analysis["synthetic_prompt"] = generated prompt
persist analysis into template_analysis
render Markdown
send Telegram summary/document
Sheets/Brain as today
```

The reverse prompt context should reuse the exact GitHub bundle already fetched for the normal repo analysis:

- repo metadata
- description/topics/stars/forks/language
- README
- prioritized file tree
- manifests
- subproject READMEs
- existing structured analysis

Prompt instruction should ask for a single useful build prompt, not a generic summary. It should preserve evidenced stack and behavior, avoid claiming hidden files, and write in a form suitable for an AI coding assistant.

### 4. Markdown Rendering

Update `render_repo_markdown()` to include:

```md
## Synthetic Build Prompt

...
```

Only render this section when `analysis.synthetic_prompt` is present.

The Telegram summary can mention that a reverse prompt was generated, but the full prompt should live in the Markdown artifact and dashboard detail.

### 5. OpenRouter Adapter

Add `src/services/openrouter.py`.

Minimal interface:

```python
async def generate(prompt: str, *, model: str, schema: dict | None = None) -> str:
    ...
```

Use OpenRouter's OpenAI-compatible chat completions endpoint. Prefer raw HTTP with the backend's existing HTTP style unless adding an SDK becomes useful later.

Add config in `src/config.py`:

```python
OPENROUTER_API_KEY: str = ""
OPENROUTER_TEXT_MODEL: str = ""
REPO_REVERSE_PROMPT_MODEL: str = ""
```

`REPO_REVERSE_PROMPT_MODEL` can default to `OPENROUTER_TEXT_MODEL` or the current Gemini flash model depending on the final generation interface.

## Telegram Bot Plan

Add a plain-text shortcut before normal URL routing in `src/telegram/webhook.py::_route_text()`.

Behavior:

```text
r owner/repo
```

Creates a repo job with:

```text
content_type = "repo"
template = "repo_reverse_prompt"
url = "https://github.com/owner/repo"
```

Also accept:

```text
r https://github.com/owner/repo
```

Reject:

```text
r https://example.com/foo
```

Reply:

```text
R command is for reverse engineering a Github repo, try again
```

This logic should sit before `_route_url()` because `r ...` is not a URL. It should be near the existing plain-text slash shortcut and user-template shortcut logic.

## Dashboard Plan

### 1. Submit Modal Command Parsing

Update `web/components/feed/submit-job.tsx::submitJob()`.

Parse command prefixes from the existing input:

```text
n owner/repo
r owner/repo
r https://github.com/owner/repo
```

Desired behavior:

- `n owner/repo` submits normal repo analysis.
- `r owner/repo` submits repo analysis plus reverse prompt.
- `r https://github.com/owner/repo` submits repo analysis plus reverse prompt.
- `r https://example.com/foo` shows the modal error:

```text
R command is for reverse engineering a Github repo, try again
```

When reverse mode is detected, post:

```json
{
  "url": "https://github.com/owner/repo",
  "template": "repo_reverse_prompt"
}
```

### 2. Command Launcher

Add a "Reverse engineer repo" action to the command launcher in `web/components/feed/submit-job.tsx`.

Shortcut:

```text
R
```

Action:

- close the command launcher
- open the Submit URL modal
- prefill the input with `r `

This makes the command discoverable while reusing the existing modal and error display.

### 3. Optional Form Copy

Keep the UI minimal. If copy is needed, use placeholder/help text sparingly, for example:

```text
Paste a URL, n owner/repo, or r owner/repo...
```

Avoid a separate reverse-engineering page for this slice.

## Sheets Plan

First version can skip Sheets changes because `template_analysis` already stores the prompt.

Optional follow-up:

- Add a trailing `synthetic_prompt` column to the repo sheet row in `src/services/sheets.py::_repo_row()`.
- Update `tests/test_sheets.py` expected column count.
- Update the actual Google Sheet header.

Do this only if the prompt needs to be first-class in Sheets.

## Test Plan

### Backend Validators

Add tests in `tests/test_validators.py`:

- accepts `owner/repo`
- accepts full GitHub repo URL
- strips subpaths
- rejects non-GitHub URLs
- rejects org-only and reserved GitHub paths

### Jobs API

Add tests in `tests/test_jobs_api.py`:

- `template=repo_reverse_prompt` plus `owner/repo` creates a repo job.
- `template=repo_reverse_prompt` plus GitHub URL creates a repo job.
- `template=repo_reverse_prompt` plus non-GitHub URL returns 422 with the exact error.
- normal repo submissions still clear unsupported template values.

### Telegram

Add tests in `tests/test_webhook.py`:

- `r owner/repo` enqueues a repo job with `template="repo_reverse_prompt"`.
- `r https://github.com/owner/repo` does the same.
- `r https://example.com/foo` sends the exact error.
- plain GitHub URL still follows normal repo routing.

### Repo Processor

Add tests in `tests/test_repo_pipeline.py`:

- reverse mode calls the reverse prompt generator.
- generated prompt is persisted under `template_analysis.synthetic_prompt`.
- Markdown includes `## Synthetic Build Prompt`.
- non-reverse repo jobs do not generate the synthetic prompt.

### OpenRouter

Add tests in `tests/test_openrouter.py`:

- sends bearer token.
- sends selected model.
- sends plain prompt.
- sends schema/structured-output request when a schema is provided.
- parses returned content.
- raises the shared text-generation error type on failure.

### Dashboard

Add tests in `web/components/feed/submit-job.test.tsx`:

- `r owner/repo` posts canonical GitHub URL with `template="repo_reverse_prompt"`.
- `r https://github.com/owner/repo` posts reverse mode.
- `r https://example.com/foo` shows `R command is for reverse engineering a Github repo, try again`.
- command launcher "Reverse engineer repo" opens the submit modal prefilled with `r `.

## Implementation Order

1. Add parser and backend tests.
2. Add API reverse-mode validation.
3. Add repo processor reverse prompt schema/build/render/persist path.
4. Add OpenRouter adapter behind text generation.
5. Add Telegram `r` command.
6. Add dashboard modal parsing and command launcher action.
7. Add/adjust focused tests.
8. Run focused backend tests and focused web tests.

## Non-Goals For This Slice

- No standalone Next.js GitReverse app.
- No new `content_type`.
- No new dashboard page unless the detail view proves insufficient.
- No migration to general document-output cards for repo jobs.
- No OpenRouter use for vision/photo/audio/embeddings.
- No broad Gemini resilience/backoff/requeue work beyond what is needed for the repo reverse prompt.

