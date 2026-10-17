"""The Manim animation writer (experiment, ``feat/manim-experiment``).

The writer turns a brief into a Manim Community scene. It has one tool,
``render_preview``, which renders the scene at low quality, runs the layout
checks, and returns the errors and a picture of the end of every step. The
writer looks at those pictures, fixes what it sees, and then returns its
final code through structured output.

Agent SDK pages used: custom-tools (``@tool``, ``create_sdk_mcp_server``,
image blocks in tool results) and structured-outputs (``output_format``
with tools, ``ResultMessage.structured_output``). ``tools=[]`` removes the
built-in tools; the preview tool is the only one. ``setting_sources=[]``
and ``skills=[]`` keep filesystem settings and skills out.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from polaris.login import reject_api_key_credential
from polaris.manim_render import PREVIEW, RenderResult, render

QueryFn = Callable[..., AsyncIterator[object]]

MAX_PREVIEWS = 5
PREVIEW_TOOL = "mcp__manim__render_preview"

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "A short title for the animation."},
        "description": {
            "type": "string",
            "description": (
                "Two or three plain sentences saying what the whole animation shows, "
                "for someone who cannot see it."
            ),
        },
        "code": {
            "type": "string",
            "description": "The complete Python file, the last version that passed render_preview.",
        },
    },
    "required": ["title", "description", "code"],
    "additionalProperties": False,
}


def manim_writer_prompt(*, previews: int = MAX_PREVIEWS) -> str:
    if previews > 0:
        return MANIM_STYLE_GUIDE.replace("{max_previews}", str(previews))
    # No preview tool: the same guide, with the last part asking for one careful pass.
    guide = MANIM_STYLE_GUIDE[: MANIM_STYLE_GUIDE.index("# How to work")]
    return guide + NO_PREVIEW_WORK


MANIM_STYLE_GUIDE = """\
You write one teaching animation with Manim Community v0.22 for Polaris, a tutor.
A learner watches it step by step on a phone or a laptop. Your job is a correct,
calm, readable explanation that moves, in the style of 3Blue1Brown: few objects,
clear focus, motion that carries the idea.

# The file

```python
from manim import *
from polaris_manim import *

class Explainer(PolarisScene):
    def construct(self):
        self.step("One plain sentence that says what to notice in this step.")
        ...  # self.play(...) / self.wait(...)
        self.step("The next sentence.")
        ...
```

- Exactly one subclass of PolarisScene. Only import manim, polaris_manim, math,
  numpy, random, itertools, functools. No files, no network, no eval or getattr.
- self.step(caption) starts each step; call it before the first animation. Polaris
  shows the caption under the video and reads it aloud, so never draw the caption
  or a title in the scene. A caption is one sentence under 120 characters that
  tells the learner what to look at, in plain words.
- 3 to 7 steps, about 20 to 60 seconds in total. Each step needs at least one
  self.play or self.wait, and ends with self.wait(0.8) to self.wait(1.5) so the
  picture lands before the next step.

# The frame

- 4:3. x runs from -5.33 to 5.33, y from -4 to 4, origin in the centre. Keep every
  object inside x -4.9..4.9 and y -3.6..3.6 (polaris_manim has safe_left(),
  safe_right(), safe_top(), safe_bottom()). Things must stay inside at every
  moment, including the end of every move.
- The background is already dark (BACKGROUND). Do not add a background.
- Plan the layout before writing code: decide which zone each thing lives in
  (for example: diagram on the left two thirds, a readout on the right; or a
  formula band at the top, a graph below). Keep zones apart by 0.4 units or more.
  Place things with arrange(), next_to(..., buff=0.25 or more), to_edge(),
  to_corner(), align_to(), and scale_to_fit_width() for wide groups; avoid magic
  coordinates when a relative placement works.
- Use the frame. The main picture is big: it spans most of the width or most of
  the height, and the picture at the end of each step is balanced around the
  centre, not crowded into the top half with the bottom left empty. A phone shows
  this frame about 320 pixels wide, so small drawings disappear.

# Colour and type (the Polaris design system)

