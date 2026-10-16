"""Quiz scenarios: QZ-01 through QZ-11, CH-02, and decisions 0002 and 0006.

A filled profile is seeded so a quiz can be created without teaching on an
empty profile. Nothing here writes the profile.
"""

import copy
import json

import pytest

from polaris.models import Profile
from polaris.quiz import InvalidQuiz, describe_result, normalize_spec, public_payload
from polaris.teaching import TeachingFailed, turn_prompt
from test_chat import (
    EMPTY_PROFILE_REPLY,
    make_client,
    parse_sse,
    post_turn,
    reply_text,
)

FILLED_PROFILE = '{\n  "facts": ["wants short explanations"]\n}\n'

QUIZ_SPEC = {
    "title": "Fractions",
    "questions": [
        {
            "id": "q1",
            "prompt": "What is 1/2 of 4?",
            "choices": [
                {"id": "a", "text": "1", "why_wrong": "1 is half of 2, not of 4."},
                {"id": "b", "text": "2"},
                {"id": "c", "text": "4", "why_wrong": "4 is the whole, not half of it."},
            ],
            "correct_choice_id": "b",
            "explanation": "Half of 4 is 2, because 4 divided by 2 is 2.",
        },
        {
            "id": "q2",
            "prompt": "Which fraction equals one whole?",
            "choices": [
                {"id": "a", "text": "1/2", "why_wrong": "1/2 is one of two halves."},
                {"id": "b", "text": "2/2"},
            ],
            "correct_choice_id": "b",
            "explanation": "2/2 means two halves, which make one whole.",
        },
    ],
}


class QuizCreatingStub:
    """Creates a stored quiz during a teaching reply. Does not grade."""

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.chat = None
        self.reply_count = 0
        self.seen_quizzes: list[list[dict]] = []
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
        quizzes=(),
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
        self.reply_count += 1
        self.seen_quizzes.append(list(quizzes))
        if not profile.facts:
            yield EMPTY_PROFILE_REPLY
            return
        yield "Here is a quiz to check what you understood."
        assert self.chat is not None
        self.chat.create_quiz(session_id, self.spec)

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


def _forbidden_fields(value, *, in_question: bool) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if in_question and key in {"answer", "correct"}:
                found.append(key)
            nested_question = in_question or key == "questions"
            if key == "questions":
                for item in child:
                    found.extend(_forbidden_fields(item, in_question=True))
            else:
                found.extend(
                    _forbidden_fields(child, in_question=nested_question)
                )
    elif isinstance(value, list):
        for item in value:
            found.extend(_forbidden_fields(item, in_question=in_question))
    return found


def _quiz_from_session(session: dict) -> dict:
    quizzes = [
        artifact
        for turn in session["turns"]
        for artifact in turn["artifacts"]
        if artifact["kind"] == "quiz"
    ]
    assert len(quizzes) == 1
    return quizzes[0]


def _make_quiz(make_client, spec: dict = QUIZ_SPEC):
    stub = QuizCreatingStub(spec)
    client, agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    events = post_turn(client, session["id"], "Quiz me on fractions.")
    saved = client.get(f"/api/sessions/{session['id']}").json()
    return client, agent, session, events, saved


def test_creating_a_quiz_stores_it_as_an_artifact_of_that_session(make_client):
    client, _agent, session, events, saved = _make_quiz(make_client)

    assert reply_text(events) == "Here is a quiz to check what you understood."
    quiz = _quiz_from_session(saved)
    assert quiz["title"] == "Fractions"
    assert saved["id"] == session["id"]
    listed = client.get(f"/api/quizzes/{quiz['id']}").json()
    assert listed["id"] == quiz["id"]
    assert listed["session_id"] == session["id"]


def test_quiz_starts_in_the_chat_turn_that_created_it(make_client):
    _client, _agent, _session, events, saved = _make_quiz(make_client)

    artifacts = [event["artifact"] for event in events if "artifact" in event]
    assert len(artifacts) == 1
    assert artifacts[0]["kind"] == "quiz"
    assert saved["turns"][0]["artifacts"] == artifacts
    assert saved["turns"][0]["reply"] == "Here is a quiz to check what you understood."


