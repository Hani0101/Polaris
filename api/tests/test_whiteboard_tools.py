"""draw_whiteboard, mark_whiteboard, and simplify_whiteboard are separate tools.

These tests never call the model. The schemas are checked with jsonschema,
which the SDK runs before a tool handler.
"""

import asyncio
import json
from pathlib import Path

import jsonschema

from polaris.chat import InvalidDrawing
from polaris.teaching import (
    DRAW_WHITEBOARD_SCHEMA,
    MARK_WHITEBOARD_SCHEMA,
    SIMPLIFY_WHITEBOARD_SCHEMA,
    ClaudeTeachingAgent,
)
from polaris.whiteboard import MARKED_DRAWING_VERSION, apply_marks, check_drawing
from test_layout import LAYOUTS, _laid_out
from test_whiteboard import _answer_drawing, _circle_mark, _mark_action, agent_drawing, valid_whiteboard


def _valid(schema: dict, args: dict) -> bool:
    try:
        jsonschema.validate(instance=args, schema=schema)
    except jsonschema.ValidationError:
        return False
    return True


def test_the_schemas_take_real_lists_and_json_text():
    drawing = agent_drawing(valid_whiteboard())
    as_text = {**drawing, "steps": json.dumps(drawing["steps"])}
    layout = _laid_out(LAYOUTS["flow"])

    assert _valid(DRAW_WHITEBOARD_SCHEMA, drawing)
    assert _valid(DRAW_WHITEBOARD_SCHEMA, as_text)
    assert _valid(DRAW_WHITEBOARD_SCHEMA, layout)
    assert _valid(DRAW_WHITEBOARD_SCHEMA, {**layout, "layout": json.dumps(layout["layout"])})
    # A drawing with mistakes still reaches the handler and its fix limit.
    assert _valid(DRAW_WHITEBOARD_SCHEMA, {"steps": [{"id": "s"}]})
    assert not _valid(DRAW_WHITEBOARD_SCHEMA, {"steps": 3})


def test_the_mark_schema_needs_the_whole_action():
    action = _mark_action()

    assert _valid(MARK_WHITEBOARD_SCHEMA, action)
    assert _valid(MARK_WHITEBOARD_SCHEMA, {**action, "marks": json.dumps(action["marks"])})
    assert not _valid(MARK_WHITEBOARD_SCHEMA, {**action, "marks": None})
    missing = dict(action)
    del missing["whiteboard_id"]
    assert not _valid(MARK_WHITEBOARD_SCHEMA, missing)
    bad_kind = {**action, "marks": [{**_circle_mark(), "mark": "star"}]}
    assert not _valid(MARK_WHITEBOARD_SCHEMA, bad_kind)


def test_the_simplify_schema_needs_the_original_id():
    drawing = agent_drawing(valid_whiteboard())

    assert not _valid(SIMPLIFY_WHITEBOARD_SCHEMA, drawing)
    assert _valid(SIMPLIFY_WHITEBOARD_SCHEMA, {**drawing, "simplifies": "wb-0"})


def _marking_agent(tmp_path: Path, saved: list[dict]) -> ClaudeTeachingAgent:
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None

    def mark(_session_id: str, action: dict) -> dict:
        result = apply_marks(stored, action)
        if result.whiteboard is None:
            raise InvalidDrawing(result.errors)
        payload = result.whiteboard.model_dump(mode="json")
        saved.append(payload)
        return payload

    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, mark_whiteboard=mark)
    return agent


def test_mark_whiteboard_sets_kind_and_author(tmp_path: Path):
    saved: list[dict] = []
    agent = _marking_agent(tmp_path, saved)
    bare = {
        key: value for key, value in _circle_mark().items() if key not in ("kind", "author")
    }

    payload = asyncio.run(
        agent.handle_mark_whiteboard("session-9", _mark_action([bare]))
    )

    assert payload.get("is_error") is not True, payload
    assert saved[0]["version"] == MARKED_DRAWING_VERSION
    mark = saved[0]["steps"][-1]["elements"][0]
    assert mark["kind"] == "mark"
    assert mark["author"] == "agent"


def test_mark_whiteboard_refuses_a_mark_on_an_agent_element(tmp_path: Path):
    saved: list[dict] = []
    agent = _marking_agent(tmp_path, saved)

    payload = asyncio.run(
        agent.handle_mark_whiteboard(
            "session-9", _mark_action([_circle_mark(target_element_id="nope")])
        )
    )

    assert saved == []
    assert payload["is_error"] is True
    assert "call mark_whiteboard again" in payload["content"][0]["text"]


def test_simplify_whiteboard_needs_simplifies_and_stores_a_redraw(tmp_path: Path):
    stored: list[dict] = []

    def store(_session_id: str, drawing: dict) -> dict:
        stored.append(drawing)
        return {"id": drawing["id"]}

    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)
    drawing = agent_drawing(valid_whiteboard())

    refused = asyncio.run(agent.handle_simplify_whiteboard("session-9", drawing))
    accepted = asyncio.run(
        agent.handle_simplify_whiteboard("session-9", {**drawing, "simplifies": "wb-0"})
    )

    assert refused["is_error"] is True
    assert "simplifies" in refused["content"][0]["text"]
    assert accepted.get("is_error") is not True, accepted
    assert stored[0]["simplifies"] == "wb-0"


def test_the_three_tools_share_one_fix_count(tmp_path: Path):
    saved: list[dict] = []
    agent = _marking_agent(tmp_path, saved)

    asyncio.run(agent.handle_draw_whiteboard("session-9", {"steps": "not json"}))
    asyncio.run(
        agent.handle_mark_whiteboard(
            "session-9", _mark_action([_circle_mark(target_element_id="nope")])
        )
    )

    assert agent.drawing_fix_count("session-9") == 2
