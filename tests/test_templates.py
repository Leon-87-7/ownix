from src.templates import PROMPT_TEMPLATES, PromptTemplate


def test_all_five_templates_present() -> None:
    assert set(PROMPT_TEMPLATES.keys()) == {"summary", "method", "technical", "review", "narrative"}


def test_summary_extra_instructions_empty() -> None:
    assert PROMPT_TEMPLATES["summary"].extra_instructions == ""


def test_method_extra_instructions_contains_template_analysis() -> None:
    assert "template_analysis" in PROMPT_TEMPLATES["method"].extra_instructions


def test_technical_extra_instructions_contains_template_analysis() -> None:
    assert "template_analysis" in PROMPT_TEMPLATES["technical"].extra_instructions


def test_review_extra_instructions_contains_template_analysis() -> None:
    assert "template_analysis" in PROMPT_TEMPLATES["review"].extra_instructions


def test_narrative_extra_instructions_contains_template_analysis() -> None:
    assert "template_analysis" in PROMPT_TEMPLATES["narrative"].extra_instructions


def test_summary_has_no_trigger_patterns() -> None:
    assert PROMPT_TEMPLATES["summary"].trigger_patterns == []


def test_method_trigger_patterns_include_tutorial() -> None:
    assert "tutorial" in PROMPT_TEMPLATES["method"].trigger_patterns


def test_all_templates_are_prompt_template_instances() -> None:
    for t in PROMPT_TEMPLATES.values():
        assert isinstance(t, PromptTemplate)
