"""Profile storage and the session-end pass: PR-05, PR-07, PR-08."""

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage, SystemMessage

from polaris.login import ApiKeyPresent
from polaris.models import Fact, FactChange, Turn
from polaris.profile import (
    ProfilePassFailed,
    ProfileUnreadable,
    active_facts,
    apply_changes,
    create_profile_tables,
    import_profile_json,
)
from polaris.profile_pass import (
    CHANGE_SCHEMA,
    ClaudeProfilePass,
    profile_pass_options,
    session_prompt,
)

NOW = "2026-10-16T10:00:00+00:00"
LATER = "2026-10-17T10:00:00+00:00"


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
    db.execute("CREATE TABLE turns (id TEXT PRIMARY KEY, session_id TEXT)")
    db.execute("CREATE TABLE artifacts (id TEXT PRIMARY KEY)")
    db.execute("INSERT INTO sessions (id) VALUES ('s1')")
    db.execute("INSERT INTO turns (id, session_id) VALUES ('t1', 's1'), ('t2', 's1')")
    create_profile_tables(db)
    yield db
    db.close()


def _apply(conn, *changes: FactChange, now: str = NOW):
    return apply_changes(
        conn, changes, session_id="s1", turn_ids={"t1", "t2"}, now=now
    )


def _texts(conn) -> tuple[str, ...]:
    return tuple(fact.text for fact in active_facts(conn))


def test_add_stores_a_new_fact_with_kind_basis_and_evidence(conn):
    _apply(
        conn,
        FactChange(
            "ADD",
            "Likes step-by-step walkthroughs",
            kind="taught",
            basis="stated",
            evidence=("t1",),
        ),
    )

    (fact,) = active_facts(conn)
    assert (fact.kind, fact.text, fact.basis) == (
        "taught",
        "Likes step-by-step walkthroughs",
        "stated",
    )
    assert fact.created_at == NOW
    evidence = conn.execute(
        "SELECT session_id, turn_id FROM fact_evidence WHERE fact_id = ?", (fact.id,)
    ).fetchall()
    assert [tuple(row) for row in evidence] == [("s1", "t1")]


def test_an_add_without_kind_is_unsorted_and_inferred(conn):
    _apply(conn, FactChange("ADD", "likes diagrams"))

    (fact,) = active_facts(conn)
    assert (fact.kind, fact.basis) == ("unsorted", "inferred")


def test_a_repeated_fact_is_not_stored_twice(conn):
    _apply(conn, FactChange("ADD", "I suck at math"))
    applied = _apply(conn, FactChange("ADD", "i suck at math!", kind="struggle"))

    assert _texts(conn) == ("I suck at math",)
    assert [item["action"] for item in applied.accepted] == ["IGNORE"]
    assert not applied.stored


def test_update_by_id_replaces_one_stored_fact_and_keeps_history(conn):
    _apply(
        conn,
        FactChange("ADD", "has written some code", evidence=("t1",)),
        FactChange("ADD", "likes diagrams", kind="taught"),
    )
    old = next(fact for fact in active_facts(conn) if fact.text == "has written some code")

    _apply(
        conn,
        FactChange(
            "UPDATE",
            "Comfortable with functions and loops in Python",
            id=old.id,
            kind="can_do",
            evidence=("t2",),
        ),
        now=LATER,
    )

    assert _texts(conn) == (
        "likes diagrams",
        "Comfortable with functions and loops in Python",
    )
    new = next(fact for fact in active_facts(conn) if fact.kind == "can_do")
    assert new.created_at == NOW
    assert new.updated_at == LATER
    retired = conn.execute(
        "SELECT retired_at, replaced_by FROM facts WHERE id = ?", (old.id,)
    ).fetchone()
    assert tuple(retired) == (LATER, new.id)
    turns = conn.execute(
        "SELECT turn_id FROM fact_evidence WHERE fact_id = ? ORDER BY turn_id",
        (new.id,),
    ).fetchall()
    assert [row["turn_id"] for row in turns] == ["t1", "t2"]


def test_an_update_that_names_no_stored_fact_is_refused(conn):
    _apply(conn, FactChange("ADD", "Struggles with math", kind="struggle"))

    applied = _apply(conn, FactChange("UPDATE", "Struggles with fractions", id="F9"))

    assert _texts(conn) == ("Struggles with math",)
    assert applied.accepted == ()
    assert applied.refused[0]["why"] == "names no stored fact"


def test_delete_by_id_removes_a_stored_fact(conn):
    _apply(
        conn,
        FactChange("ADD", "likes diagrams"),
        FactChange("ADD", "struggles with fractions"),
    )
    liked = active_facts(conn)[0]

    _apply(conn, FactChange("DELETE", id=liked.id))

    assert _texts(conn) == ("struggles with fractions",)


