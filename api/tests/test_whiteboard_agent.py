"""The agent draws a whiteboard during a turn (WB-01, CH-02, WB-05).

These tests never call the model. A fake agent records tool results and the
chat API is what the browser receives.
"""

import asyncio
import copy
import json
from pathlib import Path

from polaris.chat import InvalidDrawing
from polaris.teaching import ClaudeTeachingAgent, submit_marks, submit_whiteboard
from polaris.whiteboard import MARKED_DRAWING_VERSION, WHITEBOARD_TOOL_LIMITS, apply_marks, check_drawing
from test_chat import make_client, parse_sse, post_turn, reply_text
from test_quiz import FILLED_PROFILE
from test_whiteboard import (
    _answer_drawing,
    _circle_mark,
    _element,
    _formula_drawing,
    _graph_drawing,
    _mark_action,
    valid_whiteboard,
)

REPLY = "A fraction is one part of a whole."
LEARNER = "Explain fractions with a drawing."


class DrawingStub:
    """Calls the whiteboard tool during a reply. Does not call the model."""

    def __init__(self, drawings: list[dict]) -> None:
        self.drawings = drawings
        self.chat = None
        self.tool_results: list[dict] = []
        self.failures = 0
        self.closed: list[str] = []

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
        **_extra,
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
        if not profile.facts:
            yield (
                "What should I know before I teach? "
                "How do you want to be taught, what can you already do, "
                "and where do you struggle?"
            )
            return
        yield REPLY
        assert self.chat is not None
        for drawing in self.drawings:
            submission = submit_whiteboard(
                session_id,
                drawing,
                failures=self.failures,
                store=self.chat.create_whiteboard,
            )
            self.failures = submission.failures
            self.tool_results.append(submission.tool_result)

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


def _bad_drawing() -> dict:
    drawing = copy.deepcopy(valid_whiteboard())
    drawing["steps"][0]["elements"][0]["kind"] = "triangle"
    return drawing


def _run(make_client, drawings: list[dict]):
    stub = DrawingStub(drawings)
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    events = post_turn(client, session["id"], LEARNER)
    saved = client.get(f"/api/sessions/{session['id']}").json()
    return stub, session, events, saved


def _whiteboards(session: dict) -> list[dict]:
    return [
        artifact
        for turn in session["turns"]
        for artifact in turn["artifacts"]
        if artifact["kind"] == "whiteboard"
    ]


def _streamed(events: list[dict]) -> list[dict]:
    return [event["artifact"] for event in events if "artifact" in event]


def test_a_valid_drawing_reaches_the_turn(make_client):
    _stub, session, events, saved = _run(make_client, [valid_whiteboard()])

    streamed = _streamed(events)
    assert len(streamed) == 1
    assert streamed[0]["kind"] == "whiteboard"
    assert streamed[0]["id"] == "wb-1"
    assert streamed[0]["session_id"] == session["id"]
    assert saved["turns"][0]["artifacts"] == streamed
    text = next(
        element["text"]
        for step in streamed[0]["steps"]
        for element in step["elements"]
        if element["kind"] == "text"
    )
    assert text == "half"


def test_an_invalid_drawing_is_refused(make_client):
    stub, _session, events, saved = _run(make_client, [_bad_drawing()])

    assert _streamed(events) == []
    assert saved["turns"][0]["artifacts"] == []
    assert stub.tool_results[0]["is_error"] is True
    message = stub.tool_results[0]["content"][0]["text"]
    assert "unknown element kind" in message
    assert "triangle" in message
    assert "Fix the drawing and call draw_whiteboard again." in message


def test_a_corrected_drawing_is_shown(make_client):
    corrected = valid_whiteboard()
    corrected["id"] = "wb-fixed"
    stub, session, events, saved = _run(make_client, [_bad_drawing(), corrected])

    streamed = _streamed(events)
    assert len(streamed) == 1
    assert streamed[0]["id"] == "wb-fixed"
    assert streamed[0]["session_id"] == session["id"]
    assert saved["turns"][0]["artifacts"] == streamed
    assert stub.tool_results[0]["is_error"] is True
    assert stub.tool_results[1].get("is_error") is not True


