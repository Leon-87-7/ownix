## Running tests — never through rtk

Run test suites **directly**, never through the rtk hook or `rtk proxy`:

- A bare `pytest` invocation gets mangled by the rtk rewrite hook.
- `rtk proxy pytest …` backgrounds large/full-suite runs and returns **empty output**, so you can't see pass/fail.

**Root cause (confirmed 2026-07-24):** the `PreToolUse` hook (`rtk hook claude`, in `settings.json`) is registered with `"matcher": "Bash"` — it rewrites *every* Bash-tool command transparently, including `python -m pytest ...` typed with an explicit path. Rephrasing the command inside the Bash tool does not escape it; the rewrite happens no matter how the command is worded, and pytest runs on this machine consistently hang/background with empty output when routed through `rtk pytest`, even for a single mid-size test file.

**Do:** run pytest via the **PowerShell tool**, not the Bash tool — the hook's matcher only catches `Bash`, so PowerShell invocations reach `python -m pytest` unmodified and return real output. e.g. `PowerShell: python -m pytest tests/test_foo.py -q`. Split large runs into per-file/per-directory invocations regardless of which tool you use — smaller runs are just faster and easier to read, not a workaround for the hook itself.

`rtk proxy` (via Bash) is still fine for other commands (e.g. `git diff`).
