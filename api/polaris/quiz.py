"""Quiz artifacts: the answer key stays in the database until the quiz is
graded, and code grades it. A wrong choice's why_wrong note is part of the key."""

from typing import Any


class InvalidQuiz(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class MissingQuiz(Exception):
    def __init__(self) -> None:
        super().__init__("No quiz with that id.")


class AlreadyGraded(Exception):
    def __init__(self) -> None:
        super().__init__("That quiz has already been graded.")


class InvalidSubmission(Exception):
    def __init__(self) -> None:
        super().__init__("Each question needs exactly one valid choice.")


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the stored quiz body, or raise if QZ-05 would be broken."""

    title = spec.get("title")
    questions = spec.get("questions")
    if not isinstance(title, str) or not title.strip():
        raise InvalidQuiz("title is blank")
    if not isinstance(questions, list) or not questions:
        raise InvalidQuiz("questions are missing")
    stored_questions = [
        _normalize_question(question, index=index)
        for index, question in enumerate(questions, start=1)
    ]
    ids = [question["id"] for question in stored_questions]
    if len(ids) != len(set(ids)):
        raise InvalidQuiz("question ids must be unique")
    return {"title": title.strip(), "questions": stored_questions}


def public_payload(
    quiz_id: str,
    session_id: str,
    stored: dict[str, Any],
    *,
    score: dict[str, int] | None,
    submitted: dict[str, str] | None,
) -> dict[str, Any]:
    """Learner-visible quiz. Before grading, questions never include answer or
    correct fields (QZ-03). A graded quiz is locked, so its key is shown (QZ-06)."""

    payload: dict[str, Any] = {
        "id": quiz_id,
        "kind": "quiz",
        "session_id": session_id,
        "title": stored["title"],
        "questions": [_public_question(question) for question in stored["questions"]],
        "score": score,
    }
    if submitted is not None:
        payload["submitted"] = submitted
        payload["feedback"] = _feedback(stored["questions"], submitted)
    return payload


def grade(
    stored: dict[str, Any], submitted: dict[str, str]
) -> tuple[dict[str, int], dict[str, str]]:
    """Compare submitted choices to the stored key. The model is not involved."""

    questions = stored["questions"]
    expected = {question["id"]: question for question in questions}
    if not isinstance(submitted, dict) or set(submitted) != set(expected):
        raise InvalidSubmission()
    choices: dict[str, str] = {}
    for question_id, question in expected.items():
        choice_id = submitted[question_id]
        valid = {choice["id"] for choice in question["choices"]}
        if not isinstance(choice_id, str) or choice_id not in valid:
            raise InvalidSubmission()
        choices[question_id] = choice_id
    earned = sum(
        1
        for question in questions
        if choices[question["id"]] == question["correct_choice_id"]
    )
    return {"earned": earned, "total": len(questions)}, choices


def describe_result(payload: dict[str, Any]) -> str:
    """Text for the teaching agent about one quiz, built from the learner-visible
    payload. A quiz not yet graded shows no key."""

    title = f'Quiz {payload["id"]} "{payload["title"]}"'
    score = payload.get("score")
    if score is None:
        return f"{title}: not graded yet."
    submitted = payload.get("submitted") or {}
    feedback = {item["question_id"]: item for item in payload.get("feedback", [])}
    lines = [f"{title}: the learner scored {score['earned']} of {score['total']}."]
    for question in payload["questions"]:
        texts = {choice["id"]: choice["text"] for choice in question["choices"]}
        chosen = texts.get(submitted.get(question["id"], ""), "")
        item = feedback.get(question["id"], {})
        if item.get("right"):
            lines.append(
                f'- {question["id"]} right: {question["prompt"]} '
                f'The learner chose "{chosen}".'
            )
            continue
        line = (
            f'- {question["id"]} wrong: {question["prompt"]} '
            f'The learner chose "{chosen}". '
            f'The correct choice is "{texts.get(item.get("correct_choice_id", ""), "")}".'
        )
        if item.get("why_wrong"):
            line += f' Why their choice is wrong: {item["why_wrong"]}'
        lines.append(line)
    return "\n".join(lines)


def disagreements(
    stored: dict[str, Any], answers: dict[str, str]
) -> list[str]:
    """Questions where a check that never saw the key picked another choice (QZ-10)."""

    return [
        question["id"]
        for question in stored["questions"]
        if answers.get(question["id"]) != question["correct_choice_id"]
    ]


def check_view(stored: dict[str, Any]) -> dict[str, Any]:
    """The quiz as the key check sees it: no key, no explanation, no notes."""

    return {
        "title": stored["title"],
        "questions": [_public_question(question) for question in stored["questions"]],
    }


def _normalize_question(question: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(question, dict):
        raise InvalidQuiz(f"question {index} is not an object")
    question_id = question.get("id")
    if not isinstance(question_id, str) or not question_id.strip():
        raise InvalidQuiz(f"question {index} has a blank id")
    qid = question_id.strip()
    prompt = question.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise InvalidQuiz(f"{qid}: prompt is blank")
    raw_choices = question.get("choices")
    if not isinstance(raw_choices, list) or len(raw_choices) < 2:
        raise InvalidQuiz(f"{qid}: needs at least 2 choices")
    choices = [_normalize_choice(choice, question_id=qid) for choice in raw_choices]
    ids = [choice["id"] for choice in choices]
    if len(ids) != len(set(ids)):
        raise InvalidQuiz(f"{qid}: choice ids must be unique")
    correct_id = question.get("correct_choice_id")
    if isinstance(correct_id, str):
        correct_id = correct_id.strip()
    if not isinstance(correct_id, str) or correct_id not in ids:
        raise InvalidQuiz(f"{qid}: needs exactly one correct choice")
    explanation = question.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        raise InvalidQuiz(f"{qid}: explanation is blank")
    for choice in choices:
        if choice["id"] == correct_id:
            choice.pop("why_wrong", None)
        elif not choice.get("why_wrong"):
            raise InvalidQuiz(f"{qid}: choice {choice['id']} needs a why_wrong note")
    return {
        "id": qid,
        "prompt": prompt.strip(),
        "choices": choices,
        "correct_choice_id": correct_id,
        "explanation": explanation.strip(),
    }


def _normalize_choice(choice: Any, *, question_id: str) -> dict[str, str]:
    if not isinstance(choice, dict):
        raise InvalidQuiz(f"{question_id}: a choice is not an object")
    choice_id = choice.get("id")
    text = choice.get("text")
    if not isinstance(choice_id, str) or not choice_id.strip():
        raise InvalidQuiz(f"{question_id}: a choice has a blank id")
    if not isinstance(text, str) or not text.strip():
        raise InvalidQuiz(f"{question_id}: a choice has blank text")
    stored = {"id": choice_id.strip(), "text": text.strip()}
    note = choice.get("why_wrong")
    if isinstance(note, str) and note.strip():
        stored["why_wrong"] = note.strip()
    return stored


def _public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question["id"],
        "prompt": question["prompt"],
        "choices": [
            {"id": choice["id"], "text": choice["text"]}
            for choice in question["choices"]
        ],
    }


def _feedback(
    questions: list[dict[str, Any]], submitted: dict[str, str]
) -> list[dict[str, Any]]:
    shown: list[dict[str, Any]] = []
    for question in questions:
        picked = submitted.get(question["id"])
        right = picked == question["correct_choice_id"]
        item: dict[str, Any] = {
            "question_id": question["id"],
            "right": right,
            "correct_choice_id": question["correct_choice_id"],
            "explanation": question["explanation"],
        }
        if not right:
            note = next(
                (
                    choice.get("why_wrong")
                    for choice in question["choices"]
                    if choice["id"] == picked
                ),
                None,
            )
            if note:
                item["why_wrong"] = note
        shown.append(item)
    return shown