def test_drawing_fix_attempts_stop_at_the_limit(make_client):
    limit = WHITEBOARD_TOOL_LIMITS.max_fix_attempts
    refused = _bad_drawing()
    corrected = valid_whiteboard()
    corrected["id"] = "wb-too-late"
    drawings = [copy.deepcopy(refused) for _ in range(limit + 1)]
    drawings.append(corrected)
    stub, _session, events, saved = _run(make_client, drawings)

    assert _streamed(events) == []
    assert _whiteboards(saved) == []
    assert len(stub.tool_results) == limit + 2
    for result in stub.tool_results[:limit]:
        text = result["content"][0]["text"]
        assert result["is_error"] is True
        assert "unknown element kind" in text
        assert "Fix the drawing and call draw_whiteboard again." in text
    for result in stub.tool_results[limit:]:
        text = result["content"][0]["text"]
        assert result["is_error"] is True
        assert "was not shown" in text
        assert f"The drawing fix limit for this turn is {limit}." in text


def test_the_agent_draws(make_client):
    """Scenario: the agent draws [WB-01]."""

    _stub, _session, _events, saved = _run(make_client, [valid_whiteboard()])

    shown = _whiteboards(saved)
    assert len(shown) == 1
    rectangle = shown[0]["steps"][0]["elements"][0]
    assert rectangle["id"] == "rect-1"
    assert rectangle["kind"] == "rectangle"
    assert rectangle["author"] == "agent"


def test_a_turn_carries_a_whiteboard(make_client):
    """Scenario: a turn carries an artifact [CH-02]."""

    _stub, _session, events, saved = _run(make_client, [valid_whiteboard()])

    assert reply_text(events) == REPLY
    assert saved["turns"][0]["reply"] == REPLY
    artifacts = saved["turns"][0]["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["kind"] == "whiteboard"
    assert [event["artifact"]["kind"] for event in events if "artifact" in event] == [
        "whiteboard"
    ]


def test_the_agent_tool_returns_check_errors(tmp_path: Path):
    stored: list[tuple[str, dict]] = []

    def store(session_id: str, drawing: dict) -> dict:
        stored.append((session_id, drawing))
        return {"id": drawing["id"]}

    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", _bad_drawing()))

    assert stored == []
    assert payload["is_error"] is True
    assert "triangle" in payload["content"][0]["text"]


def test_the_agent_tool_stores_a_valid_drawing(tmp_path: Path):
    stored: list[tuple[str, dict]] = []

    def store(session_id: str, drawing: dict) -> dict:
        stored.append((session_id, drawing))
        return {"id": drawing["id"]}

    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", valid_whiteboard()))

    assert payload.get("is_error") is not True
    assert stored[0][0] == "session-9"
    assert stored[0][1]["session_id"] == "session-9"
    assert stored[0][1]["id"] == "wb-1"
    assert "wb-1" in payload["content"][0]["text"]


def test_a_drawing_sent_as_json_strings_is_stored(tmp_path: Path):
    """The model sends steps and comments as JSON text when the tool schema leaves them untyped."""

    stored: list[dict] = []

    def store(_session_id: str, drawing: dict) -> dict:
        stored.append(drawing)
        return {"id": drawing["id"]}

    drawing = _formula_drawing()
    encoded = {
        **drawing,
        "version": str(drawing["version"]),
        "steps": json.dumps(drawing["steps"]),
        "comments": "[]",
    }
    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", encoded))

    assert payload.get("is_error") is not True
    assert stored[0]["version"] == 5
    assert stored[0]["steps"][0]["elements"][0]["kind"] == "math"
    assert stored[0]["comments"] == []


def test_a_new_described_whiteboard_is_stored_as_version_4(tmp_path: Path):
    stored: list[dict] = []

    def store(_session_id: str, drawing: dict) -> dict:
        stored.append(drawing)
        return {"id": drawing["id"]}

    drawing = valid_whiteboard()
    drawing["description"] = "Two boxes show one half of a whole."
    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", drawing))

    assert payload.get("is_error") is not True
    assert stored[0]["version"] == 4
    assert stored[0]["description"] == "Two boxes show one half of a whole."


def test_a_formula_whiteboard_is_stored_as_version_5(tmp_path: Path):
    stored: list[dict] = []

    def store(_session_id: str, drawing: dict) -> dict:
        stored.append(drawing)
        return {"id": drawing["id"]}

    drawing = _formula_drawing()
    drawing["version"] = 4
    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", drawing))

    assert payload.get("is_error") is not True
    assert stored[0]["version"] == 5
    assert stored[0]["steps"][0]["elements"][0]["kind"] == "math"
    assert stored[0]["steps"][0]["elements"][1]["kind"] == "code"


def test_a_graph_whiteboard_is_stored_as_version_6(tmp_path: Path):
    stored: list[dict] = []

    def store(_session_id: str, drawing: dict) -> dict:
        stored.append(drawing)
        return {"id": drawing["id"]}

    drawing = _graph_drawing()
    drawing["version"] = 4
    assert "plotted" not in drawing["steps"][0]["elements"][0]["series"][0]
    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, store)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", drawing))

    assert payload.get("is_error") is not True
    assert stored[0]["version"] == 6
    series = stored[0]["steps"][0]["elements"][0]["series"][0]
    assert series["plotted"] == [
        {"x": 0.0, "y": 1.0},
        {"x": 1.0, "y": 3.0},
        {"x": 2.0, "y": 5.0},
    ]