def test_a_delete_that_names_no_stored_fact_is_refused(conn):
    _apply(conn, FactChange("ADD", "likes diagrams"))

    applied = _apply(conn, FactChange("DELETE", "likes diagrams"))

    assert _texts(conn) == ("likes diagrams",)
    assert applied.refused[0]["why"] == "names no stored fact"


def test_ignore_leaves_the_profile_unchanged(conn):
    _apply(conn, FactChange("ADD", "I suck at math"))
    stored = active_facts(conn)[0]

    applied = _apply(conn, FactChange("IGNORE", id=stored.id))

    assert active_facts(conn) == (stored,)
    assert not applied.stored


def test_facts_are_read_goal_first_then_how_they_want_to_be_taught(conn):
    _apply(
        conn,
        FactChange("ADD", "Struggles with fractions", kind="struggle"),
        FactChange("ADD", "Likes drawings", kind="taught"),
        FactChange("ADD", "Passing the GCSE maths exam in June", kind="goal"),
    )

    assert [fact.kind for fact in active_facts(conn)] == ["goal", "taught", "struggle"]


def test_an_old_profile_file_is_imported_once(conn, tmp_path: Path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"facts": ["likes diagrams", "I suck at math"]}))

    import_profile_json(conn, path, NOW)
    import_profile_json(conn, path, NOW)

    assert _texts(conn) == ("likes diagrams", "I suck at math")
    assert {fact.kind for fact in active_facts(conn)} == {"unsorted"}
    assert not path.exists()
    assert (tmp_path / "profile.json.imported").exists()


def test_an_unreadable_profile_file_is_not_imported(conn, tmp_path: Path):
    path = tmp_path / "profile.json"
    path.write_text("{not json")

    with pytest.raises(ProfileUnreadable):
        import_profile_json(conn, path, NOW)
    assert path.exists()


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


def _fact(fact_id: str, text: str, kind: str = "struggle") -> Fact:
    return Fact(fact_id, kind, text, "stated", NOW, NOW)


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
    assert "by its id" in prompt
    assert "Never store" in prompt


def test_the_pass_sees_facts_and_turns_by_short_id():
    prompt = session_prompt(
        (_fact("uuid-1", "Struggles with math"),),
        (Turn("I suck at math", "Let's start small.", id="turn-1"),),
    )

    assert "- F1 [struggle, stated, updated 2026-10-16] Struggles with math" in prompt
    assert "T1 Learner: I suck at math" in prompt
    assert "uuid-1" not in prompt


def test_profile_pass_maps_short_ids_back_to_stored_ids(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del options
        assert "I suck at math" in prompt
        yield _result(
            structured_output={
                "changes": [
                    {"action": "IGNORE", "id": "F1", "reason": "repeat", "evidence": ["T1"]},
                    {"action": "UPDATE", "id": "F7", "text": "x", "reason": "made up"},
                ]
            }
        )

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)
    changes = asyncio.run(
        writer.run(
            turns=(Turn("I suck at math", "Let's start small.", id="turn-1"),),
            facts=(_fact("uuid-1", "Struggles with math"),),
        )
    )

    assert changes == (
        FactChange("IGNORE", id="uuid-1", evidence=("turn-1",), reason="repeat"),
        FactChange("UPDATE", "x", id="F7", reason="made up"),
    )


def test_profile_pass_reads_the_session_and_returns_changes(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del options
        assert "I like diagrams" in prompt
        assert "(no facts yet)" in prompt
        yield _result(
            structured_output={
                "changes": [
                    {
                        "action": "ADD",
                        "kind": "taught",
                        "text": "Likes diagrams",
                        "basis": "stated",
                        "evidence": ["T1"],
                        "reason": "Said so",
                    }
                ]
            }
        )

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)
    turns = (Turn("I like diagrams", "How do you like to learn?", id="turn-1"),)
    changes = asyncio.run(writer.run(turns=turns, facts=()))

    assert changes == (
        FactChange(
            "ADD",
            "Likes diagrams",
            kind="taught",
            basis="stated",
            evidence=("turn-1",),
            reason="Said so",
        ),
    )


def test_profile_pass_fails_loudly_when_the_query_fails(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del prompt, options
        if False:
            yield
        raise RuntimeError("CLI down")

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)

    with pytest.raises(ProfilePassFailed):
        asyncio.run(
            writer.run(
                turns=(Turn(learner_message="hello", reply="What should I know?"),),
                facts=(),
            )
        )


def test_profile_pass_fails_loudly_without_a_successful_result(tmp_path: Path):
    async def fake_query(*, prompt, options, **_kwargs):
        del prompt, options
        yield _result(subtype="error_max_turns", is_error=True)

    writer = ClaudeProfilePass(tmp_path, query_fn=fake_query)

    with pytest.raises(ProfilePassFailed):
        asyncio.run(
            writer.run(
                turns=(Turn(learner_message="hello", reply="What should I know?"),),
                facts=(),
            )
        )


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
                facts=(),
            )
        )
