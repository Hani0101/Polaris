"""Teaching replies through the Claude Agent SDK.

Streaming input (ClaudeSDKClient) is the mode the SDK documents for a chat
UI. include_partial_messages yields StreamEvent text deltas as the reply is
produced. A custom system prompt is the documented choice for a non-coding
agent. tools=[] disables built-in tools. Custom in-process MCP tools (create_quiz,
draw_whiteboard, start_animation_job) are registered so a quiz, a
whiteboard, or an animation job can be stored as an artifact; see
custom-tools.md. start_animation_job takes only a plain-language brief.
Its strict schema rejects any other argument, such as code, before the
handler runs (custom-tools.md, jsonschema step). The job id is the artifact
id from the store. The animation writer writes and runs the code outside
the turn (AN-01), so the teaching agent never sends animation code.
draw_whiteboard takes the Polaris drawing format. Its schema is an open
object so every call reaches check_drawing. A strict schema would be
rejected by the SDK before that check (custom-tools.md, jsonschema step).
setting_sources=[] and skills=[] keep filesystem settings
and skills out. verbatim_prompts sends the assembled profile and earlier
turns without @path expansion.

Profile facts go in the turn prompt only. The system prompt is fixed when
the client connects, so a later change to the profile stays in the turn.
If the stream stops before a ResultMessage, the client is disconnected.
Otherwise the unread tail would be returned as the next reply. interrupt()
does not clear that buffer (Python SDK reference, "Using interrupts").
Disconnecting drops the client instead of interrupting and draining.
On Windows, uvicorn --reload uses SelectorEventLoop, which cannot spawn
the Claude CLI. That client then runs on a ProactorEventLoop in a worker
thread.
"""

import asyncio
import contextlib
import json
import sys
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    CLIConnectionError,
    CLINotFoundError,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    create_sdk_mcp_server,
    tool,
)

from polaris.agent import ReplyResult
from polaris.chat import DuplicateWhiteboard, InvalidDrawing
from polaris.login import ApiKeyPresent, reject_api_key_credential
from polaris.models import Pointing, Profile, Turn
from polaris.quiz import InvalidQuiz
from polaris.whiteboard import (
    DESCRIBED_DRAWING_VERSION,
    GRAPH_DRAWING_VERSION,
    MATH_CODE_DRAWING_VERSION,
    WHITEBOARD_TOOL_LIMITS,
    MissingWhiteboard,
    Whiteboard,
    check_drawing,
    describe_pointed,
    describe_whiteboard,
    element_count,
    pointed_element_errors,
)

_MISSING_PROFILE = (
    "Ask for what the profile is missing: "
    "how they want to be taught, what they can already do, and where they struggle. "
    "Do not teach the topic yet."
)