def _frame() -> dict:
    return {
        "version": 2,
        "id": "wb-1",
        "session_id": "session-1",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": [_element("frame-1", "rectangle")],
            }
        ],
    }


def _learner_drawing(frame: dict) -> dict:
    drawing = copy.deepcopy(frame)
    drawing["steps"][0]["elements"].append(
        _element(
            "answer-1",
            "rectangle",
            author="learner",
            position={"x": 40, "y": 50},
            size={"width": 70, "height": 30},
        )
    )
    drawing["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "my answer",
            "element_id": "answer-1",
        }
    ]
    return drawing


def _learner_parts(drawing: dict) -> tuple[list[dict], list[dict]]:
    elements = [
        element
        for step in drawing["steps"]
        for element in step["elements"]
        if element["author"] == "learner"
    ]
    comments = [
        comment
        for comment in drawing.get("comments", [])
        if comment["author"] == "learner"
    ]
    return elements, comments


class MarkingStub:
    """Stores one whiteboard, then marks the learner's answer. Does not call the model."""

    def __init__(self, marks: list[dict] | None = None, edited: dict | None = None) -> None:
        self.marks = marks
        self.edited = edited
        self.chat = None
        self.tool_results: list[dict] = []
        self.failures = 0
        self._replies = 0

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
        **_extra,
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
        self._replies += 1
        if not profile.facts:
            yield (
                "What should I know before I teach? "
                "How do you want to be taught, what can you already do, "
                "and where do you struggle?"
            )
            return
        assert self.chat is not None
        if self._replies == 1:
            yield REPLY
            submit_whiteboard(
                session_id,
                _frame(),
                failures=0,
                store=self.chat.create_whiteboard,
            )
            return
        yield "[[step:step-mark]] The circle shows the mistake."
        action = self.edited if self.edited is not None else _mark_action(self.marks)
        submission = submit_marks(
            session_id,
            action,
            failures=self.failures,
            store=self.chat.mark_whiteboard,
            create=self.chat.create_whiteboard,
        )
        self.failures = submission.failures
        self.tool_results.append(submission.tool_result)

    async def close_session(self, session_id: str) -> None:
        del session_id


def _prepared_answer(make_client, stub: MarkingStub):
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    saved = client.get(f"/api/sessions/{session['id']}").json()
    frame = saved["turns"][0]["artifacts"][0]
    drawing = _learner_drawing(frame)
    drawing.pop("kind", None)
    put = client.put(
        f"/api/sessions/{session['id']}/whiteboards/{drawing['id']}",
        json=drawing,
    )
    assert put.status_code == 200, put.text
    assert put.json()["version"] == 2
    return client, session, put.json()


