"""The learner's own boards, pinned above the chat (WB-18, WB-19, WB-20, WB-21).

These tests never call the model. A fake agent adds its parts through the same
submit path the extend_whiteboard tool uses.
"""

from polaris.extend import apply_extension
from polaris.models import Profile
from polaris.teaching import submit_extension, turn_prompt
from polaris.whiteboard import (
    BLANK_WHITEBOARD_DESCRIPTION,
    CURRENT_DRAWING_VERSION,
    blank_whiteboard,
    check_drawing,
    check_learner_drawing,
)
from test_chat import make_client, parse_sse, post_turn
from test_quiz import FILLED_PROFILE
from test_whiteboard import _element, valid_whiteboard

STEP = "hint"


def _learner_box(element_id: str = "learner-box", x: float = 0) -> dict[str, object]:
    return _element(
        element_id,
        "rectangle",
        author="learner",
        position={"x": x, "y": 0},
        size={"width": 300, "height": 200},
    )


def _agent_box(element_id: str = "agent-box") -> dict[str, object]:
    box = _element(
        element_id,
        "rectangle",
        position={"x": 40, "y": 40},
        size={"width": 200, "height": 100},
    )
    box.pop("author")
    return box


def _extension(whiteboard_id: str, step_id: str = STEP, **extra) -> dict[str, object]:
    return {
        "whiteboard_id": whiteboard_id,
        "step_id": step_id,
        "reply_part": f"[[step:{step_id}]]",
        "elements": [_agent_box(f"{step_id}-box")],
        **extra,
    }


def _with_learner_box(board):
    drawing = board.model_dump(mode="json")
    drawing["steps"][0]["elements"].append(_learner_box())
    checked = check_drawing(drawing)
    assert checked.whiteboard is not None, checked.errors
    return checked.whiteboard


class ExtendingStub:
    """Adds one step to the pinned board, and can fail after adding it."""

    def __init__(self, fail: bool = False) -> None:
        self.chat = None
        self.fail = fail
        self.pinned = []
        self.prompts: list[str] = []

    async def reply(self, *, session_id: str, profile, learner_message: str, whiteboards=(), **extra):
        pinned = extra.get("pinned")
        self.pinned.append(pinned)
        self.prompts.append(
            turn_prompt(profile, learner_message, whiteboards=whiteboards, pinned=pinned)
        )
        yield "Look at this. [[step:hint]]"
        if pinned is not None:
            assert self.chat is not None
            result = submit_extension(
                session_id,
                _extension(pinned.id),
                failures=0,
                store=self.chat.extend_whiteboard,
                preview=self.chat.preview_extension,
            ).tool_result
            assert result.get("is_error") is not True, result
        if self.fail:
            raise RuntimeError("The reply failed.")
        yield " Your box is right."

    async def close_session(self, session_id: str) -> None:
        del session_id


def _session_with_board(make_client, agent=None):
    stub = agent or ExtendingStub()
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    created = client.post(f"/api/sessions/{session['id']}/whiteboards")
    assert created.status_code == 201, created.text
    return client, stub, session, created.json()


def _put(client, session_id: str, drawing: dict):
    body = {key: value for key, value in drawing.items() if key != "kind"}
    return client.put(f"/api/sessions/{session_id}/whiteboards/{drawing['id']}", json=body)


def test_a_blank_board_is_version_7_with_one_empty_step():
    board = blank_whiteboard("wb-1", "s-1")

    assert board.version == CURRENT_DRAWING_VERSION
    assert board.description == BLANK_WHITEBOARD_DESCRIPTION
    assert [step.elements for step in board.steps] == [[]]
    assert check_drawing(board.model_dump(mode="json")).errors == []


def test_the_learner_creates_several_boards(make_client):  # WB-18
    client, _stub, session, first = _session_with_board(make_client)
    second = client.post(f"/api/sessions/{session['id']}/whiteboards").json()

    listed = client.get(f"/api/sessions/{session['id']}/whiteboards").json()["whiteboards"]

    assert [board["id"] for board in listed] == [first["id"], second["id"]]
    for board in listed:
        assert board["description"] == BLANK_WHITEBOARD_DESCRIPTION
        reopened = client.get(f"/api/sessions/{session['id']}/whiteboards/{board['id']}")
        assert reopened.status_code == 200