def test_quiz_payload_has_no_answers(make_client):
    _client, _agent, _session, events, saved = _make_quiz(make_client)

    artifacts = [event["artifact"] for event in events if "artifact" in event]
    assert artifacts
    assert _forbidden_fields(artifacts[0], in_question=False) == []
    assert _forbidden_fields(saved, in_question=False) == []
    questions = artifacts[0]["questions"]
    assert [question["id"] for question in questions] == ["q1", "q2"]
    assert [choice["text"] for choice in questions[0]["choices"]] == ["1", "2", "4"]
    encoded = json.dumps(questions)
    assert "correct_choice_id" not in encoded
    assert "explanation" not in encoded
    assert "why_wrong" not in encoded
    assert "is half of 2" not in json.dumps(saved)
    assert artifacts[0]["score"] is None
    assert "feedback" not in artifacts[0]


def test_one_correct_choice(make_client):
    client, _agent = make_client(profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    chat = client.app.state.chat
    none_correct = {
        "title": "Broken",
        "questions": [
            {
                "id": "q1",
                "prompt": "Pick one",
                "choices": [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}],
                "explanation": "There is no marked choice.",
            }
        ],
    }
    missing_choice = {
        "title": "Broken",
        "questions": [
            {
                "id": "q1",
                "prompt": "Pick one",
                "choices": [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}],
                "correct_choice_id": "z",
                "explanation": "The marked id is not a choice.",
            }
        ],
    }

    with pytest.raises(InvalidQuiz):
        chat.create_quiz(session["id"], none_correct)
    with pytest.raises(InvalidQuiz):
        chat.create_quiz(session["id"], missing_choice)

    assert client.get(f"/api/sessions/{session['id']}").json()["turns"] == []


def test_code_grades_the_quiz(make_client):
    client, agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)
    replies_before = agent.reply_count

    graded = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "a", "q2": "b"}},
    )

    assert graded.status_code == 200, graded.text
    body = graded.json()
    assert body["score"] == {"earned": 1, "total": 2}
    assert agent.reply_count == replies_before
    assert _forbidden_fields(body, in_question=False) == []


def test_grading_shows_the_key(make_client):
    """QZ-03, QZ-06: once graded, every question is explained and a miss shows the key."""

    client, _agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)

    body = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "a", "q2": "b"}},
    ).json()

    assert body["feedback"] == [
        {
            "question_id": "q1",
            "right": False,
            "correct_choice_id": "b",
            "explanation": "Half of 4 is 2, because 4 divided by 2 is 2.",
            "why_wrong": "1 is half of 2, not of 4.",
        },
        {
            "question_id": "q2",
            "right": True,
            "correct_choice_id": "b",
            "explanation": "2/2 means two halves, which make one whole.",
        },
    ]
    assert _forbidden_fields(body["questions"], in_question=True) == []
    reloaded = client.get(f"/api/quizzes/{quiz['id']}").json()
    assert reloaded["feedback"] == body["feedback"]


def test_a_wrong_choice_needs_a_note():
    """QZ-11: every wrong choice carries a note. The correct choice has none."""

    spec = copy.deepcopy(QUIZ_SPEC)
    del spec["questions"][0]["choices"][2]["why_wrong"]
    with pytest.raises(InvalidQuiz, match="q1: choice c needs a why_wrong note"):
        normalize_spec(spec)

    spec = copy.deepcopy(QUIZ_SPEC)
    spec["questions"][0]["choices"][1]["why_wrong"] = "It is right."
    stored = normalize_spec(spec)
    assert "why_wrong" not in stored["questions"][0]["choices"][1]


def test_a_quiz_stored_without_notes_still_grades(make_client):
    """Quizzes stored before QZ-11 have no notes. A miss still shows the key."""

    stored = normalize_spec(copy.deepcopy(QUIZ_SPEC))
    for question in stored["questions"]:
        for choice in question["choices"]:
            choice.pop("why_wrong", None)

    graded = public_payload(
        "quiz-1",
        "session-1",
        stored,
        score={"earned": 1, "total": 2},
        submitted={"q1": "a", "q2": "b"},
    )

    assert graded["feedback"][0] == {
        "question_id": "q1",
        "right": False,
        "correct_choice_id": "b",
        "explanation": "Half of 4 is 2, because 4 divided by 2 is 2.",
    }


def test_score_is_kept_with_the_quiz(make_client):
    client, _agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)

    client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "b", "q2": "a"}},
    )
    reloaded = client.get(f"/api/quizzes/{quiz['id']}").json()
    session = client.get(f"/api/sessions/{saved['id']}").json()

    assert reloaded["score"] == {"earned": 1, "total": 2}
    assert _quiz_from_session(session)["score"] == {"earned": 1, "total": 2}