def test_agent_marks_do_not_change_the_learners_drawing(make_client):
    """Scenario: agent marks do not change the learner's drawing [WB-09]."""

    stub = MarkingStub()
    client, session, before = _prepared_answer(make_client, stub)
    before_elements, before_comments = _learner_parts(before)

    events = post_turn(client, session["id"], "Mark the mistake in my answer.")
    loaded = client.get(
        f"/api/sessions/{session['id']}/whiteboards/{before['id']}"
    ).json()
    saved = client.get(f"/api/sessions/{session['id']}").json()
    after_elements, after_comments = _learner_parts(loaded)
    marks = [
        element
        for step in loaded["steps"]
        for element in step["elements"]
        if element["kind"] == "mark"
    ]

    assert after_elements == before_elements
    assert after_comments == before_comments
    assert loaded["version"] == MARKED_DRAWING_VERSION
    assert len(marks) == 1
    assert marks[0]["author"] == "agent"
    assert marks[0]["mark"] == "circle"
    assert marks[0]["target_element_id"] == "answer-1"
    assert marks[0]["id"] != before_elements[0]["id"]
    streamed = _streamed(events)
    assert len(streamed) == 1
    assert streamed[0]["id"] == before["id"]
    assert _learner_parts(streamed[0]) == (before_elements, before_comments)
    assert saved["turns"][0]["artifacts"][0]["id"] == before["id"]
    assert saved["turns"][0]["artifacts"][0]["version"] == MARKED_DRAWING_VERSION
    assert saved["turns"][1]["artifacts"] == []
    assert stub.tool_results[0].get("is_error") is not True


def test_the_mark_tool_refuses_a_changed_learner_element(make_client):
    edited = _learner_drawing(_frame())
    edited["version"] = MARKED_DRAWING_VERSION
    edited["steps"][0]["elements"][1]["position"] = {"x": 9, "y": 9}
    edited["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    stub = MarkingStub(edited=edited)
    client, session, before = _prepared_answer(make_client, stub)
    before_elements, _before_comments = _learner_parts(before)

    post_turn(client, session["id"], "Mark the mistake in my answer.")
    loaded = client.get(
        f"/api/sessions/{session['id']}/whiteboards/{before['id']}"
    ).json()

    assert stub.tool_results[0]["is_error"] is True
    message = stub.tool_results[0]["content"][0]["text"]
    assert "answer-1" in message
    assert "changed" in message
    assert "Fix the drawing and call draw_whiteboard again." in message
    assert _learner_parts(loaded)[0] == before_elements
    assert loaded["version"] == 2


def test_a_failed_reply_rolls_back_marks(make_client):
    from polaris.teaching import TeachingFailed

    class FailingMark(MarkingStub):
        async def reply(self, **kwargs):
            async for chunk in super().reply(**kwargs):
                yield chunk
            if self._replies > 1:
                raise TeachingFailed("the reply failed")

    stub = FailingMark()
    client, session, before = _prepared_answer(make_client, stub)
    response = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": "Mark the mistake in my answer."},
    )
    events, rest = parse_sse(response.text)
    loaded = client.get(
        f"/api/sessions/{session['id']}/whiteboards/{before['id']}"
    ).json()

    assert response.status_code == 200, response.text
    assert rest == ""
    assert any("error" in event for event in events)
    assert loaded["version"] == 2
    assert _learner_parts(loaded) == _learner_parts(before)
    assert not any(
        element["kind"] == "mark"
        for step in loaded["steps"]
        for element in step["elements"]
    )


def test_the_agent_tool_appends_marks_and_refuses_edits(tmp_path: Path):
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None
    saved: list[dict] = []

    def mark(_session_id: str, action: dict) -> dict:
        result = apply_marks(stored, action)
        if result.whiteboard is None:
            raise InvalidDrawing(result.errors)
        payload = result.whiteboard.model_dump(mode="json")
        saved.append(payload)
        return payload

    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, mark_whiteboard=mark)

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", _mark_action()))

    assert payload.get("is_error") is not True
    assert saved[0]["version"] == MARKED_DRAWING_VERSION
    assert saved[0]["steps"][0]["elements"] == _answer_drawing()["steps"][0]["elements"]

    edited = _answer_drawing()
    edited["version"] = MARKED_DRAWING_VERSION
    edited["steps"][0]["elements"][0]["position"] = {"x": 1, "y": 1}
    edited["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    refused = asyncio.run(agent.handle_draw_whiteboard("session-9", edited))

    assert refused["is_error"] is True
    assert "answer-1" in refused["content"][0]["text"]
    assert "changed" in refused["content"][0]["text"]
    assert len(saved) == 1


def test_a_failed_reply_discards_its_unattached_whiteboard(make_client):
    from polaris.teaching import TeachingFailed

    class FailingStub(DrawingStub):
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
            **_extra,
        ):
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
            raise TeachingFailed("the reply failed")

    stub = FailingStub([valid_whiteboard()])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    response = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": LEARNER},
    )
    events, rest = parse_sse(response.text)
    saved = client.get(f"/api/sessions/{session['id']}").json()

    assert response.status_code == 200, response.text
    assert rest == ""
    assert any("error" in event for event in events)
    assert saved["turns"] == []
    assert _whiteboards(saved) == []


