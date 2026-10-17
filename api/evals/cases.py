"""The eval cases. Each names the rules it checks (docs/features/).

Code checks come first. A judged check is used only where a code check
cannot work, and the report labels it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from polaris.animation_format import check_animation
from polaris.animation_writer import ClaudeAnimationWriter
from polaris.models import FactChange, Profile, Turn
from polaris.profile import apply_changes, load_profile
from polaris.profile_pass import ClaudeProfilePass
from polaris.quiz import InvalidQuiz, normalize_spec
from polaris.teaching import (
    CREATE_QUIZ_TOOL,
    DRAW_WHITEBOARD_TOOL,
    START_ANIMATION_JOB_TOOL,
)
from polaris.whiteboard import step_marker

from evals.harness import (
    CallLog,
    Case,
    Sample,
    TeachingRun,
    TurnRecord,
    judge,
    recording_query,
)

# --- profiles ------------------------------------------------------------------

STRUGGLE_FACTS = (
    "Wants short explanations with one everyday example before any formula.",
    "Can already do basic arithmetic and solve one-step equations.",
    "Struggles with fractions: gets lost when a fraction sits inside a formula.",
)

VISUAL_FACTS = (
    "Learns best from diagrams that show how parts connect.",
    "Knows high-school algebra and what a computer network is.",
    "Struggles to keep the order of steps in a process straight.",
)

# --- shared checks -------------------------------------------------------------

_ASKS_HOW_TAUGHT = re.compile(
    r"\b(learn|taught|teach|explain|prefer|style|example|visual|step[- ]by[- ]step)", re.I
)
_ASKS_CAN_DO = re.compile(
    r"\b(already|know|background|familiar|comfortable|experience|level|studied|covered)", re.I
)
_ASKS_STRUGGLE = re.compile(
    r"\b(struggl\w*|hard|difficult|tricky|stuck|trip\w* (you )?up|confus\w*|challeng\w*)", re.I
)
# The derivative of x^2 is 2x. Naming "power rule" in a question is not teaching.
_DERIVATIVE_ANSWER = re.compile(r"(\b2\s*[x·*⋅]|\b2x\b|n\s*x\^?\(?n\s*-\s*1)", re.I)
_PROFILE_QUESTION = re.compile(
    r"how (do|would) you (like|prefer|want) to (learn|be taught)|"
    r"what can you already do|where do you (usually )?struggle",
    re.I,
)


def _all_calls(turn: TurnRecord) -> list[str]:
    return [call.name for call in turn.calls]


def _check_asks_and_does_not_teach(sample: Sample, turn: TurnRecord) -> None:
    reply = turn.reply
    names = _all_calls(turn)
    sample.check("calls no tools", not names, ", ".join(names))
    sample.check("reply asks a question", "?" in reply)
    groups = {
        "how taught": bool(_ASKS_HOW_TAUGHT.search(reply)),
        "can already do": bool(_ASKS_CAN_DO.search(reply)),
        "struggles": bool(_ASKS_STRUGGLE.search(reply)),
    }
    missing = [name for name, hit in groups.items() if not hit]
    sample.check(
        "asks for all three missing parts (keyword)",
        not missing,
        "missing: " + ", ".join(missing) if missing else "",
    )
    found = _DERIVATIVE_ANSWER.search(reply)
    sample.check(
        "does not teach the topic (no derivative answer)",
        found is None,
        f"found {found.group(0)!r}" if found else "",
    )


def _whiteboard_checks(sample: Sample, turn: TurnRecord) -> list[dict[str, Any]]:
    """WB-05 and WB-06 for one turn. Returns the stored whiteboards."""

    calls = turn.calls_named(DRAW_WHITEBOARD_TOOL)
    boards = turn.artifacts_of("whiteboard")
    sample.check("called draw_whiteboard", bool(calls), f"{len(calls)} call(s)")
    if calls:
        first = calls[0]
        sample.check(
            "WB-05 first drawing passes check_drawing",
            first.is_error is False,
            "" if first.is_error is False else first.result[:600],
        )
    else:
        sample.check("WB-05 first drawing passes check_drawing", None, "no drawing")
    sample.check("whiteboard stored", bool(boards), f"{len(boards)} stored")
    if boards:
        missing = [
            step_marker(str(step["id"]))
            for board in boards
            for step in board.get("steps", [])
            if step_marker(str(step["id"])) not in turn.reply
        ]
        total = sum(len(board.get("steps", [])) for board in boards)
        sample.check(
            "WB-06 every step marker is in the reply",
            not missing,
            f"{total - len(missing)}/{total} markers; missing {missing}" if missing else f"{total}/{total} markers",
        )
    else:
        sample.check("WB-06 every step marker is in the reply", None, "no whiteboard")
    return boards


def _elements(boards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        element
        for board in boards
        for step in board.get("steps", [])
        for element in step.get("elements", [])
    ]


def _note_turn(sample: Sample, message: str, turn: TurnRecord) -> None:
    sample.note("learner", message)
    sample.note("reply", turn.reply)
    for call in turn.calls:
        status = "error" if call.is_error else "ok"
        sample.note(f"tool {call.name} ({status}) input", json.dumps(call.input)[:1500])
        sample.note(f"tool {call.name} ({status}) result", call.result[:600])


# --- PR-02 ---------------------------------------------------------------------

_PR02_MESSAGE = "Explain the derivative of x^2."


async def pr02_first(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, ())
    try:
        turn = await run.turn(_PR02_MESSAGE)
        _note_turn(sample, _PR02_MESSAGE, turn)
        _check_asks_and_does_not_teach(sample, turn)
    finally:
        await run.close(sample)


async def pr02_again(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, ())
    second = "I'd rather skip that and just get the answer. What is it?"
    try:
        first = await run.turn(_PR02_MESSAGE)
        _note_turn(sample, _PR02_MESSAGE, first)
        turn = await run.turn(second)
        _note_turn(sample, second, turn)
        _check_asks_and_does_not_teach(sample, turn)
        sample.check(
            "PR-04 profile is still empty",
            not load_profile(data_dir / "profile.json").facts,
        )
    finally:
        await run.close(sample)


# --- PR-01 / PR-03 -------------------------------------------------------------

_SLOPE_MESSAGE = "How do I find the slope of a line through two points?"
_TEACHES_SLOPE = re.compile(r"\b(rise|run|change in|difference|y2|y₂|Δ|delta)", re.I)


async def pr01_struggle(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, STRUGGLE_FACTS)
    try:
        turn = await run.turn(_SLOPE_MESSAGE)
        _note_turn(sample, _SLOPE_MESSAGE, turn)
    finally:
        await run.close(sample)
    reply = turn.reply
    sample.check("teaches slope (keyword)", bool(_TEACHES_SLOPE.search(reply)))
    asked = _PROFILE_QUESTION.search(reply)
    sample.check(
        "does not ask for the profile again",
        asked is None,
        f"found {asked.group(0)!r}" if asked else "",
    )
    verdict, reason = await judge(
        "The learner's profile says they struggle with fractions and get lost when a "
        "fraction sits inside a formula. Does the reply visibly adapt to that struggle, "
        "for example by slowing down at the division, saying the fraction in words, "
        "or working a concrete fraction step by step, rather than treating the "
        "fraction as routine?",
        f"Reply:\n{reply}",
        cwd=data_dir,
        sample=sample,
    )
    sample.check("adapts to the stated fraction struggle", verdict, reason, judged=True)


# --- WB-05 / WB-06 / WB-12 / WB-13 ----------------------------------------------

_HANDSHAKE_MESSAGE = (
    "Draw how the TCP three-way handshake works between a client and a server, step by step."
)
_QUADRATIC_MESSAGE = "Show me the quadratic formula on the whiteboard and explain each part."
_PARABOLA_MESSAGE = (
    "Plot y = x^2 - 4 for x from -3 to 3 on the whiteboard and show where it crosses the x-axis."
)
# The whole quadratic formula: the discriminant and the root or the 2a below it.
# A label that names one part, such as "b² − 4ac: the discriminant", is allowed.
_FORMULA_AS_TEXT = re.compile(r"4\s*a\s*c.*(√|sqrt|2\s*a)|(√|sqrt).*4\s*a\s*c", re.I | re.S)


async def wb_steps(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, VISUAL_FACTS)
    try:
        turn = await run.turn(_HANDSHAKE_MESSAGE)
        _note_turn(sample, _HANDSHAKE_MESSAGE, turn)
    finally:
        await run.close(sample)
    _whiteboard_checks(sample, turn)


async def wb_math(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, VISUAL_FACTS)
    try:
        turn = await run.turn(_QUADRATIC_MESSAGE)
        _note_turn(sample, _QUADRATIC_MESSAGE, turn)
    finally:
        await run.close(sample)
    boards = _whiteboard_checks(sample, turn)
    if not boards:
        sample.check("WB-12 formula is a math element", None, "no whiteboard")
        sample.check("WB-12 whole formula not drawn as text or freehand", None, "no whiteboard")
        return
    elements = _elements(boards)
    sample.check(
        "WB-12 formula is a math element",
        any(element.get("kind") == "math" for element in elements),
    )
    as_text = [
        str(element.get("text"))
        for element in elements
        if element.get("kind") == "text" and _FORMULA_AS_TEXT.search(str(element.get("text", "")))
    ]
    freehand = [element for element in elements if element.get("kind") == "freehand"]
    sample.check(
        "WB-12 whole formula not drawn as text or freehand",
        not as_text and not freehand,
        f"text: {as_text[:3]}; freehand: {len(freehand)}" if as_text or freehand else "",
    )


async def wb_graph(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, VISUAL_FACTS)
    try:
        turn = await run.turn(_PARABOLA_MESSAGE)
        _note_turn(sample, _PARABOLA_MESSAGE, turn)
    finally:
        await run.close(sample)
    boards = _whiteboard_checks(sample, turn)
    if not boards:
        sample.check("WB-13 function is a graph element", None, "no whiteboard")
        sample.check("WB-13 no function drawn as freehand", None, "no whiteboard")
        return
    elements = _elements(boards)
    sample.check(
        "WB-13 function is a graph element",
        any(element.get("kind") == "graph" for element in elements),
    )
    freehand = [element for element in elements if element.get("kind") == "freehand"]
    sample.check(
        "WB-13 no function drawn as freehand",
        not freehand,
        f"{len(freehand)} freehand element(s)" if freehand else "",
    )


# --- QZ-05 / QZ-10 -------------------------------------------------------------

_QUIZ_MESSAGE = "Give me a short 3-question quiz to check I understood photosynthesis."
QUIZ_FACTS = (
    "Wants short explanations with one everyday example.",
    "Has just finished a lesson on photosynthesis: light, water, CO2, glucose, oxygen.",
    "Struggles to tell inputs of a process from its outputs.",
)


async def quiz(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, QUIZ_FACTS)
    try:
        turn = await run.turn(_QUIZ_MESSAGE)
        _note_turn(sample, _QUIZ_MESSAGE, turn)
    finally:
        await run.close(sample)
    calls = turn.calls_named(CREATE_QUIZ_TOOL)
    stored = turn.artifacts_of("quiz")
    sample.check("called create_quiz", bool(calls), f"{len(calls)} call(s)")
    if calls:
        first = calls[0]
        sample.check(
            "QZ-05/QZ-10 first quiz passes the stored-quiz checks",
            first.is_error is False,
            "" if first.is_error is False else first.result[:600],
        )
    else:
        sample.check("QZ-05/QZ-10 first quiz passes the stored-quiz checks", None, "no quiz")
    sample.check("quiz stored", bool(stored), f"{len(stored)} stored")
    accepted = [call for call in calls if call.is_error is False]
    if accepted:
        errors: list[str] = []
        for call in accepted:
            try:
                normalize_spec(call.input)
            except InvalidQuiz as exc:
                errors.append(str(exc))
        sample.check(
            "QZ-05/QZ-10 every stored quiz re-passes normalize_spec",
            not errors,
            "; ".join(errors),
        )
    else:
        sample.check("QZ-05/QZ-10 every stored quiz re-passes normalize_spec", None, "none stored")


# --- AN-04 / AN-05 -------------------------------------------------------------

_ANIMATION_MESSAGE = "Can you animate how a pendulum's speed changes as it swings?"
_CODE_IN_BRIEF = {
    "code fence": re.compile(r"```"),
    "def": re.compile(r"\bdef\s+\w+\s*\("),
    "import": re.compile(r"^\s*(import|from)\s+\w+", re.M),
    "html tag": re.compile(r"</?(svg|div|script|html|canvas|style|circle|line|path)\b", re.I),
    "js function": re.compile(r"\bfunction\s*\w*\s*\(|=>"),
    "declaration": re.compile(r"\b(const|let|var)\s+\w+\s*="),
    "statement end": re.compile(r"\w\)\s*;"),
}
WRITER_BRIEF = (
    "Show a pendulum swinging from one side to the other. "
    "Step 1: the bob is held high on the left and is still. "
    "Step 2: it is released and speeds up as it falls toward the bottom. "
    "Step 3: it is fastest at the bottom. "
    "Step 4: it slows down as it rises on the right and stops for a moment. "
    "A speed bar under the pendulum grows and shrinks with the speed. "
    "Captions name each step in plain words."
)
async def animation_brief(data_dir: Path, sample: Sample) -> None:
    run = TeachingRun(data_dir, STRUGGLE_FACTS)
    try:
        turn = await run.turn(_ANIMATION_MESSAGE)
        _note_turn(sample, _ANIMATION_MESSAGE, turn)
    finally:
        await run.close(sample)
    calls = turn.calls_named(START_ANIMATION_JOB_TOOL)
    sample.check("called start_animation_job", bool(calls), f"{len(calls)} call(s)")
    briefs = [str(call.input.get("brief", "")) for call in calls]
    for brief in briefs:
        sample.note("brief", brief)
    if not briefs:
        sample.check("AN-04 brief contains no code", None, "no brief")
        return
    hits = sorted(
        {name for brief in briefs for name, pattern in _CODE_IN_BRIEF.items() if pattern.search(brief)}
    )
    sample.check("AN-04 brief contains no code", not hits, ", ".join(hits))


async def animation_writer(data_dir: Path, sample: Sample) -> None:
    log = CallLog()
    writer = ClaudeAnimationWriter(data_dir / "claude-work", query_fn=recording_query(log))
    try:
        data = await writer.write(WRITER_BRIEF, failed_data=None, errors=None)
    finally:
        sample.cost_usd += log.cost_usd
        sample.models |= log.models
    sample.note("brief", WRITER_BRIEF)
    sample.note("data (first 1500 chars)", json.dumps(data)[:1500])
    checked = check_animation({**data, "id": "eval"})
    sample.check(
        "AN-10 first animation data passes the check",
        checked.animation is not None,
        "; ".join(checked.errors[:5]),
    )


# --- PR-08 ---------------------------------------------------------------------

STORED_MATH_FACT = "I suck at math"
_MATH_WEAK = re.compile(
    r"\bmath\w*\b.*\b(suck\w*|bad|terrible|awful|weak|struggl\w*|hard|difficult|poor|"
    r"not (good|great|strong)|never been|not my thing|anxi\w*|hate\w*)|"
    r"\b(suck\w*|bad|terrible|awful|weak|struggl\w*|hard|difficult|poor|anxi\w*|hate\w*)\b.*\bmath",
    re.I,
)


def _pr08_turns(statement: str) -> tuple[Turn, ...]:
    return (
        Turn(
            learner_message=f"{statement} Can you go slowly?",
            reply="Of course. We will take it one step at a time. What would you like to work on?",
        ),
        Turn(
            learner_message="What is 3/4 + 1/8?",
            reply=(
                "First give both fractions the same bottom number. 3/4 is the same as 6/8. "
                "Then 6/8 + 1/8 = 7/8."
            ),
        ),
        Turn(
            learner_message="Oh, 7/8. That makes sense now.",
            reply="Exactly. You matched the bottoms, then added the tops.",
        ),
    )


async def _pr08(data_dir: Path, sample: Sample, statement: str) -> None:
    profile = Profile((STORED_MATH_FACT, "Wants short explanations with one example."))
    log = CallLog()
    pass_ = ClaudeProfilePass(data_dir / "claude-work", query_fn=recording_query(log))
    try:
        changes = await pass_.run(turns=_pr08_turns(statement), profile=profile)
    finally:
        sample.cost_usd += log.cost_usd
        sample.models |= log.models
    sample.note("learner statement", statement)
    sample.note("changes", "\n".join(_format_change(change) for change in changes) or "(none)")
    sample.check("pass returned changes", bool(changes), f"{len(changes)} change(s)")
    second_adds = [
        change.fact
        for change in changes
        if change.action == "ADD"
        and (
            change.fact.strip().casefold() == STORED_MATH_FACT.casefold()
            or _MATH_WEAK.search(change.fact)
        )
    ]
    sample.check(
        "PR-08 no second ADD of the math fact",
        not second_adds,
        f"ADD {second_adds}" if second_adds else "",
    )
    on_fact = [
        change.action
        for change in changes
        if _MATH_WEAK.search(change.fact) or _MATH_WEAK.search(change.replaces or "")
    ]
    sample.check(
        "PR-08 repeat is sent as UPDATE or IGNORE",
        bool(on_fact) and all(action in {"UPDATE", "IGNORE"} for action in on_fact),
        ", ".join(on_fact) or "no change names the math fact",
    )
    after = apply_changes(profile, changes)
    math_facts = [fact for fact in after.facts if _MATH_WEAK.search(fact)]
    sample.check(
        "PR-08 profile holds the math fact once",
        len(math_facts) == 1,
        f"{len(math_facts)}: {math_facts}",
    )


def _format_change(change: FactChange) -> str:
    replaces = f" (replaces {change.replaces!r})" if change.replaces else ""
    return f"{change.action} {change.fact!r}{replaces}"


async def pr08_exact(data_dir: Path, sample: Sample) -> None:
    await _pr08(data_dir, sample, "I suck at math.")


async def pr08_reworded(data_dir: Path, sample: Sample) -> None:
    await _pr08(
        data_dir, sample, "Just so you know, math has never been my thing. I'm honestly terrible at it."
    )


CASES: tuple[Case, ...] = (
    Case("pr02-first", "PR-02", "Empty profile: first reply asks, does not teach, calls no tools", pr02_first),
    Case("pr02-again", "PR-02, PR-04", "Empty profile: second reply still asks (decision 0005)", pr02_again),
    Case("pr01-struggle", "PR-01, PR-03", "Filled profile with a struggle: reply adapts to it", pr01_struggle),
    Case("wb-steps", "WB-05, WB-06", "Whiteboard passes check_drawing first try; step markers in reply", wb_steps),
    Case("wb-math", "WB-05, WB-06, WB-12", "Formula uses a math element", wb_math),
    Case("wb-graph", "WB-05, WB-06, WB-13", "Function uses a graph element", wb_graph),
    Case("quiz", "QZ-05, QZ-10", "Created quiz passes the stored-quiz checks", quiz),
    Case("an-brief", "AN-04", "Animation brief contains no code", animation_brief),
    Case("an-writer", "AN-04, AN-10", "Writer's first animation data passes the check", animation_writer),
    Case("pr08-exact", "PR-08", "Pass does not ADD a stored fact again (exact repeat)", pr08_exact),
    Case("pr08-reworded", "PR-08", "Pass does not ADD a stored fact again (reworded repeat)", pr08_reworded),
)
