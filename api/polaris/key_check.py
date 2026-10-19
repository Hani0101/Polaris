"""Key check for a new quiz (QZ-12). A second model answers the quiz
without the key, so a quiz whose key disagrees can be refused.

Uses one-shot query() with structured output (streaming-vs-single-mode,
structured-outputs). model="haiku" (configuration, model aliases).
setting_sources=[] and skills=[] keep filesystem settings and skills out.
verbatim_prompts sends the quiz text without @path expansion.
The prompt is built only from learner-visible fields, so the key, the
explanation and the wrong-choice notes never reach the checking model.
A result counts only when its subtype is "success" and structured_output
is present (structured-outputs, error handling); anything else raises
KeyCheckFailed. The query runs on the shared queue of one-shot Claude calls,
on a loop that can spawn the Claude CLI, as the profile pass does.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)

from polaris.login import ApiKeyPresent, reject_api_key_credential
from polaris.tool_policy import DISALLOWED_TOOLS
from polaris.work_queue import TURN_CALLS, run_claude_call

QueryFn = Callable[..., AsyncIterator[object]]


class KeyCheckFailed(Exception):
    """The check could not produce a usable answer for every question."""


class KeyCheck(Protocol):
    async def answer(self, quiz: dict[str, Any]) -> dict[str, str]:
        """Answer every question without the key. Returns question_id -> choice_id."""
        ...


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "choice_id": {"type": "string"},
                },
                "required": ["question_id", "choice_id"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["answers"],
    "additionalProperties": False,
}


def key_check_prompt() -> str:
    return (
        "You answer one multiple-choice quiz.\n"
        "For each question, pick exactly one choice id: the one that is correct.\n"
        "Answer every question once. Use the question ids and choice ids as given.\n"
        "Work each question out carefully before you pick.\n"
        "Do not teach. Do not explain. Do not draw. Do not create a quiz.\n"
    )


def _visible_questions(
    quiz: dict[str, Any],
) -> list[tuple[str, str, list[tuple[str, str]]]]:
    """Read only the learner-visible fields of each question."""

    raw = quiz.get("questions")
    if not isinstance(raw, list) or not raw:
        raise KeyCheckFailed("The quiz has no questions to check.")
    questions: list[tuple[str, str, list[tuple[str, str]]]] = []
    for question in raw:
        if not isinstance(question, dict):
            raise KeyCheckFailed("A quiz question is not an object.")
        question_id = question.get("id")
        prompt = question.get("prompt")
        raw_choices = question.get("choices")
        if (
            not isinstance(question_id, str)
            or not isinstance(prompt, str)
            or not isinstance(raw_choices, list)
            or not raw_choices
        ):
            raise KeyCheckFailed("A quiz question is missing its id, prompt or choices.")
        choices: list[tuple[str, str]] = []
        for choice in raw_choices:
            if not isinstance(choice, dict):
                raise KeyCheckFailed("A quiz choice is not an object.")
            choice_id = choice.get("id")
            text = choice.get("text")
            if not isinstance(choice_id, str) or not isinstance(text, str):
                raise KeyCheckFailed("A quiz choice is missing its id or text.")
            choices.append((choice_id, text))
        questions.append((question_id, prompt, choices))
    return questions


def quiz_prompt(quiz: dict[str, Any]) -> str:
    title = quiz.get("title")
    lines = [f"Quiz: {title if isinstance(title, str) else ''}", ""]
    for question_id, prompt, choices in _visible_questions(quiz):
        lines.append(f"Question id: {question_id}")
        lines.append(prompt)
        lines.append("Choices:")
        lines.extend(f"- {choice_id}: {text}" for choice_id, text in choices)
        lines.append("")
    lines.append("Pick the correct choice id for every question id.")
    return "\n".join(lines)


def key_check_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=key_check_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        model="haiku",
        output_format={"type": "json_schema", "schema": ANSWER_SCHEMA},
        disallowed_tools=DISALLOWED_TOOLS,
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )


def parse_answers(data: object, quiz: dict[str, Any]) -> dict[str, str]:
    """Map question_id -> choice_id, or raise when any answer is unusable."""

    known = {
        question_id: {choice_id for choice_id, _ in choices}
        for question_id, _, choices in _visible_questions(quiz)
    }
    if not isinstance(data, dict):
        raise KeyCheckFailed("The key check returned no answers object.")
    raw = data.get("answers")
    if not isinstance(raw, list):
        raise KeyCheckFailed("The key check returned no answers list.")
    answers: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise KeyCheckFailed("A key check answer is not an object.")
        question_id = item.get("question_id")
        choice_id = item.get("choice_id")
        if not isinstance(question_id, str) or not isinstance(choice_id, str):
            raise KeyCheckFailed("A key check answer is missing its ids.")
        if question_id not in known:
            raise KeyCheckFailed(f"The key check answered unknown question {question_id!r}.")
        if choice_id not in known[question_id]:
            raise KeyCheckFailed(
                f"The key check picked unknown choice {choice_id!r} for {question_id!r}."
            )
        if question_id in answers:
            raise KeyCheckFailed(f"The key check answered {question_id!r} twice.")
        answers[question_id] = choice_id
    missing = [question_id for question_id in known if question_id not in answers]
    if missing:
        raise KeyCheckFailed(f"The key check did not answer {', '.join(missing)}.")
    return answers


class ClaudeKeyCheck:
    """One-shot Haiku pass that answers a quiz without its key."""

    def __init__(
        self,
        work_dir: Path,
        query_fn: QueryFn = query,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn

    async def answer(self, quiz: dict[str, Any]) -> dict[str, str]:
        prompt = quiz_prompt(quiz)
        options = key_check_options(cwd=self.work_dir)
        try:
            messages = await self._collect(prompt, options)
        except ApiKeyPresent:
            raise
        except Exception as exc:
            raise KeyCheckFailed("The key check query failed.") from exc
        for message in messages:
            if isinstance(message, ResultMessage):
                if message.subtype == "success" and message.structured_output:
                    return parse_answers(message.structured_output, quiz)
        raise KeyCheckFailed("The key check ended without structured answers.")

    async def _collect(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> list[object]:
        # The reply waits on this, so it does not queue behind a profile pass.
        return await run_claude_call(lambda: self._gather(prompt, options), TURN_CALLS)

    async def _gather(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> list[object]:
        """Collect the stream, stopping at once if Claude reports an API key."""

        gathered: list[object] = []
        async for message in self._query_fn(prompt=prompt, options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            gathered.append(message)
        return gathered
