"""Choose the animation engine for a job: Manim or Lottie.

Manim draws maths and heavy graphs: equations, calculus, geometry, plots of
functions or data on axes, vectors and matrices, and graph theory with
many nodes and edges. Lottie draws everything else: processes, systems,
how something works, stories, timelines, and simple diagrams.

Before the writer starts, a small evaluation reads the learner's request
and the teaching agent's brief and picks one engine. It is a one-shot
query() with structured output (structured-outputs) on a small model, with
no tools, settings, or skills. When that call fails or answers nothing,
a keyword check picks instead, so routing never fails a job.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)

from polaris.login import reject_api_key_credential

QueryFn = Callable[..., AsyncIterator[object]]

MANIM = "manim"
LOTTIE = "lottie"
ENGINES = (MANIM, LOTTIE)

# Small and quick: this call only sorts a request into one of two kinds.
DEFAULT_ROUTER_MODEL = "claude-haiku-5-5"

ROUTE_FILE = "route.json"

ROUTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "engine": {"type": "string", "enum": list(ENGINES)},
        "reason": {
            "type": "string",
            "description": "One short sentence on why this engine fits.",
        },
    },
    "required": ["engine", "reason"],
    "additionalProperties": False,
}

ROUTER_PROMPT = """\
You choose which tool makes one teaching animation for Polaris, a tutor.

- manim: mathematics and heavy graphs. Equations and algebra, calculus
  (limits, derivatives, integrals), geometry and trigonometry, linear algebra
  (vectors, matrices, transformations), probability and statistics worked
  with formulas, proofs, number theory. Plots of functions or data on axes,
  curves, areas under curves, vector fields. Graph theory with many nodes and
  edges (shortest paths, spanning trees, network flow, graph search).
- lottie: everything else. How something works, processes and cycles,
  biology, chemistry, physics and engineering told visually rather than by
  equations, algorithms shown as moving boxes or cards, history and
  timelines, stories, flows between parts of a system, user interfaces,
  simple diagrams, and simple charts with a few bars or slices.

Choose manim when the main thing the learner must see is a formula, a
mathematical object, a plot, or a large graph. Otherwise choose lottie.
Answer with the engine and one short reason.
"""

# Fallback when the evaluation call fails. Words and symbols that mark a
# maths request or a heavy graph; everything else goes to Lottie.
_MATH_WORDS = (
    "algebra", "area under", "asymptote", "calculus", "chain rule",
    "coordinate", "cosine", "derivative", "determinant", "differential",
    "dijkstra", "eigen", "equation", "exponential", "formula", "fourier",
    "fraction", "geometry", "gradient", "graph", "hypotenuse", "integral",
    "integrate", "logarithm", "matrices", "matrix", "minimum spanning",
    "parabola", "plot", "polynomial", "probability", "proof", "prove",
    "pythagor", "quadratic", "radian", "riemann", "shortest path", "sine",
    "slope", "spanning tree", "tangent", "taylor", "theorem", "triangle",
    "trigonometr", "unit circle", "vector", "vertices",
)
_MATH_PATTERN = re.compile(
    r"\b(?:" + r"|".join(re.escape(word) for word in _MATH_WORDS) + r")"
    + r"|[=^²³√∫∑π≤≥]|\b(?:sin|cos|tan|log|ln)\b|\bd[xy]\b|\bf\(x\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Route:
    """The engine chosen for one job, why, and whether the model or the keywords chose."""

    engine: str
    reason: str
    by: str


def keyword_route(brief: str, learner_message: str | None = None) -> Route:
    """Pick an engine from words alone. Used when the evaluation call fails."""

    text = " ".join(part for part in (learner_message, brief) if part)
    found = _MATH_PATTERN.search(text)
    if found:
        return Route(MANIM, f"The request mentions '{found.group(0)}'.", "keywords")
    return Route(LOTTIE, "No maths or heavy graph words in the request.", "keywords")


def router_prompt(brief: str, learner_message: str | None) -> str:
    lines: list[str] = []
    if learner_message and learner_message.strip():
        lines += ["The learner wrote:", learner_message.strip(), ""]
    lines += ["The brief for the animation:", brief.strip()]
    return "\n".join(lines)


def router_options(*, cwd: Path, model: str | None = None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=ROUTER_PROMPT,
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        allowed_tools=[],
        output_format={"type": "json_schema", "schema": ROUTE_SCHEMA},
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        model=model or os.environ.get("POLARIS_ROUTER_MODEL") or DEFAULT_ROUTER_MODEL,
        verbatim_prompts=True,
    )


async def choose_engine(
    brief: str,
    learner_message: str | None = None,
    *,
    cwd: Path,
    query_fn: QueryFn = query,
    model: str | None = None,
) -> Route:
    """Ask a small model which engine fits. Falls back to ``keyword_route``."""

    answer: dict[str, Any] | None = None
    try:
        # Read the whole stream so the CLI process ends before this returns.
        async for message in query_fn(
            prompt=router_prompt(brief, learner_message),
            options=router_options(cwd=cwd, model=model),
        ):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if (
                isinstance(message, ResultMessage)
                and message.subtype == "success"
                and isinstance(message.structured_output, dict)
            ):
                answer = message.structured_output
    except Exception:  # noqa: BLE001 - any failure falls back to the keywords
        answer = None
    if answer is None or answer.get("engine") not in ENGINES:
        return keyword_route(brief, learner_message)
    return Route(str(answer["engine"]), str(answer.get("reason", "")).strip(), "model")


def save_route(work_dir: Path | str, route: Route) -> None:
    """Keep the chosen engine beside the job's files, for debugging and evals.

    The job does not need this file, so a failed write is ignored.
    """

    try:
        (Path(work_dir) / ROUTE_FILE).write_text(
            json.dumps(asdict(route)), encoding="utf-8"
        )
    except OSError:
        pass


class AnimationRouter:
    """Both animation writers, and the evaluation that picks one per job."""

    def __init__(
        self,
        *,
        manim: Any,
        lottie: Any,
        work_dir: Path,
        query_fn: QueryFn = query,
    ) -> None:
        self.manim = manim
        self.lottie = lottie
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn

    async def route(self, brief: str, learner_message: str | None = None) -> Route:
        return await choose_engine(
            brief, learner_message, cwd=self.work_dir, query_fn=self._query_fn
        )

    def writer_for(self, route: Route) -> Any:
        return self.manim if route.engine == MANIM else self.lottie