POLARIS_SERVER_NAME = "polaris"
CREATE_QUIZ_TOOL = "mcp__polaris__create_quiz"
DRAW_WHITEBOARD_TOOL = "mcp__polaris__draw_whiteboard"
START_ANIMATION_JOB_TOOL = "mcp__polaris__start_animation_job"
# Tool-use turns only, per agent-loop.md. Covers the original drawing,
# each fix attempt, one animation job, one quiz, one quiz fix attempt after a
# QZ-10 refusal, and one spare tool turn.
TEACHING_MAX_TURNS = 1 + WHITEBOARD_TOOL_LIMITS.max_fix_attempts + 4
DRAW_WHITEBOARD_DESCRIPTION = (
    "Draw a whiteboard when a picture helps the learner see an idea: "
    "how parts connect, a sequence, a comparison, or a layout. "
    "Do not use this when the explanation is clear as text, and do not use it for a quiz. "
    "The input is one Polaris drawing: version 4, id, description, session_id, steps, and comments. "
    "A drawing that contains math or code is version 5 and still includes a description. "
    "A drawing that contains a graph is version 6 and still includes a description. "
    "description is required on a new whiteboard. It is the text a person who cannot see the drawing reads. "
    "Polaris sets session_id to the open session. "
    "Each step has id, reply_part, and elements. "
    "reply_part must be [[step:<that step's id>]], for example [[step:step-1]] "
    "when the step id is step-1. "
    "Write that same marker in the reply at the start of the part that step explains. "
    "Each element has id, kind, author (agent or learner), position (x, y), "
    "size (width, height), and style (stroke, fill, stroke_width). "
    "kind is rectangle, ellipse, arrow, line, text, freehand, mark, math, code, or graph. "
    "arrow and line also have start and end. text also has text. freehand also has points. "
    "math also has latex, the LaTeX source of one formula. "
    "code also has language, a short name such as python, and code, the source text. "
    "Use a math element for a formula and a code element for code. "
    "Do not draw a formula or code as shapes. "
    "Use a graph element for a function or for data. "
    "Do not draw a function or data as a freehand curve. "
    "A graph has x_label, y_label, x_min, x_max, y_min, y_max, and series. "
    "x_min is less than x_max, and y_min is less than y_max. "
    "Each series is a function with expression and sample_count, or data with points of x and y. "
    "expression may use x and sin, cos, tan, asin, acos, atan, sqrt, log, log10, exp, abs, floor, ceil, pi, and e. "
    "Do not send plotted points. Polaris computes them. "
    "A mark targets one learner element. It has mark (circle, arrow, or note), "
    "author agent, and target_element_id. An arrow mark also has start and end. "
    "A note also has text. "
    "To mark a whiteboard already in the session, send whiteboard_id, step_id, "
    "reply_part [[step:<step_id>]], and marks. Do not send a description, and do not send the learner's elements. "
    "Do not change, move, or delete learner elements or learner comments. "
    "comments is a list. Each comment has id, author, text, and either a position "
    "(x, y) or the element_id of the element it is about. "
    "Use a new id for the whiteboard, every step, every element, every mark, and every comment. "
    "To draw a simpler version of a whiteboard already in the session, send a new "
    "whiteboard with fewer elements, a description, and simplifies set to the "
    "original whiteboard id. Do not change or delete the original."
)
# properties is required so the SDK treats this as JSON Schema. An open
# object lets invalid drawings reach check_drawing instead of failing earlier.
# steps, comments, and marks stay untyped. The model then sends those lists
# as JSON text, and _decode_json_lists reads that text before the check.
DRAW_WHITEBOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": (
                "Required on a new whiteboard. Text for a person who cannot see the drawing."
            ),
        },
        "simplifies": {
            "type": "string",
            "description": (
                "Id of the original whiteboard when this drawing is a simpler version."
            ),
        },
        "whiteboard_id": {
            "type": "string",
            "description": "Id of the stored whiteboard to mark.",
        },
        "step_id": {
            "type": "string",
            "description": "Id of the new step that holds the marks.",
        },
        "reply_part": {
            "type": "string",
            "description": "[[step:<step_id>]]. Write the same marker in the reply.",
        },
        "marks": {
            "type": "array",
            "description": "Circle, arrow, or note marks on learner elements.",
            "items": {"type": "object"},
        },
    },
    "additionalProperties": True,
}
CREATE_QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short title for the quiz."},
        "questions": {
            "type": "array",
            "description": "Questions used to check what the learner understood.",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "choices": {
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["id", "text"],
                            "additionalProperties": False,
                        },
                    },
                    "correct_choice_id": {
                        "type": "string",
                        "description": (
                            "Id of the one correct choice. Stored in the database. "
                            "Never shown to the learner."
                        ),
                    },
                    "explanation": {
                        "type": "string",
                        "description": (
                            "Why the correct choice is right. Shown after grading "
                            "only for questions the learner got wrong."
                        ),
                    },
                },
                "required": [
                    "id",
                    "prompt",
                    "choices",
                    "correct_choice_id",
                    "explanation",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "questions"],
    "additionalProperties": False,
}
ANIMATION_BRIEF_LIMIT = 2000
# additionalProperties false rejects animation code, or any other field,
# before the handler (custom-tools.md, jsonschema step).
START_ANIMATION_JOB_SCHEMA = {
    "type": "object",
    "properties": {
        "brief": {
            "type": "string",
            "minLength": 1,
            "maxLength": ANIMATION_BRIEF_LIMIT,
            "description": (
                "What the animation shows, step by step, in plain words, "
                "pitched for this learner. Not code."
            ),
        }
    },
    "required": ["brief"],
    "additionalProperties": False,
}
START_ANIMATION_JOB_DESCRIPTION = (
    "Start an animation job for this session when a moving explanation "
    "helps the learner: motion, change over time, or a process with steps. "
    "Send a brief that says what the animation shows. Do not send code; "
    "Polaris writes and runs the animation after this turn. The job id comes "
    "back before the animation is ready, and the learner can keep talking. "
    "Polaris sets the session."
)

QuizHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
QuizStore = Callable[[str, dict[str, Any]], dict[str, Any]]
WhiteboardHandler = QuizHandler
AnimationHandler = QuizHandler
AnimationJobStore = Callable[[str, str], dict[str, Any]]


class TeachingFailed(RuntimeError):
    """The agent finished without a successful reply."""


def reply_error_message(exc: BaseException) -> str:
    """Honest learner-facing text when teaching or the Claude CLI fails."""

    if isinstance(exc, CLINotFoundError):
        return (
            "Claude Code was not found. Install Claude Code and stay signed in "
            "with the Claude login on this machine."
        )
    if isinstance(exc, CLIConnectionError):
        cause = exc.__cause__
        if isinstance(cause, NotImplementedError):
            return (
                "Polaris could not start Claude Code because this server cannot "
                "spawn processes. On Windows, --reload uses an event loop that "
                "cannot start the Claude CLI."
            )
        text = str(exc).strip()
        if text and not text.endswith(":"):
            return text
        return (
            "Polaris could not start Claude Code. Confirm Claude Code is installed "
            "and you are signed in with the Claude login on this machine."
        )
    text = str(exc).strip()
    return text or "The reply failed."


def format_facts(profile: Profile) -> str:
    if not profile.facts:
        return "- (no facts yet)"
    return "\n".join(f"- {fact}" for fact in profile.facts)


def teaching_prompt() -> str:
    return (
        "You are Polaris. You teach one learner in a conversation.\n"
        "The profile facts for a reply are in that turn.\n"
        "When the turn lists no facts:\n"
        f"{_MISSING_PROFILE}\n"
        "Do not call create_quiz.\n"
        "Do not call draw_whiteboard.\n"
        "Do not call start_animation_job.\n"
        "When the turn lists facts, teach the topic in the learner message using those facts.\n"
        "If a quiz would help check understanding, call create_quiz.\n"
        "Each question must have exactly one correct choice.\n"
        "Write each wrong choice as a mistake this learner could plausibly make, "
        "such as a common misconception about the idea, not an obviously silly answer.\n"
        "Keep every choice about the same length and form as the correct one.\n"
        "Do not write all of the above or none of the above, and do not repeat a choice.\n"
        "Polaris shuffles the choices. Do not label them with letters, and in an explanation "
        "name a choice by its text, not by its letter or position.\n"
        "Never put the correct choices in the reply text.\n"
        "Do not grade the learner's choices. Code grades them against the stored key.\n"
        "When a drawing will help the learner see how parts connect, a sequence, "
        "a comparison, or a layout, call draw_whiteboard.\n"
        "A new whiteboard is version 4 and includes a description for a person "
        "who cannot see the drawing.\n"
        "When the drawing contains a formula or code, use a math or code element "
        "and version 5. Do not draw a formula or code as shapes.\n"
        "When the drawing contains a function or data, use a graph element "
        "and version 6. Do not draw a function or data as a freehand curve.\n"
        "Do not call draw_whiteboard when the explanation is clear as text, "
        "and do not call it for a quiz.\n"
        "Set each step's reply_part to [[step:<that step's id>]] "
        "and write that same marker in the reply where the step should appear.\n"
        "To mark a mistake on the learner's drawing, call draw_whiteboard with "
        "whiteboard_id, step_id, reply_part [[step:<that step's id>]], and marks. "
        "A mark is a circle, an arrow, or a note on one learner element. "
        "Do not change, move, or delete what the learner drew.\n"
        "When the learner asks for a simpler version of a whiteboard, "
        "call draw_whiteboard with fewer elements, a description, and simplifies "
        "set to that whiteboard's id. Do not change or delete the original whiteboard.\n"
        "When the learner asks for an animation, or motion over time would "
        "explain the idea better than a still drawing, call start_animation_job once.\n"
        "Its brief says what the animation shows, step by step, for this learner. "
        "Do not put code in the brief.\n"
        "The animation is not ready when the tool returns. Do not say it is ready "
        "and do not describe it as finished. Keep teaching in text meanwhile.\n"
        "Polaris tells the learner how long it may take and how they will be told.\n"
        "Do not store, update, or delete profile facts.\n"
    )