def test_a_learner_board_survives_a_failed_turn(make_client):  # WB-18, WB-04
    client, _stub, session, board = _session_with_board(make_client, ExtendingStub(fail=True))

    response = client.post(f"/api/sessions/{session['id']}/turns", json={"message": "hi"})
    events, _rest = parse_sse(response.text)

    assert any("error" in event for event in events)
    reopened = client.get(f"/api/sessions/{session['id']}/whiteboards/{board['id']}")
    assert reopened.status_code == 200
    assert [step["id"] for step in reopened.json()["steps"]] == ["learner"]


def test_a_message_is_about_the_pinned_board(make_client):  # WB-19, WB-03
    client, stub, session, board = _session_with_board(make_client)
    board["steps"][0]["elements"].append(_learner_box())
    assert _put(client, session["id"], board).status_code == 200

    post_turn(client, session["id"], "Is my box right?", pinned_whiteboard_id=board["id"])

    assert stub.pinned[-1] is not None and stub.pinned[-1].id == board["id"]
    prompt = stub.prompts[-1]
    assert f"Whiteboard {board['id']} is pinned above the conversation" in prompt
    assert "learner-box" in prompt


def test_a_turn_without_a_pinned_board_is_not_about_one(make_client):  # WB-19
    client, stub, session, _board = _session_with_board(make_client)

    post_turn(client, session["id"], "Hello")

    assert stub.pinned[-1] is None
    assert "is pinned above the conversation" not in stub.prompts[-1]


def test_the_agent_draws_next_to_the_learners_work(make_client):  # WB-20, WB-06
    client, _stub, session, board = _session_with_board(make_client)
    board["steps"][0]["elements"].append(_learner_box())
    learner_before = _put(client, session["id"], board).json()["steps"][0]

    events = post_turn(client, session["id"], "Help", pinned_whiteboard_id=board["id"])

    shown = [event["artifact"] for event in events if "artifact" in event]
    assert shown and shown[-1]["id"] == board["id"]
    stored = client.get(f"/api/sessions/{session['id']}/whiteboards/{board['id']}").json()
    assert stored["steps"][0] == learner_before
    added = stored["steps"][-1]
    assert added["extension"] is True
    assert added["reply_part"] == "[[step:hint]]"
    assert [element["author"] for element in added["elements"]] == ["agent"]
    # Placed beside the learner's 300-wide box, not on it.
    assert added["elements"][0]["position"]["x"] >= 300


def test_a_failed_turn_takes_back_only_the_added_step(make_client):  # WB-20
    client, _stub, session, board = _session_with_board(make_client, ExtendingStub(fail=True))
    board["steps"][0]["elements"].append(_learner_box())
    _put(client, session["id"], board)

    client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": "Help", "pinned_whiteboard_id": board["id"]},
    )

    stored = client.get(f"/api/sessions/{session['id']}/whiteboards/{board['id']}").json()
    assert [step["id"] for step in stored["steps"]] == ["learner"]
    assert [element["id"] for element in stored["steps"][0]["elements"]] == ["learner-box"]


def test_a_stale_save_keeps_the_agents_parts(make_client):  # WB-21
    client, _stub, session, board = _session_with_board(make_client)
    loaded = client.get(f"/api/sessions/{session['id']}/whiteboards/{board['id']}").json()
    post_turn(client, session["id"], "Help", pinned_whiteboard_id=board["id"])

    # The browser still has the copy it loaded before the agent's step.
    loaded["steps"][0]["elements"].append(_learner_box())
    saved = _put(client, session["id"], loaded)

    assert saved.status_code == 200, saved.text
    steps = saved.json()["steps"]
    assert [step["id"] for step in steps] == ["learner", STEP]
    assert [element["id"] for element in steps[0]["elements"]] == ["learner-box"]
    assert [element["id"] for element in steps[1]["elements"]] == ["hint-box"]


