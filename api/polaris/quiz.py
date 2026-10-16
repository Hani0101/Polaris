"""Quiz artifacts: the answer key stays in the database and code grades it."""

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
    """Learner-visible quiz. Questions never include answer or correct fields."""

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
        payload["mistakes"] = _mistakes(stored["questions"], submitted)
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
    return {"id": choice_id.strip(), "text": text.strip()}


def _public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": question["id"],
        "prompt": question["prompt"],
        "choices": [
            {"id": choice["id"], "text": choice["text"]}
            for choice in question["choices"]
        ],
    }


def _mistakes(
    questions: list[dict[str, Any]], submitted: dict[str, str]
) -> list[dict[str, str]]:
    wrong: list[dict[str, str]] = []
    for question in questions:
        if submitted.get(question["id"]) != question["correct_choice_id"]:
            wrong.append(
                {
                    "question_id": question["id"],
                    "explanation": question["explanation"],
                }
            )
    return wrong