def _pointing_text(
    whiteboards: Sequence[Whiteboard], pointing: Pointing | None
) -> str | None:
    if pointing is None:
        return None
    board = next(
        (item for item in whiteboards if item.id == pointing.whiteboard_id),
        None,
    )
    if board is None:
        return None
    if pointed_element_errors(board, pointing.element_ids):
        return None
    return describe_pointed(board, pointing.element_ids)


def _simpler_instruction(whiteboard: Whiteboard) -> str:
    count = element_count(whiteboard)
    noun = "element" if count == 1 else "elements"
    return (
        f"The learner asked for a simpler version of whiteboard {whiteboard.id}. "
        f"That whiteboard has {count} {noun}. "
        "Call draw_whiteboard with fewer elements, at least one element, "
        "a description, and simplifies set to "
        f"{whiteboard.id}. Do not send an image. "
        "Do not change or delete the original whiteboard."
    )


def turn_prompt(
    profile: Profile,
    learner_message: str,
    prior_turns: Sequence[Turn] = (),
    whiteboards: Sequence[Whiteboard] = (),
    pointing: Pointing | None = None,
    simplify: Whiteboard | None = None,
) -> str:
    lines = [
        "Profile facts, read for this reply:",
        format_facts(profile),
    ]
    if not profile.facts:
        lines.append(_MISSING_PROFILE)
    if prior_turns:
        lines.append("")
        lines.append("Earlier turns:")
        for turn in prior_turns:
            lines.append(f"Learner: {turn.learner_message}")
            earlier = _pointing_text(whiteboards, turn.pointing)
            if earlier is not None:
                lines.append(earlier)
            lines.append(f"Polaris: {turn.reply}")
    if whiteboards:
        lines.append("")
        lines.append("Whiteboards in this session:")
        for whiteboard in whiteboards:
            lines.append(describe_whiteboard(whiteboard))
    current = _pointing_text(whiteboards, pointing)
    if current is not None:
        lines.append("")
        lines.append(current)
    if simplify is not None:
        lines.append("")
        lines.append(_simpler_instruction(simplify))
        lines.append(describe_whiteboard(simplify))
    lines.append("")
    lines.append("Learner message:")
    lines.append(learner_message)
    return "\n".join(lines)


async def _unavailable_quiz(_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": "Quiz storage is not available."}
        ],
        "is_error": True,
    }


async def _unavailable_whiteboard(_args: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": "Whiteboard storage is not available."}
        ],
        "is_error": True,
    }


async def _unavailable_animation(_args: dict[str, Any]) -> dict[str, Any]:
    return _tool_error("Animation jobs are not available.")


def _tool_error(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "is_error": True,
    }


def _limit_message() -> str:
    limit = WHITEBOARD_TOOL_LIMITS.max_fix_attempts
    return (
        f"The drawing fix limit for this turn is {limit}. "
        "This drawing was not shown. Do not call draw_whiteboard again this turn."
    )


def _fix_message(detail: str, failures: int) -> str:
    limit = WHITEBOARD_TOOL_LIMITS.max_fix_attempts
    if failures > limit:
        if detail:
            return f"{detail}\n{_limit_message()}"
        return _limit_message()
    if detail:
        return f"{detail}\nFix the drawing and call draw_whiteboard again."
    return "Fix the drawing and call draw_whiteboard again."


@dataclass(frozen=True)
class WhiteboardSubmission:
    tool_result: dict[str, Any]
    failures: int


WhiteboardStore = Callable[[str, dict[str, Any]], dict[str, Any]]


