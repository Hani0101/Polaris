"""Key check before a quiz is stored: QZ-12.

A second model answers the quiz without the key. These tests use a fake
query_fn in place of the Claude CLI.
"""

import asyncio
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage, SystemMessage

from polaris.key_check import (
    ANSWER_SCHEMA,
    ClaudeKeyCheck,
    KeyCheckFailed,
    key_check_options,
    quiz_prompt,
)
from polaris.login import ApiKeyPresent


def _quiz() -> dict:
    return {
        "title": "Fractions",
        "questions": [
            {
                "id": "q1",
                "prompt": "What is 1/2 + 1/4?",
                "choices": [
                    {"id": "a", "text": "2/6"},
                    {"id": "b", "text": "3/4"},
                ],
            },
            {
                "id": "q2",
                "prompt": "Which is larger, 2/3 or 3/5?",
                "choices": [
                    {"id": "a", "text": "2/3"},
                    {"id": "b", "text": "3/5"},
                ],
            },
        ],
    }


def _result(**overrides) -> ResultMessage:
    fields = {
        "subtype": "success",
        "duration_ms": 1,
        "duration_api_ms": 1,
        "is_error": False,
        "num_turns": 1,
        "session_id": "sdk-1",
        "result": None,
        "errors": None,
    }
    fields.update(overrides)
    return ResultMessage(**fields)


def _answering(*messages):
    seen: dict = {}

    async def fake_query(*, prompt, options, **_kwargs):
        seen["prompt"] = prompt
        seen["options"] = options
        for message in messages:
            yield message

    return fake_query, seen


def _run(tmp_path: Path, fake_query, quiz: dict | None = None) -> dict[str, str]:
    checker = ClaudeKeyCheck(tmp_path, query_fn=fake_query)
    return asyncio.run(checker.answer(quiz if quiz is not None else _quiz()))


def test_key_check_options_match_the_sdk_docs(tmp_path: Path):
    options = key_check_options(cwd=tmp_path)

    assert options.model == "haiku"
    assert options.tools == []
    assert options.allowed_tools == []
    assert options.skills == []
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.verbatim_prompts is True
    assert options.permission_mode == "dontAsk"
    assert options.cwd == tmp_path
    assert options.output_format == {
        "type": "json_schema",
        "schema": ANSWER_SCHEMA,
    }
    prompt = options.system_prompt
    assert isinstance(prompt, str)
    assert "exactly one choice id" in prompt
    assert "the one that is correct" in prompt
    assert "Do not teach" in prompt


def test_quiz_prompt_never_contains_the_key():
    quiz = _quiz()
    quiz["questions"][0]["correct_choice_id"] = "b"
    quiz["questions"][0]["explanation"] = "SECRET-EXPLANATION quarters add up"
    quiz["questions"][0]["choices"][0]["why_wrong"] = "SECRET-NOTE added tops"
    quiz["questions"][1]["correct_choice_id"] = "a"
    quiz["questions"][1]["explanation"] = "SECRET-EXPLANATION common denominator"

    prompt = quiz_prompt(quiz)

    assert "correct_choice_id" not in prompt
    assert "SECRET" not in prompt
    assert "explanation" not in prompt
    assert "why_wrong" not in prompt
    assert "Fractions" in prompt
    assert "q1" in prompt and "q2" in prompt
    assert "What is 1/2 + 1/4?" in prompt
    assert "- b: 3/4" in prompt


def test_the_check_sees_no_key_even_when_the_stored_quiz_is_passed(
    tmp_path: Path,
):
    quiz = _quiz()
    quiz["questions"][0]["correct_choice_id"] = "b"
    quiz["questions"][0]["explanation"] = "SECRET-EXPLANATION"
    fake_query, seen = _answering(
        _result(
            structured_output={
                "answers": [
                    {"question_id": "q1", "choice_id": "b"},
                    {"question_id": "q2", "choice_id": "a"},
                ]
            }
        )
    )

    _run(tmp_path, fake_query, quiz)

    assert "SECRET" not in seen["prompt"]
    assert "correct_choice_id" not in seen["prompt"]


def test_key_check_maps_each_question_to_its_choice(tmp_path: Path):
    fake_query, seen = _answering(
        SystemMessage(subtype="init", data={"apiKeySource": "none"}),
        _result(
            structured_output={
                "answers": [
                    {"question_id": "q2", "choice_id": "a"},
                    {"question_id": "q1", "choice_id": "b"},
                ]
            }
        ),
    )

    answers = _run(tmp_path, fake_query)

    assert answers == {"q1": "b", "q2": "a"}
    assert seen["options"].model == "haiku"
    assert "What is 1/2 + 1/4?" in seen["prompt"]


def test_key_check_fails_when_the_query_raises(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del prompt, options
        if False:
            yield
        raise RuntimeError("CLI down")

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_without_a_result(tmp_path: Path):
    fake_query, _ = _answering(
        SystemMessage(subtype="init", data={"apiKeySource": "none"})
    )

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_on_an_error_result(tmp_path: Path):
    fake_query, _ = _answering(
        _result(
            subtype="error_max_structured_output_retries",
            is_error=True,
            errors=["no valid output"],
        )
    )

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_on_success_without_structured_output(tmp_path: Path):
    fake_query, _ = _answering(_result(result="b and a"))

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_when_a_question_is_not_answered(tmp_path: Path):
    fake_query, _ = _answering(
        _result(
            structured_output={
                "answers": [{"question_id": "q1", "choice_id": "b"}]
            }
        )
    )

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_on_an_unknown_question_id(tmp_path: Path):
    fake_query, _ = _answering(
        _result(
            structured_output={
                "answers": [
                    {"question_id": "q1", "choice_id": "b"},
                    {"question_id": "q2", "choice_id": "a"},
                    {"question_id": "q9", "choice_id": "a"},
                ]
            }
        )
    )

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_on_an_unknown_choice_id(tmp_path: Path):
    fake_query, _ = _answering(
        _result(
            structured_output={
                "answers": [
                    {"question_id": "q1", "choice_id": "z"},
                    {"question_id": "q2", "choice_id": "a"},
                ]
            }
        )
    )

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_fails_when_a_question_is_answered_twice(tmp_path: Path):
    fake_query, _ = _answering(
        _result(
            structured_output={
                "answers": [
                    {"question_id": "q1", "choice_id": "b"},
                    {"question_id": "q1", "choice_id": "a"},
                    {"question_id": "q2", "choice_id": "a"},
                ]
            }
        )
    )

    with pytest.raises(KeyCheckFailed):
        _run(tmp_path, fake_query)


def test_key_check_rejects_an_api_key(tmp_path: Path):
    fake_query, _ = _answering(
        SystemMessage(subtype="init", data={"apiKeySource": "ANTHROPIC_API_KEY"}),
        _result(
            structured_output={
                "answers": [
                    {"question_id": "q1", "choice_id": "b"},
                    {"question_id": "q2", "choice_id": "a"},
                ]
            }
        ),
    )

    with pytest.raises(ApiKeyPresent):
        _run(tmp_path, fake_query)


def test_an_api_key_is_not_hidden_by_a_later_query_failure(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del prompt, options
        yield SystemMessage(
            subtype="init", data={"apiKeySource": "ANTHROPIC_API_KEY"}
        )
        raise RuntimeError("CLI down")

    with pytest.raises(ApiKeyPresent):
        _run(tmp_path, fake_query)