- Colours from polaris_manim: INK (main text and shapes), MUTED (secondary
  text, context), FAINT (axes, grids, guides), ACCENT (the one thing in focus),
  INFO (a second series or a neutral object), POSITIVE (correct, kept, output),
  NEGATIVE (wrong, removed), HIGHLIGHT (a result or a key formula), SURFACE and
  BORDER (filled boxes and their edges). Use no other colours.
- Give each idea one colour and keep it for the whole animation. Only one thing
  is ACCENT at a time. Dim what is no longer the focus (set_opacity(0.35) or
  MUTED) instead of leaving everything bright.
- Text: Text(..., font_size=...) uses the design-system font already. Sizes:
  TITLE_SIZE 52, BODY_SIZE 40, LABEL_SIZE 34; never below MIN_TEXT_SIZE 32, and do
  not .scale() text below that. Fewer than 12 words on screen at once. Short
  labels, not sentences: the caption carries the sentence.
- Strokes 4 to 6 wide for main shapes, 2 to 3 for axes and guides. Dots radius
  0.08 to 0.12.

# Maths: Typst, not LaTeX

LaTeX is not installed: MathTex, Tex, Title, BulletedList, and anything that
builds MathTex (axes.get_axis_labels() and get_graph_label() with a string)
fail. Write maths with MathTypst("...", font_size=44, color=INK), which uses
Typst math syntax:
- x^2, x_1, x_(i+1), a/b or frac(a, b), sqrt(x), root(3, x), abs(x)
- sum_(i=1)^n i, integral_0^1 f(x) dif x, lim_(h -> 0), dot, times, div
- Greek by name: theta, pi, alpha, Delta, omega. Arrows: ->, =>, arrow.r
- Relations: =, !=, <=, >=, approx. Words inside maths go in quotes: "slope".
- Functions sin(x), cos(x), log(x), ln(x), exp(x) are built in.
- Write it all as one expression; colour the whole MathTypst. Do not index into
  its parts.
- MathTypst uses a serif maths font. Use it for real formulas only. Plain
  numbers, words, and simple comparisons such as "17 < 23" are Text, so they
  match the rest of the picture.
Numbers: DecimalNumber and Integer work (Polaris renders them as Text). Axes
with include_numbers=True work; pass axis_config={"font_size": 32} or larger.
Axis labels: make them yourself with Text or MathTypst and next_to() the axis end.

# Motion that teaches

- Introduce: Create for lines and shapes, Write for text and formulas, FadeIn
  with shift for groups, GrowFromCenter for dots, GrowArrow for arrows.
  LaggedStart(..., lag_ratio=0.15) for a row of similar things.
- The key motion of a step gets the time: 3 to 6 seconds, rate_func=smooth, or
  linear for steady motion like a rotation or a point moving at constant speed.
  Creates and fades: 0.8 to 1.5 seconds.
- Linked motion: drive it with a ValueTracker and build dependent objects with
  always_redraw or add_updater, then animate the tracker
  (tracker.animate.set_value(...)). Keep always_redraw bodies small: a Dot, a
  Line, a DecimalNumber; not a whole Axes. Call clear_updaters() or remove a
  redrawn object when it should stop following.
- Changes of form: Transform / ReplacementTransform between two shapes or two
  formulas, TransformMatchingShapes for rearranging the same symbols. Use
  ReplacementTransform when you will refer to the new object later.
- Movement: obj.animate.move_to / shift / rotate, MoveAlongPath, Rotate(obj,
  angle, about_point=...). Swaps: two .animate.move_to with path_arc=PI/2 so they
  pass each other instead of colliding.
- Point at things: Indicate, Circumscribe, Flash, FocusOn, a SurroundingRectangle
  in HIGHLIGHT, or a short Arrow. Then remove or dim the pointer.
- FadeOut what the learner no longer needs before the next idea comes in.

# Common Manim mistakes to avoid

- Lines that run outside their axes: clip a tangent or guide line to the axes
  ranges (compute its end points inside x_range and y_range).
- Labels placed on top of lines or other labels. Put labels beside what they
  name, with next_to and a direction away from crowded parts.