def submit_whiteboard(
    session_id: str,
    data: object,
    *,
    failures: int,
    store: WhiteboardStore | None,
) -> WhiteboardSubmission:
    """Check a drawing, and store it only when the check passes and fixes remain."""

    limit = WHITEBOARD_TOOL_LIMITS.max_fix_attempts
    if isinstance(data, dict):
        incoming = {**_decode_json_lists(data), "session_id": session_id}
        if _contains_graph(incoming):
            incoming["version"] = GRAPH_DRAWING_VERSION
        elif _contains_math_or_code(incoming):
            incoming["version"] = MATH_CODE_DRAWING_VERSION
        elif "description" in incoming or _names_a_simpler_original(incoming):
            incoming["version"] = DESCRIBED_DRAWING_VERSION
    else:
        incoming = data
    checked = check_drawing(incoming)
    if failures > limit:
        return WhiteboardSubmission(
            tool_result=_tool_error(_limit_message()),
            failures=failures,
        )
    if checked.errors or checked.whiteboard is None:
        updated = failures + 1
        return WhiteboardSubmission(
            tool_result=_tool_error(_fix_message("\n".join(checked.errors), updated)),
            failures=updated,
        )
    if store is None:
        return WhiteboardSubmission(
            tool_result=_tool_error("Whiteboard storage is not available."),
            failures=failures,
        )
    try:
        payload = store(session_id, checked.whiteboard.model_dump(mode="json"))
    except (DuplicateWhiteboard, InvalidDrawing) as exc:
        updated = failures + 1
        detail = "\n".join(exc.errors) if isinstance(exc, InvalidDrawing) else str(exc)
        return WhiteboardSubmission(
            tool_result=_tool_error(_fix_message(detail, updated)),
            failures=updated,
        )
    return WhiteboardSubmission(
        tool_result={
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Whiteboard stored as id {payload['id']}. "
                        "The learner can see the drawing."
                    ),
                }
            ]
        },
        failures=failures,
    )


def _contains_graph(data: dict[str, object]) -> bool:
    return _contains_kind(data, "graph")


def _contains_math_or_code(data: dict[str, object]) -> bool:
    return _contains_kind(data, "math", "code")


def _contains_kind(data: dict[str, object], *kinds: str) -> bool:
    steps = data.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        elements = step.get("elements")
        if not isinstance(elements, list):
            continue
        for element in elements:
            if isinstance(element, dict) and element.get("kind") in kinds:
                return True
    return False


def _names_a_simpler_original(data: dict[str, object]) -> bool:
    simplifies = data.get("simplifies")
    return isinstance(simplifies, str) and bool(simplifies.strip())


_JSON_LIST_FIELDS = ("steps", "comments", "marks")


def _decode_json_lists(data: dict[str, Any]) -> dict[str, Any]:
    """Turn JSON text back into lists. The open tool schema leaves those fields untyped."""

    decoded = dict(data)
    for key in _JSON_LIST_FIELDS:
        value = decoded.get(key)
        if not isinstance(value, str):
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue
        decoded[key] = parsed
    return decoded


def _is_compact_mark(data: object) -> bool:
    return isinstance(data, dict) and "marks" in data and "steps" not in data


def _contains_mark(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    steps = data.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            continue
        elements = step.get("elements")
        if not isinstance(elements, list):
            continue
        for element in elements:
            if isinstance(element, dict) and element.get("kind") == "mark":
                return True
    return False


def _mark_request(data: object) -> bool:
    return _is_compact_mark(data) or _contains_mark(data)


def submit_marks(
    session_id: str,
    data: object,
    *,
    failures: int,
    store: WhiteboardStore | None,
    create: WhiteboardStore | None = None,
) -> WhiteboardSubmission:
    """Check marks against the stored whiteboard, then store them when they pass."""

    limit = WHITEBOARD_TOOL_LIMITS.max_fix_attempts
    if failures > limit:
        return WhiteboardSubmission(
            tool_result=_tool_error(_limit_message()),
            failures=failures,
        )
    if store is None:
        return WhiteboardSubmission(
            tool_result=_tool_error("Whiteboard storage is not available."),
            failures=failures,
        )
    if isinstance(data, dict):
        data = _decode_json_lists(data)
    try:
        payload = store(session_id, data if isinstance(data, dict) else {})
    except MissingWhiteboard:
        if create is not None and _contains_mark(data) and not _is_compact_mark(data):
            return submit_whiteboard(
                session_id,
                data,
                failures=failures,
                store=create,
            )
        updated = failures + 1
        return WhiteboardSubmission(
            tool_result=_tool_error(
                _fix_message("No whiteboard with that id.", updated)
            ),
            failures=updated,
        )
    except (DuplicateWhiteboard, InvalidDrawing) as exc:
        updated = failures + 1
        detail = "\n".join(exc.errors) if isinstance(exc, InvalidDrawing) else str(exc)
        return WhiteboardSubmission(
            tool_result=_tool_error(_fix_message(detail, updated)),
            failures=updated,
        )
    return WhiteboardSubmission(
        tool_result={
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Marks stored on whiteboard {payload['id']}. "
                        "The learner's drawing was not changed."
                    ),
                }
            ]
        },
        failures=failures,
    )