def test_the_next_reply_sees_the_quiz_score(make_client):
    """QZ-09: the next teaching reply reads the score and the missed questions."""

    client, agent, session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)
    client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "a", "q2": "b"}},
    )

    post_turn(client, session["id"], "How did I do?")

    seen = agent.seen_quizzes[-1]
    assert [item["id"] for item in seen] == [quiz["id"]]
    assert seen[0]["score"] == {"earned": 1, "total": 2}
    assert [item["question_id"] for item in seen[0]["feedback"] if not item["right"]] == [
        "q1"
    ]


def test_quiz_result_names_the_learner_choice_and_the_key():
    """QZ-09: a missed question names the learner's choice, the correct one, and the note."""

    stored = normalize_spec(copy.deepcopy(QUIZ_SPEC))
    graded = public_payload(
        "quiz-1",
        "session-1",
        stored,
        score={"earned": 1, "total": 2},
        submitted={"q1": "a", "q2": "b"},
    )
    ungraded = public_payload("quiz-2", "session-1", stored, score=None, submitted=None)

    text = describe_result(graded)
    lines = text.splitlines()
    assert lines[0] == 'Quiz quiz-1 "Fractions": the learner scored 1 of 2.'
    assert lines[1] == (
        '- q1 wrong: What is 1/2 of 4? The learner chose "1". '
        'The correct choice is "2". Why their choice is wrong: 1 is half of 2, not of 4.'
    )
    assert lines[2] == '- q2 right: Which fraction equals one whole? The learner chose "2/2".'
    assert describe_result(ungraded) == 'Quiz quiz-2 "Fractions": not graded yet.'

    prompt = turn_prompt(
        Profile(("wants short explanations",)), "How did I do?", quizzes=(graded,)
    )
    section = prompt.split("Quizzes in this session", 1)[1]
    assert text in section
    assert "correct_choice_id" not in prompt

    ungraded_prompt = turn_prompt(
        Profile(("wants short explanations",)), "Hint?", quizzes=(ungraded,)
    )
    assert "The correct choice" not in ungraded_prompt
    assert "half of 2" not in ungraded_prompt


def test_the_learner_expands_the_quiz(make_client):
    client, _agent, _session, _events, saved = _make_quiz(make_client)
    in_chat = _quiz_from_session(saved)

    page = client.get(f"/api/quizzes/{in_chat['id']}")
    assert page.status_code == 200, page.text
    expanded = page.json()

    assert expanded["id"] == in_chat["id"]
    assert expanded["questions"] == in_chat["questions"]
    assert expanded["score"] is None

    client.post(
        f"/api/quizzes/{in_chat['id']}/grade",
        json={"choices": {"q1": "b", "q2": "b"}},
    )
    after_chat = _quiz_from_session(
        client.get(f"/api/sessions/{saved['id']}").json()
    )
    after_page = client.get(f"/api/quizzes/{in_chat['id']}").json()
    assert after_page["id"] == after_chat["id"]
    assert after_page["questions"] == after_chat["questions"]
    assert after_page["score"] == after_chat["score"] == {"earned": 2, "total": 2}


def test_empty_profile_does_not_create_a_quiz(make_client):
    stub = QuizCreatingStub(QUIZ_SPEC)
    client, _agent = make_client(stub)
    session = client.post("/api/sessions").json()

    events = post_turn(client, session["id"], "Quiz me on fractions.")

    assert reply_text(events) == EMPTY_PROFILE_REPLY
    assert [event for event in events if "artifact" in event] == []
    assert client.get(f"/api/sessions/{session['id']}").json()["turns"] == [
        {
            "learner_message": "Quiz me on fractions.",
            "reply": EMPTY_PROFILE_REPLY,
            "artifacts": [],
        }
    ]
    assert client.get("/api/profile").json() == {"facts": []}


def test_grading_twice_keeps_the_original_score(make_client):
    client, _agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)

    first = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "b", "q2": "b"}},
    )
    second = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "a", "q2": "a"}},
    )
    reloaded = client.get(f"/api/quizzes/{quiz['id']}").json()

    assert first.status_code == 200, first.text
    assert first.json()["score"] == {"earned": 2, "total": 2}
    assert second.status_code == 409
    assert reloaded["score"] == {"earned": 2, "total": 2}
    assert reloaded["submitted"] == {"q1": "b", "q2": "b"}


