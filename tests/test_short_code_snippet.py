from src.processors.short_video import _build_analysis_markdown, _code_block

JOB = {"id": "j1", "url": "https://x.test/r/1"}


def test_fence_widens_past_backticks_in_code():
    # Markdown inside the snippet must not break out of the fence.
    assert _code_block("const md = ```x```", "js").startswith("````js\n")
    assert _code_block("a = 1", "python") == "```python\na = 1\n```"


def test_code_section_only_when_code_present():
    assert "## Code" not in _build_analysis_markdown(JOB, "tiktok", "v", "s", [])
    md = _build_analysis_markdown(JOB, "tiktok", "v", "s", [], "a {\n  b: c;\n}", "css")
    assert "## Code\n\n```css\na {\n  b: c;\n}\n```" in md


if __name__ == "__main__":
    test_fence_widens_past_backticks_in_code()
    test_code_section_only_when_code_present()
    print("ok")
