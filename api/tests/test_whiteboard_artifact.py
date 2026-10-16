"""A whiteboard is an artifact of the session that created it (WB-04, CH-04).

These tests never call the model. A fake agent stores a drawing through the
same check the teaching tool uses, and the chat API is what the learner hits.
"""

import copy

from polaris.models import Profile
from polaris.teaching import submit_whiteboard, turn_prompt
from polaris.whiteboard import check_drawing, describe_pointed
from test_chat import make_client, parse_sse, post_turn
from test_quiz import FILLED_PROFILE
from test_whiteboard import _element, valid_whiteboard

REPLY = "A fraction is one part of a whole."
LEARNER = "Explain fractions with a drawing."
FOLLOW_UP = "And what about a third?"


class OneDrawingStub:
    """Stores one whiteboard on the first reply. Later replies are text only."""

    def __init__(self, drawing: dict) -> None:
        self.drawing = drawing
        self.chat = None
        self._drawn = False

    async def reply(
        self,
        *,
        session_id: str,
        profile,
        learner_message: str,
        prior_turns,
        sdk_session_id: str | None,
        whiteboards=(),
        pointing=None,
        simplify=None,
    ):
        del learner_message, prior_turns, sdk_session_id, pointing, simplify
        self.whiteboards = whiteboards
        if not profile.facts:
            yield (
                "What should I know before I teach? "
                "How do you want to be taught, what can you already do, "
                "and where do you struggle?"
            )
            return
        yield REPLY
        if self._drawn:
            return
        self._drawn = True
        assert self.chat is not None
        submit_whiteboard(
            session_id,
            self.drawing,
            failures=0,
            store=self.chat.create_whiteboard,
        )

    async def close_session(self, session_id: str) -> None:
        del session_id


def _without_kind(artifact: dict) -> dict:
    drawing = dict(artifact)
    drawing.pop("kind", None)
    return drawing


def _create(make_client):
    stub = OneDrawingStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    post_turn(client, session["id"], FOLLOW_UP)
    saved = client.get(f"/api/sessions/{session['id']}").json()
    return client, session, saved


def test_creating_a_whiteboard_stores_it_with_its_session_and_turn(make_client):
    """WB-04: creating a whiteboard stores it as an artifact of that session."""

    client, session, saved = _create(make_client)

    first = saved["turns"][0]
    assert first["learner_message"] == LEARNER
    assert first["reply"] == REPLY
    assert len(first["artifacts"]) == 1
    whiteboard = first["artifacts"][0]
    assert whiteboard["kind"] == "whiteboard"
    assert whiteboard["id"] == "wb-1"
    assert whiteboard["session_id"] == session["id"]
    assert saved["turns"][1]["learner_message"] == FOLLOW_UP
    assert saved["turns"][1]["artifacts"] == []

    listed = client.get(f"/api/sessions/{session['id']}/whiteboards")
    assert listed.status_code == 200
    assert listed.json() == {"whiteboards": [whiteboard]}


def test_reopening_the_session_shows_the_same_whiteboard(make_client):
    """CH-04: opening an earlier session again still shows its turns."""

    client, session, saved = _create(make_client)
    whiteboard = saved["turns"][0]["artifacts"][0]
    other = client.post("/api/sessions").json()
    assert other["id"] != session["id"]

    reopened = client.post(f"/api/sessions/{session['id']}/open")

    assert reopened.status_code == 200
    body = reopened.json()
    assert [turn["learner_message"] for turn in body["turns"]] == [LEARNER, FOLLOW_UP]
    assert body["turns"][0]["reply"] == REPLY
    assert body["turns"][0]["artifacts"] == [whiteboard]
    assert body["turns"][1]["artifacts"] == []


