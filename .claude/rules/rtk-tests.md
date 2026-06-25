## Running tests — never through rtk

Run test suites **directly**, never through the rtk hook or `rtk proxy`:

- A bare `pytest` invocation gets mangled by the rtk rewrite hook.
- `rtk proxy pytest …` backgrounds large/full-suite runs and returns **empty output**, so you can't see pass/fail.

**Do:** invoke the runner directly with an explicit path, e.g. `python -m pytest tests/test_foo.py -q` or `python -m pytest tests -q`. If a full-suite run still gets backgrounded with empty output, split it into per-file or per-directory runs (those run foreground fine).

`rtk proxy` is still fine for other commands (e.g. `git diff`).
