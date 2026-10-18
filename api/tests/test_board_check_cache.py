"""A stored whiteboard is checked once per stored text, not on every read (WB-05).

These tests never call the model. They count how often the drawing check runs
while a turn's reads load the same board again.
"""

import json
import sqlite3

import pytest

import polaris.chat as chat_module
from test_chat import make_client  # noqa: F401
from test_whiteboard_artifact import _create


@pytest.fixture
def counted_checks(monkeypatch):
    chat_module._checked_board.cache_clear()
    calls: list[object] = []
    real = chat_module.check_drawing

    def counting(data: object):
        calls.append(data)
        return real(data)

    monkeypatch.setattr(chat_module, "check_drawing", counting)
    yield calls
    chat_module._checked_board.cache_clear()


def _reads(client, chat, session_id: str):
    """What a reply reads: the session's turns, the board list, and the agent's boards."""

    saved = client.get(f"/api/sessions/{session_id}").json()
    listed = client.get(f"/api/sessions/{session_id}/whiteboards").json()["whiteboards"]
    boards = chat.whiteboards_for_reply(session_id)
    return saved, listed, boards


def test_a_second_read_of_the_same_board_does_not_check_it_again(
    make_client, counted_checks  # noqa: F811
):
    client, session, _saved = _create(make_client)
    chat = client.app.state.chat
    counted_checks.clear()
    chat_module._checked_board.cache_clear()

    saved, listed, boards = _reads(client, chat, session["id"])

    assert len(counted_checks) == 1
    assert saved["turns"][0]["artifacts"] == listed
    assert [board.id for board in boards] == ["wb-1"]

    again = _reads(client, chat, session["id"])

    assert len(counted_checks) == 1
    assert again[0] == saved and again[1] == listed
    assert again[2] == boards


def test_a_board_from_the_cache_is_a_copy_each_time(make_client, counted_checks):  # noqa: F811
    client, session, _saved = _create(make_client)
    chat = client.app.state.chat

    first = chat.whiteboards_for_reply(session["id"])[0]
    first.steps.clear()
    second = chat.whiteboards_for_reply(session["id"])[0]

    assert second.steps
    assert second is not first


def test_a_changed_board_is_checked_anew(make_client, counted_checks):  # noqa: F811
    client, session, _saved = _create(make_client)
    chat = client.app.state.chat
    _reads(client, chat, session["id"])
    before = len(counted_checks)

    with sqlite3.connect(chat.db_path) as conn:
        raw = conn.execute("SELECT drawing_json FROM whiteboards WHERE id = 'wb-1'").fetchone()[0]
        changed = json.loads(raw)
        changed["description"] = "The same drawing, described again."
        conn.execute(
            "UPDATE whiteboards SET drawing_json = ? WHERE id = 'wb-1'",
            (json.dumps(changed),),
        )
    conn.close()

    saved, listed, boards = _reads(client, chat, session["id"])

    assert len(counted_checks) == before + 1
    assert saved["turns"][0]["artifacts"][0]["description"] == changed["description"]
    assert listed[0]["description"] == changed["description"]
    assert boards[0].description == changed["description"]

    with sqlite3.connect(chat.db_path) as conn:
        changed["version"] = 1
        conn.execute(
            "UPDATE whiteboards SET drawing_json = ? WHERE id = 'wb-1'",
            (json.dumps(changed),),
        )
    conn.close()

    saved, listed, boards = _reads(client, chat, session["id"])

    assert len(counted_checks) == before + 2
    assert saved["turns"][0]["artifacts"] == []
    assert listed == []
    assert boards == []
