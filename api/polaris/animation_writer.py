"""The animation writer. It writes the data for one animation job.

It runs outside the learner's turn, so the chat stays usable (AN-01). The
teaching agent only starts the job with a brief. This writer turns the
brief into animation data that Polaris checks and plays; no code it writes
is run (decision 0006, AN-04). On a fix it receives the data that failed
and the check errors (AN-05).

Uses one-shot query() with structured output (streaming-vs-single-mode,
structured-outputs), like the profile pass. The schema comes from the
Pydantic models in animation_format, trimmed to the JSON Schema features
structured output accepts. The backend check stays the authority.
tools=[], setting_sources=[] and skills=[] keep built-in tools, filesystem
settings and skills out. verbatim_prompts sends the brief without @path
expansion. The caller runs this on a loop that can spawn the Claude CLI (a
ProactorEventLoop on Windows).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any, Protocol

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)

from polaris.animation_format import ANIMATION_LIMITS, Animation
from polaris.login import reject_api_key_credential

QueryFn = Callable[..., AsyncIterator[object]]

# Keywords structured output does not accept, or that the check enforces
# with a clearer message. Dropped from the schema sent to the writer.
_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "discriminator",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "maxItems",
        "title",
    }
)

# Filled in by the backend: the job id, the format version, and plotted points.
_BACKEND_FIELDS = frozenset({"id", "version", "plotted"})


def _trim_schema(node: Any, *, top: bool = False) -> Any:
    if isinstance(node, list):
        return [_trim_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYWORDS:
            continue
        if key == "oneOf":
            out["anyOf"] = _trim_schema(value)
        elif key == "minItems":
            out[key] = min(int(value), 1)
        elif key == "properties" and isinstance(value, dict):
            out[key] = {
                name: _trim_schema(prop)
                for name, prop in value.items()
                if name != "plotted" and not (top and name in _BACKEND_FIELDS)
            }
        elif key == "properties":
            out[key] = value
        elif key == "required" and isinstance(value, list):
            out[key] = [
                name
                for name in value
                if name != "plotted" and not (top and name in _BACKEND_FIELDS)
            ]
        elif key == "$defs" and isinstance(value, dict):
            # Draft-07 names this "definitions"; the SDK validates with draft-07.
            out["definitions"] = {name: _trim_schema(item) for name, item in value.items()}
        elif key == "$ref" and isinstance(value, str):
            out[key] = value.replace("#/$defs/", "#/definitions/")
        else:
            out[key] = _trim_schema(value)
    return out


def writer_schema() -> dict[str, Any]:
    """The animation format as structured output accepts it."""

    return _trim_schema(Animation.model_json_schema(), top=True)


def new_cli_loop() -> asyncio.AbstractEventLoop:
    """A loop that can spawn the Claude CLI. On Windows that is a ProactorEventLoop."""

    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


class WriterFailed(RuntimeError):
    """The writer returned no animation data."""


class AnimationWriter(Protocol):
    async def write(
        self,
        brief: str,
        *,
        failed_data: dict[str, Any] | None,
        errors: list[str] | None,
    ) -> dict[str, Any]:
        """Return animation data. A fix receives the data that failed and its errors."""


def animation_writer_prompt() -> str:
    limits = ANIMATION_LIMITS
    return (
        "You write the data for one Polaris animation.\n"
        "An animation is a moving explanation a learner watches step by step. "
        "Polaris draws it and adds the controls, captions, colours, fonts, and "
        "reduced-motion mode. You write data only, never code.\n"
        "\n"
        f"The canvas is {limits.canvas_width:g} units wide and "
        f"{limits.canvas_height:g} high. x grows to the right and y grows down. "
        "Every visible element must stay inside the canvas at every moment.\n"
        "\n"
        "Elements. Every element has an id, a kind, a colour role, and "
        "visible_at_start (false unless it is there before step 1).\n"
        "- rectangle, ellipse: x, y (top-left), width, height, filled.\n"
        "- line, arrow: start and end points.\n"
        "- path: two or more points, closed.\n"
        "- text: x, y, text, size, align. With align start, x, y is the "
        "top-left; middle, the top-centre; end, the top-right. The box is about "
        "0.6 x size wide per character and 1.25 x size high per line.\n"
        "- math: x, y, width, height (your estimate of the rendered box), "
        "latex, size.\n"
        "- code: x, y, language, code, size. The box is about 0.6 x size per "
        "character plus 8 units of padding on each side.\n"
        "- graph: x, y, width, height, x_min, x_max, y_min, y_max, labels, and "
        "series. A series is a function of x (expression, sample_count) or "
        "points. Expressions use + - * / // % **, pi, e, and sin cos tan asin "
        "acos atan sqrt log log10 exp abs floor ceil.\n"
        f"Text, math, and code size is from {limits.min_text_size:g} to "
        f"{limits.max_text_size:g}. Two pieces of text must never overlap.\n"
        "Colour roles: ink (normal), muted (secondary), accent, positive, "
        "negative, highlight. Do not pick colours or fonts.\n"
        "\n"
        f"Steps. At most {limits.max_steps} steps. Each has an id, a caption, "
        f"duration_ms ({limits.min_step_ms} to {limits.max_step_ms}), and actions. "
        f"A caption is one short plain sentence, at most "
        f"{limits.max_caption_length} characters, that explains the step. "
        "Element and step ids share one set and must be unique.\n"
        "Each action names an element and has start_ms and duration_ms; it must "
        "end inside its step. Two actions of the same type on one element must "
        "not overlap in time. The anchor of a box or text is its x, y; of a line "
        "or arrow its start; of a path its first point.\n"
        "- appear, disappear: fade in or out.\n"
        "- move: the anchor goes to `to`.\n"
        "- follow: the anchor goes along path.points, or along x_expression and "
        "y_expression in t from t_min to t_max (sample_count points). Use this "
        "for curved or periodic motion such as a pendulum.\n"
        "- trace: draws a line, arrow, path, or graph series from start to end "
        "(series picks one graph series, numbered from 0).\n"
        "- highlight: changes the colour role; keep keeps it after the step.\n"
        "- count: a text element shows a number counting from from_value to "
        "to_value with decimals places.\n"
        "- scale: resizes around the centre to `to`.\n"
        "\n"
        "Write a title and a description. The description says in two or three "
        "plain sentences what the whole animation shows, for someone who "
        "cannot see it.\n"
        "Leave room: keep labels apart, and keep moving things away from the "
        "edges. Prefer a few clear elements over many small ones.\n"
        "Keep it focused on the brief. Do not teach anything the brief does not ask for.\n"
    )


def writer_prompt(
    brief: str,
    *,
    failed_data: dict[str, Any] | None = None,
    errors: list[str] | None = None,
) -> str:
    lines = ["Brief:", brief.strip()]
    if errors is not None:
        lines += [
            "",
            "Polaris refused your last animation. Fix every error below and "
            "return the whole animation again.",
            "",
            "Last animation:",
            json.dumps(failed_data) if failed_data is not None else "(missing)",
            "",
            "Errors:",
            *[f"- {error}" for error in errors],
        ]
    return "\n".join(lines)


def animation_writer_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=animation_writer_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        output_format={"type": "json_schema", "schema": writer_schema()},
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )


class ClaudeAnimationWriter:
    """One-shot query per run: the first animation, then each fix."""

    def __init__(self, work_dir: Path, query_fn: QueryFn = query) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn

    async def write(
        self,
        brief: str,
        *,
        failed_data: dict[str, Any] | None,
        errors: list[str] | None,
    ) -> dict[str, Any]:
        options = animation_writer_options(cwd=self.work_dir)
        prompt = writer_prompt(brief, failed_data=failed_data, errors=errors)
        data: dict[str, Any] | None = None
        # Read the whole stream so the CLI process ends before this returns.
        async for message in self._query_fn(prompt=prompt, options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if (
                isinstance(message, ResultMessage)
                and message.subtype == "success"
                and isinstance(message.structured_output, dict)
                and message.structured_output
            ):
                data = message.structured_output
        if data is None:
            raise WriterFailed("The animation writer returned no animation.")
        return data