def test_loading_a_whiteboard_from_another_session_is_refused(make_client):
    client, session, saved = _create(make_client)
    whiteboard_id = saved["turns"][0]["artifacts"][0]["id"]
    other = client.post("/api/sessions").json()

    refused = client.get(f"/api/sessions/{other['id']}/whiteboards/{whiteboard_id}")
    assert refused.status_code == 404

    allowed = client.get(f"/api/sessions/{session['id']}/whiteboards/{whiteboard_id}")
    assert allowed.status_code == 200
    assert allowed.json()["id"] == whiteboard_id
    assert allowed.json()["session_id"] == session["id"]


def test_a_loaded_whiteboard_passes_the_drawing_check(make_client):
    """WB-05: drawing data loaded from the session still passes the check."""

    client, session, saved = _create(make_client)
    whiteboard_id = saved["turns"][0]["artifacts"][0]["id"]

    loaded = client.get(f"/api/sessions/{session['id']}/whiteboards/{whiteboard_id}")

    assert loaded.status_code == 200
    drawing = _without_kind(loaded.json())
    result = check_drawing(drawing)
    assert result.errors == []
    assert result.whiteboard is not None
    assert result.whiteboard.model_dump(mode="json") == drawing


def _open_drawing(make_client):
    stub = OneDrawingStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    saved = client.get(f"/api/sessions/{session['id']}").json()
    artifact = saved["turns"][0]["artifacts"][0]
    return client, stub, session, _without_kind(artifact)


def _learner_box() -> dict[str, object]:
    return _element(
        "learner-box",
        "rectangle",
        author="learner",
        position={"x": 120, "y": 40},
    )


def _put_drawing(client, session_id: str, drawing: dict):
    return client.put(
        f"/api/sessions/{session_id}/whiteboards/{drawing['id']}",
        json=drawing,
    )


def test_a_learner_element_is_stored_with_author_learner(make_client):
    client, _stub, session, drawing = _open_drawing(make_client)
    drawing["steps"][1]["elements"].append(_learner_box())

    response = _put_drawing(client, session["id"], drawing)

    assert response.status_code == 200, response.text
    added = response.json()["steps"][1]["elements"][-1]
    assert added["id"] == "learner-box"
    assert added["author"] == "learner"
    loaded = client.get(
        f"/api/sessions/{session['id']}/whiteboards/{drawing['id']}"
    )
    assert loaded.json()["steps"][1]["elements"][-1]["author"] == "learner"


def test_a_learner_cannot_change_an_agent_element(make_client):
    client, _stub, session, drawing = _open_drawing(make_client)
    original = copy.deepcopy(drawing["steps"][0]["elements"][0])
    drawing["steps"][0]["elements"][0]["position"] = {"x": 400, "y": 400}

    response = _put_drawing(client, session["id"], drawing)

    assert response.status_code == 422
    assert "rect-1" in response.json()["detail"]
    loaded = client.get(
        f"/api/sessions/{session['id']}/whiteboards/{drawing['id']}"
    )
    assert loaded.json()["steps"][0]["elements"][0]["position"] == original["position"]


def test_bad_learner_data_is_refused(make_client):
    client, _stub, session, drawing = _open_drawing(make_client)
    drawing["comments"] = [
        {"id": "comment-1", "author": "learner", "text": "why"}
    ]

    response = _put_drawing(client, session["id"], drawing)

    assert response.status_code == 422
    assert "position or an element id" in response.json()["detail"]
    loaded = client.get(
        f"/api/sessions/{session['id']}/whiteboards/{drawing['id']}"
    )
    assert loaded.json().get("comments", []) == []