def polaris_mcp_server(
    *,
    create_quiz: QuizHandler,
    draw_whiteboard: WhiteboardHandler,
    start_animation_job: AnimationHandler,
):
    @tool(
        "create_quiz",
        (
            "Store a quiz as an artifact of this session. "
            "Each question must have exactly one correct choice. "
            "Wrong choices are plausible mistakes of about the same length as the "
            "correct one. Polaris shuffles the choices, so do not label them. "
            "The learner never sees the answer key."
        ),
        CREATE_QUIZ_SCHEMA,
    )
    async def create_quiz_tool(args: dict[str, Any]) -> dict[str, Any]:
        return await create_quiz(args)

    @tool(
        "draw_whiteboard",
        DRAW_WHITEBOARD_DESCRIPTION,
        DRAW_WHITEBOARD_SCHEMA,
    )
    async def draw_whiteboard_tool(args: dict[str, Any]) -> dict[str, Any]:
        return await draw_whiteboard(args)

    @tool(
        "start_animation_job",
        START_ANIMATION_JOB_DESCRIPTION,
        START_ANIMATION_JOB_SCHEMA,
    )
    async def start_animation_job_tool(args: dict[str, Any]) -> dict[str, Any]:
        return await start_animation_job(args)

    return create_sdk_mcp_server(
        name=POLARIS_SERVER_NAME,
        version="1.0.0",
        tools=[create_quiz_tool, draw_whiteboard_tool, start_animation_job_tool],
    )


def teaching_options(
    *,
    cwd: Path,
    create_quiz: QuizHandler | None = None,
    draw_whiteboard: WhiteboardHandler | None = None,
    start_animation_job: AnimationHandler | None = None,
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=teaching_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        mcp_servers={
            POLARIS_SERVER_NAME: polaris_mcp_server(
                create_quiz=create_quiz or _unavailable_quiz,
                draw_whiteboard=draw_whiteboard or _unavailable_whiteboard,
                start_animation_job=start_animation_job or _unavailable_animation,
            )
        },
        allowed_tools=[
            CREATE_QUIZ_TOOL,
            DRAW_WHITEBOARD_TOOL,
            START_ANIMATION_JOB_TOOL,
        ],
        include_partial_messages=True,
        verbatim_prompts=True,
        permission_mode="dontAsk",
        max_turns=TEACHING_MAX_TURNS,
        cwd=cwd,
    )


def text_delta(message: StreamEvent) -> str:
    event = message.event
    if event.get("type") != "content_block_delta":
        return ""
    delta = event.get("delta", {})
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return ""
    text = delta.get("text", "")
    return text if isinstance(text, str) else ""


@dataclass
class ReplyWatch:
    """Pull learner-visible text out of one receive_response() stream."""

    sdk_session_id: str | None = None
    reached_result: bool = False

    async def text(self, messages: AsyncIterator[object]) -> AsyncIterator[str]:
        saw_delta = False
        async for message in messages:
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
                continue
            if isinstance(message, StreamEvent):
                chunk = text_delta(message)
                if chunk:
                    saw_delta = True
                    yield chunk
                continue
            if isinstance(message, ResultMessage):
                self.sdk_session_id = message.session_id
                self.reached_result = True
                if message.is_error or message.subtype != "success":
                    detail = message.result or ""
                    if not detail and message.errors:
                        detail = ", ".join(message.errors)
                    raise TeachingFailed(detail or "The reply failed.")
                if not saw_delta and message.result:
                    yield message.result