- .animate on an always_redraw object does nothing useful; animate its tracker.
- Text built in a loop with the same position; use VGroup(...).arrange(...).
- Arrow with a short length gets a huge tip: set
  max_tip_length_to_length_ratio=0.2 or a smaller tip_length.
- A Group of non-vector mobjects in VGroup: use Group for mixed types.
- Code(...) for source code: code_string=..., language="python",
  background="window"; keep it under 10 lines and do not scale it down.

# How to work

1. Think through the explanation: what the learner should notice in each step,
   and the layout zones, before writing code.
2. Write the whole file and call render_preview with it.
3. Read the errors and fix every one. Then look hard at every picture: Is
   anything cut off, crowded, overlapping, or hard to read on a small phone? Is
   the focus obvious? Does each step show what its caption says? Is the maths
   correct? Fix what you see and preview again.
4. When a preview has no errors and the pictures look right, return the title,
   the description, and that exact code. You have at most {max_previews} previews.
   Never return code that has not passed a preview.
"""

NO_PREVIEW_WORK = """\
# How to work

1. Think through the explanation: what the learner should notice in each step,
   and the layout zones, before writing code.
2. Work out the size and position of every object in frame units and check by
   hand that nothing leaves the safe area or overlaps text at any moment.
3. Return the title, the description, and the whole file. Polaris renders it;
   if the render fails you get the errors back.
"""


def writer_prompt(
    brief: str, *, failed_code: str | None = None, errors: list[str] | None = None
) -> str:
    lines = ["Brief:", brief.strip()]
    if errors is not None:
        lines += [
            "",
            "Polaris could not use your last animation. Fix every error below, "
            "preview again, and return the whole file.",
            "",
            "Last code:",
            "```python",
            failed_code or "(missing)",
            "```",
            "",
            "Errors:",
            *[f"- {error}" for error in errors],
        ]
    return "\n".join(lines)


def preview_tool_result(result: RenderResult, *, previews_left: int) -> dict[str, Any]:
    """The text and pictures the writer sees after one preview."""

    lines: list[str] = []
    if result.ok:
        lines.append("The preview rendered with no layout errors.")
    else:
        lines.append("The preview found problems. Fix every one:")
        lines += [f"- {error}" for error in result.errors]
    if result.steps:
        lines.append("")
        lines.append(f"Steps ({result.duration_s:.1f} s in total):")
        for index, step in enumerate(result.steps, start=1):
            lines.append(f"{index}. {step.duration_s:.1f} s - {step.caption}")
    if result.frames:
        lines.append("")
        lines.append(
            "For each step below: a strip of small pictures taken after each "
            "animation inside the step (when it has more than one), then the last "
            "frame of the step at 640x480. Check each one before you return."
        )
    lines.append(f"Previews left: {previews_left}.")
    content: list[dict[str, Any]] = [{"type": "text", "text": "\n".join(lines)}]
    for index, frame in enumerate(result.frames, start=1):
        if not frame.is_file():
            continue
        during = result.keyframes.get(index, ())[:-1]
        if during:
            content.append({"type": "text", "text": f"During step {index}:"})
            content.append(_image_block(_strip(during)))
        content.append({"type": "text", "text": f"End of step {index}:"})
        content.append(_image_block(frame.read_bytes()))
    return {"content": content, "is_error": not result.ok}


def _image_block(png: bytes) -> dict[str, Any]:
    return {"type": "image", "data": base64.b64encode(png).decode("ascii"), "mimeType": "image/png"}


def _strip(frames: tuple[Path, ...], *, most: int = 4) -> bytes:
    """Up to ``most`` evenly spread pictures side by side at half size."""

    from PIL import Image

    if len(frames) > most:
        picks = [frames[round(i * (len(frames) - 1) / (most - 1))] for i in range(most)]
    else:
        picks = list(frames)
    images = [Image.open(path).convert("RGB") for path in picks]
    width, height = images[0].width // 2, images[0].height // 2
    gap = 6
    sheet = Image.new("RGB", (len(images) * width + gap * (len(images) - 1), height), "#7a6f62")
    for slot, image in enumerate(images):
        sheet.paste(image.resize((width, height)), (slot * (width + gap), 0))
    out = io.BytesIO()
    sheet.save(out, format="PNG")
    return out.getvalue()


@dataclass
class WriterRun:
    """What one writer call did, for the experiment's report."""

    previews: list[dict[str, Any]] = field(default_factory=list)
    result_subtype: str | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    num_turns: int | None = None


