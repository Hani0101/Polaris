"""Profile storage and the session-end pass: PR-05, PR-07, PR-08."""

import asyncio
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage, SystemMessage

from polaris.login import ApiKeyPresent
from polaris.models import FactChange, Profile, Turn
from polaris.profile import apply_changes, load_profile, save_profile
from polaris.profile_pass import (
    CHANGE_SCHEMA,
    ClaudeProfilePass,
    profile_pass_options,
)


def test_add_stores_a_new_fact():
    profile = apply_changes(
        Profile(()),
        (FactChange("ADD", "likes step-by-step walkthroughs"),),
    )

    assert profile.facts == ("likes step-by-step walkthroughs",)


def test_a_repeated_fact_is_not_stored_twice():
    profile = apply_changes(
        Profile(("I suck at math",)),
        (FactChange("ADD", "I suck at math"),),
    )

    assert profile.facts == ("I suck at math",)


def test_update_replaces_one_stored_fact():
    profile = apply_changes(
        Profile(("has written some code", "likes diagrams")),
        (
            FactChange(
                "UPDATE",
                "comfortable with functions and loops in Python",
                replaces="has written some code",
            ),
        ),
    )

    assert profile.facts == (
        "comfortable with functions and loops in Python",
        "likes diagrams",
    )


def test_delete_removes_a_stored_fact():
    profile = apply_changes(
        Profile(("likes diagrams", "struggles with fractions")),
        (FactChange("DELETE", "likes diagrams"),),
    )

    assert profile.facts == ("struggles with fractions",)


def test_ignore_leaves_the_profile_unchanged():
    profile = apply_changes(
        Profile(("I suck at math",)),
        (FactChange("IGNORE", "I suck at math"),),
    )

    assert profile.facts == ("I suck at math",)


def test_save_then_load_returns_the_same_facts(tmp_path: Path):
    path = tmp_path / "profile.json"
    save_profile(path, Profile(("likes diagrams", "I suck at math")))

    assert load_profile(path).facts == ("likes diagrams", "I suck at math")


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


def test_profile_pass_options_match_the_sdk_docs(tmp_path: Path):
    options = profile_pass_options(cwd=tmp_path)

    assert options.model == "haiku"
    assert options.tools == []
    assert options.skills == []
    assert options.setting_sources == []
    assert options.verbatim_prompts is True
    assert options.permission_mode == "dontAsk"
    assert options.max_turns == 3
    assert options.cwd == tmp_path
    assert options.output_format == {
        "type": "json_schema",
        "schema": CHANGE_SCHEMA,
    }
    prompt = options.system_prompt
    assert isinstance(prompt, str)
    assert "Do not teach" in prompt
    assert "ADD, UPDATE, DELETE, or IGNORE" in prompt
    assert "A fact already stored is not added again" in prompt


def test_profile_pass_reads_the_session_and_returns_changes(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del options
        assert "I like diagrams" in prompt
        assert "(no facts yet)" in prompt
        yield _result(
            structured_output={
                "changes": [{"action": "ADD", "fact": "likes diagrams"}]
            }
        )

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)
    turns = (
        Turn(
            learner_message="I like diagrams",
            reply="How do you like to learn?",
        ),
    )
    changes = asyncio.run(writer.run(turns=turns, profile=Profile(())))

    assert changes == (FactChange("ADD", "likes diagrams"),)


def test_profile_pass_returns_no_changes_when_the_query_fails(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del prompt, options
        if False:
            yield
        raise RuntimeError("CLI down")

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)
    changes = asyncio.run(
        writer.run(
            turns=(Turn(learner_message="hello", reply="What should I know?"),),
            profile=Profile(()),
        )
    )

    assert changes == ()


def test_profile_pass_rejects_an_api_key(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del prompt, options
        yield SystemMessage(
            subtype="init", data={"apiKeySource": "ANTHROPIC_API_KEY"}
        )
        yield _result(structured_output={"changes": []})

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)

    with pytest.raises(ApiKeyPresent):
        asyncio.run(
            writer.run(
                turns=(Turn(learner_message="hello", reply="What should I know?"),),
                profile=Profile(()),
            )
        )