@pytest.mark.parametrize(
    "choices",
    [
        {},
        {"q1": "b"},
        {"q1": "b", "q2": "b", "q3": "a"},
        {"q1": "b", "q2": "z"},
    ],
)
def test_invalid_submission_is_rejected_and_not_stored(make_client, choices):
    client, _agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)

    response = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": choices},
    )
    reloaded = client.get(f"/api/quizzes/{quiz['id']}").json()

    assert response.status_code == 422, response.text
    assert reloaded["score"] is None
    assert "submitted" not in reloaded
    assert "feedback" not in reloaded


def test_unknown_quiz_is_not_found(make_client):
    client, _agent = make_client()
    missing = "00000000-0000-0000-0000-000000000000"

    listed = client.get(f"/api/quizzes/{missing}")
    graded = client.post(
        f"/api/quizzes/{missing}/grade",
        json={"choices": {"q1": "a"}},
    )

    assert listed.status_code == 404
    assert graded.status_code == 404


class FailingAfterQuizStub:
    """Creates a quiz, then fails the reply so the turn is not stored."""

    def __init__(self, spec: dict) -> None:
        self.spec = spec
        self.chat = None
        self.quiz_id: str | None = None
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
        quizzes=(),
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify, quizzes
        if not profile.facts:
            yield EMPTY_PROFILE_REPLY
            return
        yield "Here is a quiz to check what you understood."
        assert self.chat is not None
        self.quiz_id = self.chat.create_quiz(session_id, self.spec)["id"]
        raise TeachingFailed("the reply failed")

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


def test_failed_reply_discards_its_unattached_quiz(make_client):
    stub = FailingAfterQuizStub(QUIZ_SPEC)
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()

    response = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": "Quiz me on fractions."},
    )
    events, rest = parse_sse(response.text)
    saved = client.get(f"/api/sessions/{session['id']}").json()

    assert response.status_code == 200, response.text
    assert rest == ""
    assert any("error" in event for event in events)
    assert stub.quiz_id is not None
    assert client.get(f"/api/quizzes/{stub.quiz_id}").status_code == 404
    assert saved["turns"] == []


def test_duplicate_question_ids_are_rejected(make_client):
    client, _agent = make_client(profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    spec = copy.deepcopy(QUIZ_SPEC)
    spec["questions"][1]["id"] = "q1"

    with pytest.raises(InvalidQuiz, match="question ids must be unique"):
        client.app.state.chat.create_quiz(session["id"], spec)


def test_unique_question_ids_are_stored(make_client):
    _client, _agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)
    ids = [question["id"] for question in quiz["questions"]]

    assert ids == ["q1", "q2"]
    assert len(ids) == len(set(ids))


def test_a_question_needs_at_least_two_choices(make_client):
    client, _agent = make_client(profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    spec = {
        "title": "Broken",
        "questions": [
            {
                "id": "q1",
                "prompt": "Pick one",
                "choices": [{"id": "a", "text": "1"}],
                "correct_choice_id": "a",
                "explanation": "There is only one choice.",
            }
        ],
    }

    with pytest.raises(InvalidQuiz, match="q1: needs at least 2 choices"):
        client.app.state.chat.create_quiz(session["id"], spec)


def test_blank_explanation_names_the_question():
    spec = copy.deepcopy(QUIZ_SPEC)
    spec["questions"][1]["explanation"] = "   "

    with pytest.raises(InvalidQuiz, match="q2: explanation is blank"):
        normalize_spec(spec)


def test_missing_correct_choice_names_the_question():
    spec = copy.deepcopy(QUIZ_SPEC)
    del spec["questions"][0]["correct_choice_id"]

    with pytest.raises(InvalidQuiz, match="q1: needs exactly one correct choice"):
        normalize_spec(spec)


def test_blank_title_is_named_as_the_reason():
    spec = copy.deepcopy(QUIZ_SPEC)
    spec["title"] = "   "

    with pytest.raises(InvalidQuiz, match="title is blank"):
        normalize_spec(spec)


def test_correct_choice_id_is_trimmed(make_client):
    spec = copy.deepcopy(QUIZ_SPEC)
    spec["questions"][0]["correct_choice_id"] = "  b  "
    client, _agent, _session, _events, saved = _make_quiz(make_client, spec)
    quiz = _quiz_from_session(saved)

    graded = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "b", "q2": "b"}},
    )

    assert graded.status_code == 200, graded.text
    assert graded.json()["score"] == {"earned": 2, "total": 2}