def test_a_save_replaces_the_learners_parts_only():  # WB-21
    stored = apply_extension(
        _with_learner_box(blank_whiteboard("wb-1", "s-1")), _agent_extension("wb-1")
    ).whiteboard
    assert stored is not None
    copy = stored.model_dump(mode="json")
    copy["steps"][0]["elements"] = [_learner_box("learner-other", x=-400)]
    copy["steps"].pop()

    merged = check_learner_drawing(stored, copy)

    assert merged.errors == []
    assert merged.whiteboard is not None
    ids = [[element.id for element in step.elements] for step in merged.whiteboard.steps]
    assert ids == [["learner-other"], ["hint-box"]]


def test_a_save_cannot_put_learner_parts_in_the_agents_step():
    stored = apply_extension(
        _with_learner_box(blank_whiteboard("wb-1", "s-1")), _agent_extension("wb-1")
    ).whiteboard
    assert stored is not None
    copy = stored.model_dump(mode="json")
    copy["steps"][-1]["elements"].append(_learner_box("learner-late", x=900))

    result = check_learner_drawing(stored, copy)

    assert result.whiteboard is None
    assert any("agent's own parts" in error for error in result.errors)


def test_a_save_cannot_add_a_step():
    stored = _with_learner_box(blank_whiteboard("wb-1", "s-1"))
    copy = stored.model_dump(mode="json")
    copy["steps"].append({"id": "mine", "reply_part": "[[step:mine]]", "elements": []})

    result = check_learner_drawing(stored, copy)

    assert result.whiteboard is None
    assert "steps cannot be added or reordered" in result.errors


def _agent_extension(whiteboard_id: str, step_id: str = STEP) -> dict[str, object]:
    action = _extension(whiteboard_id, step_id)
    action["elements"] = [{**element, "author": "agent"} for element in action["elements"]]
    return action


def test_added_parts_are_checked_on_their_own():  # WB-20
    stored = _with_learner_box(blank_whiteboard("wb-1", "s-1"))
    crowded = _agent_extension("wb-1")
    crowded["elements"].append(
        {**crowded["elements"][0], "id": "hint-twin", "position": {"x": 140, "y": 90}}
    )

    checked = apply_extension(stored, crowded)

    assert checked.whiteboard is not None
    assert {problem.kind for problem in checked.problems} == {"overlap"}
    assert all("learner-box" not in problem.element_ids for problem in checked.problems)


def test_an_added_arrow_attaches_only_to_the_agents_own_parts():  # WB-20
    stored = _with_learner_box(blank_whiteboard("wb-1", "s-1"))
    action = _agent_extension("wb-1")
    action["elements"].append(
        {
            **_element("hint-arrow", "arrow"),
            "start": {"x": 240, "y": 90},
            "end": {"x": 300, "y": 90},
            "end_element_id": "learner-box",
        }
    )

    checked = apply_extension(stored, action)

    assert checked.whiteboard is None
    assert any("learner-box" in error for error in checked.errors)


def test_parts_cannot_be_added_to_an_older_board():
    older = check_drawing(valid_whiteboard()).whiteboard
    assert older is not None and older.version != CURRENT_DRAWING_VERSION

    checked = apply_extension(older, _agent_extension(older.id))

    assert checked.whiteboard is None
    assert any("older format" in error for error in checked.errors)


def test_the_pinned_board_is_described_in_full():  # WB-19
    first = _with_learner_box(blank_whiteboard("wb-1", "s-1"))
    latest = blank_whiteboard("wb-2", "s-1")

    prompt = turn_prompt(
        Profile(facts=("Learns by drawing.",)),
        "Is this right?",
        whiteboards=[first, latest],
        pinned=first,
    )

    assert "learner-box" in prompt
    assert "Whiteboard wb-1 is pinned above the conversation" in prompt