ClientFactory = Callable[[ClaudeAgentOptions], Any]


def _default_client(options: ClaudeAgentOptions) -> ClaudeSDKClient:
    return ClaudeSDKClient(options)


def _cli_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


def _off_loop_required() -> bool:
    if sys.platform != "win32":
        return False
    loop = asyncio.get_running_loop()
    return not isinstance(loop, asyncio.ProactorEventLoop)


class _OffLoopClient:
    """Run a ClaudeSDKClient on a loop that can spawn the CLI subprocess."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._loop = _cli_loop()
        self._thread = threading.Thread(
            target=self._run, name="polaris-claude-cli", daemon=True
        )
        self._started = threading.Event()
        self._stopped = False

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()
        self._loop.close()

    def _ensure_running(self) -> None:
        if self._thread.is_alive():
            return
        if self._stopped:
            raise RuntimeError("The Claude CLI helper has stopped.")
        self._thread.start()
        self._started.wait()

    async def _call(self, coro: Awaitable[Any]) -> Any:
        self._ensure_running()
        return await asyncio.wrap_future(
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        )

    async def connect(self) -> None:
        await self._call(self._client.connect())

    async def query(
        self, prompt: str, session_id: str = "default"
    ) -> None:
        await self._call(self._client.query(prompt, session_id=session_id))

    async def receive_response(self) -> AsyncIterator[object]:
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        caller = asyncio.get_running_loop()

        async def pump() -> None:
            try:
                async for message in self._client.receive_response():
                    caller.call_soon_threadsafe(queue.put_nowait, ("item", message))
                caller.call_soon_threadsafe(queue.put_nowait, ("end", None))
            except Exception as exc:
                caller.call_soon_threadsafe(queue.put_nowait, ("err", exc))

        self._ensure_running()
        asyncio.run_coroutine_threadsafe(pump(), self._loop)
        while True:
            kind, payload = await queue.get()
            if kind == "item":
                yield payload
            elif kind == "end":
                return
            else:
                raise payload  # type: ignore[misc]

    async def disconnect(self) -> None:
        try:
            if self._thread.is_alive():
                await self._call(self._client.disconnect())
        finally:
            self._stopped = True
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
                if threading.current_thread() is not self._thread:
                    self._thread.join(timeout=5)
            elif not self._loop.is_closed():
                self._loop.close()


class ClaudeTeachingAgent:
    """One ClaudeSDKClient per open Polaris session. Disconnect when the learner leaves."""

    def __init__(
        self,
        work_dir: Path,
        client_factory: ClientFactory = _default_client,
        store_quiz: QuizStore | None = None,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._client_factory = client_factory
        self._clients: dict[str, Any] = {}
        self._store_quiz = store_quiz
        self._store_whiteboard: WhiteboardStore | None = None
        self._mark_whiteboard: WhiteboardStore | None = None
        self._start_animation_job: AnimationJobStore | None = None
        self._drawing_failures: dict[str, int] = {}

    def bind_store(
        self,
        store_quiz: QuizStore,
        store_whiteboard: WhiteboardStore | None = None,
        *,
        mark_whiteboard: WhiteboardStore | None = None,
        start_animation_job: AnimationJobStore | None = None,
    ) -> None:
        """Chat calls this so tools can store an artifact. Does not write the profile."""

        self._store_quiz = store_quiz
        self._store_whiteboard = store_whiteboard
        self._mark_whiteboard = mark_whiteboard
        self._start_animation_job = start_animation_job

    def _handler_for(self, session_id: str) -> QuizHandler:
        async def handle(args: dict[str, Any]) -> dict[str, Any]:
            return await self.handle_create_quiz(session_id, args)

        return handle

    async def handle_create_quiz(
        self, session_id: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        if self._store_quiz is None:
            return await _unavailable_quiz(args)
        try:
            payload = await asyncio.to_thread(self._store_quiz, session_id, args)
        except InvalidQuiz as exc:
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "is_error": True,
            }
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Quiz stored as id {payload['id']}. "
                        "The learner sees the questions. "
                        "Do not mention the correct choices."
                    ),
                }
            ]
        }

    def _whiteboard_handler_for(self, session_id: str) -> WhiteboardHandler:
        async def handle(args: dict[str, Any]) -> dict[str, Any]:
            return await self.handle_draw_whiteboard(session_id, args)

        return handle

    async def handle_draw_whiteboard(
        self, session_id: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        marking = _mark_request(args)
        submit = submit_marks if marking else submit_whiteboard
        kwargs: dict[str, Any] = {
            "failures": self._drawing_failures.get(session_id, 0),
            "store": self._mark_whiteboard if marking else self._store_whiteboard,
        }
        if marking:
            kwargs["create"] = self._store_whiteboard
        submission = await asyncio.to_thread(
            partial(submit, session_id, args, **kwargs)
        )
        self._drawing_failures[session_id] = submission.failures
        return submission.tool_result

    def _animation_handler_for(self, session_id: str) -> AnimationHandler:
        async def handle(args: dict[str, Any]) -> dict[str, Any]:
            return await self.handle_start_animation_job(session_id, args)

        return handle

    async def handle_start_animation_job(
        self, session_id: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Start a job for this session from a brief (AN-01). Only the brief is read."""

        if self._start_animation_job is None:
            return await _unavailable_animation({})
        brief = args.get("brief") if isinstance(args, dict) else None
        if not isinstance(brief, str) or not brief.strip():
            return _tool_error(
                "start_animation_job needs a brief that says what the animation shows."
            )
        try:
            payload = await asyncio.to_thread(
                self._start_animation_job,
                session_id,
                brief.strip()[:ANIMATION_BRIEF_LIMIT],
            )
        except Exception as exc:
            return _tool_error(str(exc) or "The animation job did not start.")
        job_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(job_id, str) or not job_id:
            return _tool_error("The animation job did not return an id.")
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Animation job started as id {job_id}. "
                        "The animation is not ready yet. Polaris writes and runs it "
                        "after this turn and tells the learner when it is ready. "
                        "The learner can keep talking."
                    ),
                }
            ]
        }

    async def reply(
        self,
        *,
        session_id: str,
        profile: Profile,
        learner_message: str,
        prior_turns: Sequence[Turn],
        sdk_session_id: str | None,
        whiteboards: Sequence[Whiteboard] = (),
        pointing: Pointing | None = None,
        simplify: Whiteboard | None = None,
    ) -> AsyncIterator[str | ReplyResult]:
        self._drawing_failures[session_id] = 0
        client, include_transcript = await self._ensure_client(
            session_id,
            sdk_session_id,
            prior_turns,
        )
        prompt = turn_prompt(
            profile,
            learner_message,
            prior_turns if include_transcript else (),
            whiteboards,
            pointing,
            simplify,
        )
        await client.query(prompt)
        watch = ReplyWatch()
        try:
            async for chunk in watch.text(client.receive_response()):
                yield chunk
        finally:
            if not watch.reached_result:
                await self.close_session(session_id)
        if watch.reached_result:
            yield ReplyResult(sdk_session_id=watch.sdk_session_id)

    async def close_session(self, session_id: str) -> None:
        self._drawing_failures.pop(session_id, None)
        client = self._clients.pop(session_id, None)
        if client is not None:
            await client.disconnect()

    async def close_all(self) -> None:
        for session_id in list(self._clients):
            await self.close_session(session_id)

    async def _ensure_client(
        self,
        session_id: str,
        sdk_session_id: str | None,
        prior_turns: Sequence[Turn],
    ) -> tuple[Any, bool]:
        existing = self._clients.get(session_id)
        if existing is not None:
            return existing, False
        options = teaching_options(
            cwd=self.work_dir,
            create_quiz=self._handler_for(session_id),
            draw_whiteboard=self._whiteboard_handler_for(session_id),
            start_animation_job=self._animation_handler_for(session_id),        )
        include_transcript = False
        if sdk_session_id:
            options = replace(options, resume=sdk_session_id)
        elif prior_turns:
            include_transcript = True
        client = self._client_factory(options)
        if isinstance(client, ClaudeSDKClient) and _off_loop_required():
            client = _OffLoopClient(client)
        try:
            await client.connect()
        except Exception:
            with contextlib.suppress(Exception):
                await client.disconnect()
            raise
        self._clients[session_id] = client
        return client, include_transcript
