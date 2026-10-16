"""Quiz scenarios: QZ-01 through QZ-10, CH-02, and decision 0002.

A filled profile is seeded so a quiz can be created without teaching on an
empty profile. Nothing here writes the profile.
"""

import copy
import json
import random

import pytest

from polaris.quiz import InvalidQuiz, grade, normalize_spec
from polaris.teaching import TeachingFailed
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
                {"id": "a", "text": "1"},
                {"id": "b", "text": "2"},
                {"id": "c", "text": "4"},
            ],
            "correct_choice_id": "b",
            "explanation": "Half of 4 is 2, because 4 divided by 2 is 2.",
        },
        {
            "id": "q2",
            "prompt": "Which fraction equals one whole?",
            "choices": [
                {"id": "a", "text": "1/2"},
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
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
        self.reply_count += 1
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
    # QZ-09 shuffles the choices, so only the set of texts is fixed.
    assert sorted(choice["text"] for choice in questions[0]["choices"]) == ["1", "2", "4"]
    encoded = json.dumps(questions)
    assert "correct_choice_id" not in encoded
    assert "explanation" not in encoded
    assert artifacts[0]["score"] is None
    assert "mistakes" not in artifacts[0]


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


def test_after_grading_wrong_questions_are_explained(make_client):
    client, _agent, _session, _events, saved = _make_quiz(make_client)
    quiz = _quiz_from_session(saved)

    body = client.post(
        f"/api/quizzes/{quiz['id']}/grade",
        json={"choices": {"q1": "a", "q2": "b"}},
    ).json()

    assert body["mistakes"] == [
        {
            "question_id": "q1",
            "explanation": "Half of 4 is 2, because 4 divided by 2 is 2.",
        }
    ]
    assert "q2" not in [mistake["question_id"] for mistake in body["mistakes"]]
    assert _forbidden_fields(body["questions"], in_question=True) == []


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
    assert "mistakes" not in reloaded


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
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
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


FIRST_IS_CORRECT = {
    "title": "Fractions",
    "questions": [
        {
            "id": "q1",
            "prompt": "What is 1/2 of 8?",
            "choices": [
                {"id": "a", "text": "4"},
                {"id": "b", "text": "2"},
                {"id": "c", "text": "8"},
                {"id": "d", "text": "16"},
            ],
            "correct_choice_id": "a",
            "explanation": "Half of 8 is 4, because 8 divided by 2 is 4.",
        }
    ],
}


def test_choices_are_shuffled():
    rng = random.Random(0)
    positions = set()
    for _ in range(40):
        question = normalize_spec(FIRST_IS_CORRECT, rng=rng)["questions"][0]
        ids = [choice["id"] for choice in question["choices"]]
        positions.add(ids.index("a"))
        assert sorted(ids) == ["a", "b", "c", "d"]
        assert question["correct_choice_id"] == "a"

    assert positions != {0}


def test_shuffled_choices_keep_their_text_and_grade_against_the_key():
    stored = normalize_spec(FIRST_IS_CORRECT, rng=random.Random(1))
    texts = {choice["id"]: choice["text"] for choice in stored["questions"][0]["choices"]}

    assert texts == {"a": "4", "b": "2", "c": "8", "d": "16"}
    assert grade(stored, {"q1": "a"})[0] == {"earned": 1, "total": 1}
    assert grade(stored, {"q1": "b"})[0] == {"earned": 0, "total": 1}


def _with_choice_text(choice_id: str, text: str) -> dict:
    spec = copy.deepcopy(FIRST_IS_CORRECT)
    for choice in spec["questions"][0]["choices"]:
        if choice["id"] == choice_id:
            choice["text"] = text
    return spec


def _with_explanation(text: str) -> dict:
    spec = copy.deepcopy(FIRST_IS_CORRECT)
    spec["questions"][0]["explanation"] = text
    return spec


@pytest.mark.parametrize(
    ("spec", "reason"),
    [
        (_with_choice_text("d", "All of the above"), "refers to the other choices"),
        (_with_choice_text("d", "None of these"), "refers to the other choices"),
        (_with_choice_text("a", "Both of them"), "refers to the other choices"),
        (_with_choice_text("b", "B) 2"), "starts with a letter label"),
        (_with_choice_text("c", "(c) 8"), "starts with a letter label"),
        (_with_choice_text("c", " 4 "), "two choices have the same text"),
        (_with_explanation("Option A is right: 8 / 2 is 4."), "names a choice by its letter"),
        (_with_explanation("The answer (A) is 4."), "names a choice by its letter"),
        (
            _with_choice_text("a", "4, because half of a number is that number divided by 2"),
            "far longer than the others",
        ),
    ],
)
def test_a_choice_that_gives_the_answer_away_is_refused(spec, reason):
    with pytest.raises(InvalidQuiz, match=rf"^q1: .*{reason}"):
        normalize_spec(spec)


@pytest.mark.parametrize(
    "spec",
    [
        _with_choice_text("d", "a + b"),
        _with_choice_text("a", "Four halves of one"),
        _with_explanation("A wrong answer here usually means halving twice."),
        _with_explanation("The answer is 4, not 2 or 8."),
    ],
)
def test_ordinary_choices_and_explanations_are_not_refused(spec):
    assert normalize_spec(spec)["title"] == "Fractions"


def test_a_refused_quiz_is_not_stored(make_client):
    client, _agent = make_client(profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()

    with pytest.raises(InvalidQuiz):
        client.app.state.chat.create_quiz(
            session["id"], _with_choice_text("d", "All of the above")
        )

    assert client.get(f"/api/sessions/{session['id']}").json()["turns"] == []