SIMPLER_REQUEST = "Draw a simpler version of this whiteboard."


def _counted_drawing(count: int, **fields: object) -> dict:
    data: dict[str, object] = {
        "version": 4,
        "id": "wb-simple",
        "session_id": "session-1",
        "description": "One box stands for the whole.",
        "simplifies": "wb-1",
        "steps": [
            {
                "id": "step-simple",
                "reply_part": "[[step:step-simple]]",
                "elements": [
                    _element(f"box-{index}", "rectangle") for index in range(count)
                ],
            }
        ],
    }
    data.update(fields)
    return data


class SimplerStub:
    """Stores one whiteboard, then redraws it when the learner asks for a simpler one."""

    def __init__(self, redraws: list[dict]) -> None:
        self.redraws = redraws
        self.chat = None
        self.simplify = None
        self.calls = 0
        self.tool_results: list[dict] = []
        self.failures = 0

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
        **_extra,
    ):
        del prior_turns, sdk_session_id, whiteboards, pointing
        self.calls += 1
        self.failures = 0
        if not profile.facts:
            yield (
                "What should I know before I teach? "
                "How do you want to be taught, what can you already do, "
                "and where do you struggle?"
            )
            return
        assert self.chat is not None
        if simplify is None:
            yield REPLY
            submission = submit_whiteboard(
                session_id,
                valid_whiteboard(),
                failures=0,
                store=self.chat.create_whiteboard,
            )
            self.tool_results.append(submission.tool_result)
            return
        self.simplify = simplify
        yield f"A simpler drawing for {learner_message}"
        for drawing in self.redraws:
            submission = submit_whiteboard(
                session_id,
                drawing,
                failures=self.failures,
                store=self.chat.create_whiteboard,
            )
            self.failures = submission.failures
            self.tool_results.append(submission.tool_result)

    async def close_session(self, session_id: str) -> None:
        del session_id


def _ask_simpler(client, session_id: str, whiteboard_id: str):
    return client.post(
        f"/api/sessions/{session_id}/turns",
        json={"message": SIMPLER_REQUEST, "simplifies": whiteboard_id},
    )


def _element_total(drawing: dict) -> int:
    return sum(len(step["elements"]) for step in drawing["steps"])


def test_a_simpler_redraw_keeps_the_first_one(make_client):
    """Scenario: a simpler redraw keeps the first one [WB-11]."""

    stub = SimplerStub([_counted_drawing(1)])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    original = client.get(f"/api/sessions/{session['id']}/whiteboards/wb-1").json()

    response = _ask_simpler(client, session["id"], "wb-1")

    assert response.status_code == 200, response.text
    events, rest = parse_sse(response.text)
    assert rest == ""
    streamed = _streamed(events)
    assert len(streamed) == 1
    assert streamed[0]["id"] == "wb-simple"
    assert streamed[0]["simplifies"] == "wb-1"
    assert streamed[0]["version"] == 4
    assert _element_total(streamed[0]) == 1
    assert _element_total(original) == 7
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert saved["turns"][0]["artifacts"][0]["id"] == "wb-1"
    assert "simplifies" not in saved["turns"][0]["artifacts"][0]
    assert saved["turns"][1]["learner_message"] == SIMPLER_REQUEST
    assert saved["turns"][1]["artifacts"][0]["id"] == "wb-simple"
    still = client.get(f"/api/sessions/{session['id']}/whiteboards/wb-1")
    assert still.status_code == 200
    assert still.json() == original
    opened = client.get(f"/api/sessions/{session['id']}/whiteboards/wb-simple")
    assert opened.status_code == 200
    assert opened.json()["simplifies"] == "wb-1"
    assert stub.simplify is not None
    assert stub.simplify.id == "wb-1"