def test_a_learner_drawing_and_comment_survive_into_the_next_turn(make_client):
    """WB-02, WB-03: the drawing and comment stay, and the next turn can read them."""

    client, stub, session, drawing = _open_drawing(make_client)
    drawing["steps"][1]["elements"].append(_learner_box())
    drawing["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "the left box is the whole",
            "element_id": "rect-1",
        }
    ]

    saved = _put_drawing(client, session["id"], drawing)
    assert saved.status_code == 200, saved.text

    opened = client.post(f"/api/sessions/{session['id']}/open").json()
    artifact = opened["turns"][0]["artifacts"][0]
    elements = [
        element
        for step in artifact["steps"]
        for element in step["elements"]
    ]
    box = next(element for element in elements if element["id"] == "learner-box")
    assert box["author"] == "learner"
    assert artifact["comments"][0]["text"] == "the left box is the whole"
    assert artifact["comments"][0]["element_id"] == "rect-1"

    post_turn(client, session["id"], "What did I mark?")
    prompt = turn_prompt(
        Profile(("wants short explanations",)),
        "What did I mark?",
        whiteboards=stub.whiteboards,
    )
    assert "rectangle learner-box by learner at (120, 40)" in prompt
    assert (
        'comment comment-1 by learner about rect-1: "the left box is the whole"'
        in prompt
    )


class PointingStub(OneDrawingStub):
    """Records the parts the learner pointed at, and replies about those parts."""

    def __init__(self, drawing: dict) -> None:
        super().__init__(drawing)
        self.pointing = None

    async def reply(
        self,
        *,
        session_id: str,
        profile,
        learner_message: str,
        prior_turns,
        sdk_session_id: str | None,
        whiteboards=(),
        pointing=None,
        simplify=None,
    ):
        if not self._drawn:
            async for chunk in super().reply(
                session_id=session_id,
                profile=profile,
                learner_message=learner_message,
                prior_turns=prior_turns,
                sdk_session_id=sdk_session_id,
                whiteboards=whiteboards,
                pointing=pointing,
                simplify=simplify,
            ):
                yield chunk
            return
        self.pointing = pointing
        self.whiteboards = whiteboards
        if pointing is None:
            yield "no pointing"
            return
        board = next(item for item in whiteboards if item.id == pointing.whiteboard_id)
        yield describe_pointed(board, pointing.element_ids)


def _point(client, session_id: str, message: str, whiteboard_id: str, element_ids: list[str]):
    return client.post(
        f"/api/sessions/{session_id}/turns",
        json={
            "message": message,
            "pointing": {
                "whiteboard_id": whiteboard_id,
                "element_ids": element_ids,
            },
        },
    )


def test_selected_ids_reach_the_backend_as_polaris_ids(make_client):
    stub = PointingStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    response = _point(
        client,
        session["id"],
        "What are these parts?",
        "wb-1",
        ["rect-1", "text-1"],
    )

    assert response.status_code == 200, response.text
    assert stub.pointing is not None
    assert stub.pointing.whiteboard_id == "wb-1"
    assert stub.pointing.element_ids == ("rect-1", "text-1")
    assert "shape:" not in stub.pointing.element_ids
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert saved["turns"][1]["pointing"] == {
        "whiteboard_id": "wb-1",
        "element_ids": ["rect-1", "text-1"],
    }
    assert "pointing" not in saved["turns"][0]


def test_the_learner_points_and_asks(make_client):
    """WB-08: selecting one part and asking makes the reply about that part."""

    stub = PointingStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    response = _point(client, session["id"], "What is this part?", "wb-1", ["rect-1"])

    assert response.status_code == 200, response.text
    events, rest = parse_sse(response.text)
    assert rest == ""
    reply = "".join(event["text"] for event in events if "text" in event)
    assert "rectangle rect-1 by agent at (10, 20)" in reply
    assert "ellipse-1" not in reply
    assert "text-1" not in reply


def test_an_unknown_element_id_is_refused(make_client):
    stub = PointingStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    response = _point(
        client,
        session["id"],
        "What is this part?",
        "wb-1",
        ["shape:rect-1"],
    )

    assert response.status_code == 422
    assert "shape:rect-1" in response.json()["detail"]
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert len(saved["turns"]) == 1
    assert stub.pointing is None


def test_a_whiteboard_id_from_another_session_is_refused(make_client):
    stub = PointingStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    other = client.post("/api/sessions").json()

    response = _point(client, other["id"], "What is this part?", "wb-1", ["rect-1"])

    assert response.status_code == 404
    saved = client.get(f"/api/sessions/{other['id']}").json()
    assert saved["turns"] == []
