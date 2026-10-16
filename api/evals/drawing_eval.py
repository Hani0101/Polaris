"""Drawing evals. The layout checks are the score (MVP: evals that pass).

score: read the whiteboards stored in a Polaris data directory and score
the agent's drawings. It does not call the model.

run: send each case in drawing_prompts.json to the teaching agent in a fresh
session, score the drawings it stores, and count the fixes each drawing
needed. It calls Claude through the Claude login on this machine, like the
app does.

Both print one JSON report. The exit status is 1 when the share of clean
drawings is below --min-clean, so a run can gate a change such as a new
layout kind.

    uv run python -m evals.drawing_eval score ../data
    uv run python -m evals.drawing_eval run --min-clean 0.8
"""

import argparse
import asyncio
import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from polaris.layout_check import LAYOUT_PROBLEM_KINDS, layout_problems
from polaris.whiteboard import (
    ArrowElement,
    EllipseElement,
    RectangleElement,
    Whiteboard,
    check_drawing,
)

PROMPTS = Path(__file__).with_name("drawing_prompts.json")


@dataclass
class DrawingScore:
    whiteboard_id: str
    problems: dict[str, int]
    messages: list[str]
    placed: bool
    case: str | None = None
    fixes: int | None = None

    @property
    def clean(self) -> bool:
        return not any(self.problems.values())


@dataclass
class EvalReport:
    drawings: list[DrawingScore] = field(default_factory=list)
    # Cases where the agent drew nothing.
    undrawn: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        count = len(self.drawings)
        totals = {kind: 0 for kind in LAYOUT_PROBLEM_KINDS}
        for drawing in self.drawings:
            for kind, value in drawing.problems.items():
                totals[kind] += value
        fixes = [drawing.fixes for drawing in self.drawings if drawing.fixes is not None]
        return {
            "drawings": count,
            "clean": sum(1 for drawing in self.drawings if drawing.clean),
            "clean_rate": round(self.clean_rate, 3),
            "placed_by_layout": sum(1 for drawing in self.drawings if drawing.placed),
            "problems": totals,
            "mean_fixes": round(sum(fixes) / len(fixes), 3) if fixes else None,
            "undrawn": self.undrawn,
        }

    @property
    def clean_rate(self) -> float:
        if not self.drawings:
            return 0.0
        return sum(1 for drawing in self.drawings if drawing.clean) / len(self.drawings)

    def as_json(self) -> dict[str, object]:
        return {
            "summary": self.summary(),
            "drawings": [
                {
                    "case": drawing.case,
                    "whiteboard_id": drawing.whiteboard_id,
                    "clean": drawing.clean,
                    "placed_by_layout": drawing.placed,
                    "fixes": drawing.fixes,
                    "problems": drawing.problems,
                    "messages": drawing.messages,
                }
                for drawing in self.drawings
            ],
        }


def _placed_by_layout(whiteboard: Whiteboard) -> bool:
    """True when the drawing has labels inside boxes or attached arrows."""

    for step in whiteboard.steps:
        for element in step.elements:
            if isinstance(element, (RectangleElement, EllipseElement)) and element.label:
                return True
            if isinstance(element, ArrowElement) and (
                element.start_element_id or element.end_element_id
            ):
                return True
    return False


def score_whiteboard(
    whiteboard: Whiteboard, case: str | None = None, fixes: int | None = None
) -> DrawingScore:
    problems = layout_problems(whiteboard)
    counts = {kind: 0 for kind in LAYOUT_PROBLEM_KINDS}
    for problem in problems:
        counts[problem.kind] += 1
    return DrawingScore(
        whiteboard_id=whiteboard.id,
        problems=counts,
        messages=[problem.message for problem in problems],
        placed=_placed_by_layout(whiteboard),
        case=case,
        fixes=fixes,
    )


def stored_whiteboards(data_dir: Path) -> Iterable[Whiteboard]:
    """Whiteboards in a Polaris database that still pass check_drawing."""

    connection = sqlite3.connect(data_dir / "polaris.db")
    try:
        rows = connection.execute("SELECT drawing_json FROM whiteboards").fetchall()
    finally:
        connection.close()
    for (raw,) in rows:
        checked = check_drawing(json.loads(raw))
        if checked.whiteboard is not None:
            yield checked.whiteboard


def score_stored(data_dir: Path) -> EvalReport:
    report = EvalReport()
    for whiteboard in stored_whiteboards(data_dir):
        report.drawings.append(score_whiteboard(whiteboard))
    return report


async def run_cases(
    cases_path: Path = PROMPTS, make_agent: Callable[[Path], Any] | None = None
) -> EvalReport:
    """Ask the teaching agent for each case. The real agent needs the Claude login.

    make_agent replaces the real agent in tests.
    """

    from polaris.chat import Chat
    from polaris.login import assert_claude_login
    from polaris.teaching import ClaudeTeachingAgent

    if make_agent is None:
        assert_claude_login()
        make_agent = ClaudeTeachingAgent
    spec = json.loads(cases_path.read_text(encoding="utf-8"))
    report = EvalReport()
    with tempfile.TemporaryDirectory(prefix="polaris-eval-") as raw_dir:
        data_dir = Path(raw_dir)
        (data_dir / "profile.json").write_text(
            json.dumps({"facts": spec["profile"]}), encoding="utf-8"
        )
        agent = make_agent(data_dir / "claude-work")
        chat = Chat(data_dir, agent)
        try:
            for case in spec["cases"]:
                session, _ended = chat.start()
                session_id = str(session["id"])
                drawn: list[dict[str, object]] = []
                async for item in chat.stream_reply(session_id, case["message"]):
                    if isinstance(item, dict) and item.get("kind") == "whiteboard":
                        drawn.append(item)
                fixes = agent.drawing_fix_count(session_id)
                await agent.close_session(session_id)
                if not drawn:
                    report.undrawn.append(case["id"])
                for payload in drawn:
                    stored = {key: value for key, value in payload.items() if key != "kind"}
                    checked = check_drawing(stored)
                    if checked.whiteboard is not None:
                        report.drawings.append(
                            score_whiteboard(checked.whiteboard, case=case["id"], fixes=fixes)
                        )
        finally:
            await agent.close_all()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    score = commands.add_parser("score", help="score stored whiteboards")
    score.add_argument("data_dir", type=Path)
    run = commands.add_parser("run", help="ask the teaching agent, then score")
    run.add_argument("--cases", type=Path, default=PROMPTS)
    for command in (score, run):
        command.add_argument("--min-clean", type=float, default=0.8)
    args = parser.parse_args(argv)
    if args.command == "score":
        report = score_stored(args.data_dir)
    else:
        report = asyncio.run(run_cases(args.cases))
    print(json.dumps(report.as_json(), indent=2))
    return 0 if report.drawings and report.clean_rate >= args.min_clean else 1


if __name__ == "__main__":
    sys.exit(main())