def test_a_simpler_whiteboard_that_is_not_smaller_is_not_stored(make_client):
    stub = SimplerStub([_counted_drawing(7), _counted_drawing(8, id="wb-more")])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    original = client.get(f"/api/sessions/{session['id']}/whiteboards/wb-1").json()

    response = _ask_simpler(client, session["id"], "wb-1")

    assert response.status_code == 200, response.text
    events, rest = parse_sse(response.text)
    assert rest == ""
    assert _streamed(events) == []
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert _whiteboards(saved) == [original]
    assert len(stub.tool_results) == 3
    for result in stub.tool_results[1:]:
        text = result["content"][0]["text"]
        assert result["is_error"] is True
        assert "fewer elements" in text
        assert "Fix the drawing and call draw_whiteboard again." in text
    still = client.get(f"/api/sessions/{session['id']}/whiteboards/wb-1")
    assert still.json() == original


def test_a_simpler_whiteboard_with_zero_elements_is_not_stored(make_client):
    stub = SimplerStub([_counted_drawing(0)])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    response = _ask_simpler(client, session["id"], "wb-1")

    assert response.status_code == 200, response.text
    events, rest = parse_sse(response.text)
    assert rest == ""
    assert _streamed(events) == []
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert [item["id"] for item in _whiteboards(saved)] == ["wb-1"]
    text = stub.tool_results[-1]["content"][0]["text"]
    assert stub.tool_results[-1]["is_error"] is True
    assert "at least one element" in text
    assert "Fix the drawing and call draw_whiteboard again." in text


def test_a_smaller_redraw_is_stored_after_a_refused_attempt(make_client):
    stub = SimplerStub([_counted_drawing(7), _counted_drawing(1)])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    response = _ask_simpler(client, session["id"], "wb-1")

    assert response.status_code == 200, response.text
    events, rest = parse_sse(response.text)
    assert rest == ""
    streamed = _streamed(events)
    assert [item["id"] for item in streamed] == ["wb-simple"]
    assert stub.tool_results[-2]["is_error"] is True
    assert stub.tool_results[-1].get("is_error") is not True
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert [item["id"] for item in _whiteboards(saved)] == ["wb-1", "wb-simple"]


def test_a_drawing_without_simplifies_is_not_compared(make_client):
    """A new whiteboard with no simplifies field skips the element-count rule."""

    class AnotherDrawingStub(SimplerStub):
        async def reply(self, **kwargs):
            if kwargs.get("simplify") is not None:
                raise AssertionError("this turn did not ask for a simpler version")
            if self.calls == 0:
                async for chunk in super().reply(**kwargs):
                    yield chunk
                return
            self.calls += 1
            drawing = valid_whiteboard()
            drawing["id"] = "wb-2"
            drawing["description"] = "The same parts, drawn again."
            yield "Another picture."
            assert self.chat is not None
            submission = submit_whiteboard(
                kwargs["session_id"],
                drawing,
                failures=0,
                store=self.chat.create_whiteboard,
            )
            self.tool_results.append(submission.tool_result)

    stub = AnotherDrawingStub([])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    events = post_turn(client, session["id"], "Draw it again.")

    streamed = _streamed(events)
    assert len(streamed) == 1
    assert streamed[0]["id"] == "wb-2"
    assert streamed[0]["version"] == 4
    assert "simplifies" not in streamed[0]
    assert _element_total(streamed[0]) == 7
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert [item["id"] for item in _whiteboards(saved)] == ["wb-1", "wb-2"]


def test_an_unknown_whiteboard_is_refused_before_a_simpler_redraw(make_client):
    stub = SimplerStub([_counted_drawing(1)])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)

    missing = _ask_simpler(client, session["id"], "wb-missing")

    assert missing.status_code == 404
    assert stub.calls == 1
    assert stub.simplify is None
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert len(saved["turns"]) == 1


def test_a_simpler_request_from_another_session_is_refused(make_client):
    stub = SimplerStub([_counted_drawing(1)])
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], LEARNER)
    other = client.post("/api/sessions").json()

    elsewhere = _ask_simpler(client, other["id"], "wb-1")

    assert elsewhere.status_code == 404
    assert stub.calls == 1
    assert client.get(f"/api/sessions/{other['id']}").json()["turns"] == []