@dataclass(frozen=True)
class ManimDraft:
    title: str
    description: str
    code: str
    run: WriterRun


class ManimWriterFailed(RuntimeError):
    """The writer returned no animation."""


class ClaudeManimWriter:
    """One agent run per draft: write, preview, look, fix, return."""

    engine = "manim"

    def __init__(
        self,
        work_dir: Path,
        query_fn: QueryFn = query,
        *,
        model: str | None = None,
        renderer: Callable[..., RenderResult] = render,
        max_previews: int = MAX_PREVIEWS,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn
        self._model = model
        self._render = renderer
        self._max_previews = max_previews

    async def write(
        self,
        brief: str,
        *,
        failed_code: str | None = None,
        errors: list[str] | None = None,
        preview_dir: Path | None = None,
    ) -> ManimDraft:
        run = WriterRun()
        previews_dir = preview_dir or (self.work_dir / "manim-previews")
        state = {"count": 0}

        @tool(
            "render_preview",
            "Render the whole scene file at 640x480, run the layout checks, and "
            "return the errors and the last frame of every step.",
            {"code": str},
        )
        async def render_preview(args: dict[str, Any]) -> dict[str, Any]:
            if state["count"] >= self._max_previews:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "No previews left. Return the last code that passed.",
                        }
                    ],
                    "is_error": True,
                }
            state["count"] += 1
            out = previews_dir / f"preview-{state['count']}"
            result = await asyncio.to_thread(
                self._render, str(args.get("code", "")), out, quality=PREVIEW
            )
            run.previews.append(
                {
                    "ok": result.ok,
                    "errors": list(result.errors),
                    "duration_s": result.duration_s,
                    "timings": result.timings,
                    "steps": len(result.steps),
                }
            )
            return preview_tool_result(
                result, previews_left=self._max_previews - state["count"]
            )

        server = create_sdk_mcp_server(name="manim", version="1.0.0", tools=[render_preview])
        previewing = self._max_previews > 0
        options = ClaudeAgentOptions(
            system_prompt=manim_writer_prompt(previews=self._max_previews),
            tools=[],
            skills=[],
            setting_sources=[],
            strict_mcp_config=True,
            mcp_servers={"manim": server} if previewing else {},
            allowed_tools=[PREVIEW_TOOL] if previewing else [],
            output_format={"type": "json_schema", "schema": OUTPUT_SCHEMA},
            permission_mode="dontAsk",
            max_turns=4 * self._max_previews + 4,
            cwd=self.work_dir,
            model=self._model,
        )
        prompt = writer_prompt(brief, failed_code=failed_code, errors=errors)
        data: dict[str, Any] | None = None
        async for message in self._query_fn(prompt=prompt, options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if isinstance(message, ResultMessage):
                run.result_subtype = message.subtype
                run.cost_usd = message.total_cost_usd
                run.duration_ms = message.duration_ms
                run.num_turns = message.num_turns
                if (
                    message.subtype == "success"
                    and isinstance(message.structured_output, dict)
                    and message.structured_output
                ):
                    data = message.structured_output
        if data is None or not str(data.get("code", "")).strip():
            raise ManimWriterFailed(
                f"The Manim writer returned no code ({run.result_subtype})."
            )
        return ManimDraft(
            title=str(data.get("title", "")).strip() or "Animation",
            description=str(data.get("description", "")).strip(),
            code=str(data["code"]),
            run=run,
        )


def draft_summary(draft: ManimDraft) -> str:
    return json.dumps(
        {"title": draft.title, "previews": draft.run.previews, "cost": draft.run.cost_usd}
    )

