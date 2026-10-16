"""Animation format, and the check that runs before an animation is stored.

An animation is data that Polaris plays, not code (decision 0006, AN-04).
The writer returns this format. ``check_animation`` refuses data that would
draw badly (AN-10, AN-11), and its errors go back to the writer (AN-05).
Each error names the step and the element.

Math, code, and graph elements reuse the whiteboard's checks (WB-12,
WB-13). Graph series and ``follow`` paths are sampled here, so the browser
never evaluates an expression.

The check plays the animation forward in code. At every action boundary
it works out where each element is, and it checks every sampled point of
a ``follow`` path. A ``move`` between two positions inside the canvas
stays inside, so its end points are enough.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from polaris.whiteboard import (
    AxisLabel,
    CodeSource,
    DataPoint,
    DataSeries,
    ExpressionSource,
    FunctionSeries,
    LanguageName,
    LatexSource,
    SampleCount,
    plot_expression,
)

ANIMATION_FORMAT_VERSION = 1


@dataclass(frozen=True)
class AnimationLimits:
    """Bounds for animation data. Every numeric and text check reads this."""

    canvas_width: float = 400
    canvas_height: float = 300
    min_text_size: float = 22
    max_text_size: float = 64
    max_elements: int = 40
    max_steps: int = 12
    max_actions_per_step: int = 16
    min_step_ms: int = 500
    max_step_ms: int = 15_000
    max_title_length: int = 80
    max_caption_length: int = 160
    max_description_length: int = 1_000
    max_text_length: int = 200
    max_id_length: int = 64
    max_path_points: int = 200
    min_scale: float = 0.25
    max_scale: float = 4
    max_decimals: int = 3
    # Coordinates may sit off the canvas in the data; the canvas rule refuses
    # them only when the element is visible there.
    max_abs_coordinate: float = 10_000
    min_graph_extent: float = 80


ANIMATION_LIMITS = AnimationLimits()

# Estimated glyph width as a share of the font size. Atkinson Hyperlegible
# and its mono face both sit close to this.
TEXT_WIDTH_RATIO = 0.6
TEXT_LINE_HEIGHT = 1.25
CODE_LINE_HEIGHT = 1.4
CODE_PADDING = 8
# Two text boxes may touch by this much before they count as overlapping.
OVERLAP_TOLERANCE = 1.0

ColorRole = Literal["ink", "muted", "accent", "positive", "negative", "highlight"]
GRAPH_SERIES_ROLES: tuple[ColorRole, ...] = ("accent", "positive", "highlight", "negative")


def _identifier(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    if len(text) > ANIMATION_LIMITS.max_id_length:
        raise ValueError("is too long")
    return text


def _coordinate(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    if abs(value) > ANIMATION_LIMITS.max_abs_coordinate:
        raise ValueError("is out of range")
    return value


def _extent(value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError("must be greater than 0")
    if value > ANIMATION_LIMITS.max_abs_coordinate:
        raise ValueError("is out of range")
    return value


def _text_size(value: float) -> float:
    low = ANIMATION_LIMITS.min_text_size
    high = ANIMATION_LIMITS.max_text_size
    if not math.isfinite(value) or value < low or value > high:
        raise ValueError(f"must be from {low:g} to {high:g}")
    return value


def _label_text(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    if len(value) > ANIMATION_LIMITS.max_text_length:
        raise ValueError(f"is longer than {ANIMATION_LIMITS.max_text_length} characters")
    return value


def _title(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    if len(value) > ANIMATION_LIMITS.max_title_length:
        raise ValueError(f"is longer than {ANIMATION_LIMITS.max_title_length} characters")
    return value


def _caption(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    if len(value) > ANIMATION_LIMITS.max_caption_length:
        raise ValueError(
            f"is longer than {ANIMATION_LIMITS.max_caption_length} characters"
        )
    return value


def _description(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    if len(value) > ANIMATION_LIMITS.max_description_length:
        raise ValueError(
            f"is longer than {ANIMATION_LIMITS.max_description_length} characters"
        )
    return value


def _milliseconds(value: int) -> int:
    if value < 0:
        raise ValueError("must be 0 or more")
    if value > ANIMATION_LIMITS.max_step_ms:
        raise ValueError(f"must be at most {ANIMATION_LIMITS.max_step_ms}")
    return value


def _step_milliseconds(value: int) -> int:
    low = ANIMATION_LIMITS.min_step_ms
    high = ANIMATION_LIMITS.max_step_ms
    if value < low or value > high:
        raise ValueError(f"must be from {low} to {high}")
    return value


def _scale(value: float) -> float:
    low = ANIMATION_LIMITS.min_scale
    high = ANIMATION_LIMITS.max_scale
    if not math.isfinite(value) or value < low or value > high:
        raise ValueError(f"must be from {low:g} to {high:g}")
    return value


def _number(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    return value


def _decimals(value: int) -> int:
    if value < 0 or value > ANIMATION_LIMITS.max_decimals:
        raise ValueError(f"must be from 0 to {ANIMATION_LIMITS.max_decimals}")
    return value


Identifier = Annotated[str, AfterValidator(_identifier)]
Coordinate = Annotated[float, AfterValidator(_coordinate)]
Extent = Annotated[float, AfterValidator(_extent)]
TextSize = Annotated[float, AfterValidator(_text_size)]
LabelText = Annotated[str, AfterValidator(_label_text)]
Title = Annotated[str, AfterValidator(_title)]
Caption = Annotated[str, AfterValidator(_caption)]
Description = Annotated[str, AfterValidator(_description)]
Milliseconds = Annotated[int, AfterValidator(_milliseconds)]
StepMilliseconds = Annotated[int, AfterValidator(_step_milliseconds)]
Scale = Annotated[float, AfterValidator(_scale)]
Number = Annotated[float, AfterValidator(_number)]
Decimals = Annotated[int, AfterValidator(_decimals)]


class AnimationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(AnimationModel):
    x: Coordinate
    y: Coordinate


class ElementBase(AnimationModel):
    id: Identifier
    color: ColorRole = "ink"
    visible_at_start: bool = False


class RectangleElement(ElementBase):
    kind: Literal["rectangle"]
    x: Coordinate
    y: Coordinate
    width: Extent
    height: Extent
    filled: bool = False


class EllipseElement(ElementBase):
    kind: Literal["ellipse"]
    x: Coordinate
    y: Coordinate
    width: Extent
    height: Extent
    filled: bool = False


class LineElement(ElementBase):
    kind: Literal["line"]
    start: Point
    end: Point


class ArrowElement(ElementBase):
    kind: Literal["arrow"]
    start: Point
    end: Point


def _path_points(value: list[Point]) -> list[Point]:
    if len(value) > ANIMATION_LIMITS.max_path_points:
        raise ValueError(f"has more than {ANIMATION_LIMITS.max_path_points} points")
    return value


class PathElement(ElementBase):
    kind: Literal["path"]
    points: Annotated[list[Point], Field(min_length=2), AfterValidator(_path_points)]
    closed: bool = False


class TextElement(ElementBase):
    """Text whose top-left (or top-centre, or top-right) is at x, y."""

    kind: Literal["text"]
    x: Coordinate
    y: Coordinate
    text: LabelText
    size: TextSize = 22
    align: Literal["start", "middle", "end"] = "start"


class MathElement(ElementBase):
    """A formula in the box at x, y. The box is the agent's estimate of its size."""

    kind: Literal["math"]
    x: Coordinate
    y: Coordinate
    width: Extent
    height: Extent
    latex: LatexSource
    size: TextSize = 22


class CodeElement(ElementBase):
    """A code block. Its box is worked out from the code and the size."""

    kind: Literal["code"]
    x: Coordinate
    y: Coordinate
    language: LanguageName
    code: CodeSource
    size: TextSize = 22


def _drop_plotted(items: object) -> object:
    if not isinstance(items, list):
        return items
    return [
        {key: value for key, value in item.items() if key != "plotted"}
        if isinstance(item, dict)
        else item
        for item in items
    ]


class GraphElement(ElementBase):
    """Axes in the box at x, y. The backend stores each series' plotted points."""

    kind: Literal["graph"]
    x: Coordinate
    y: Coordinate
    width: Extent
    height: Extent
    x_label: AxisLabel = ""
    y_label: AxisLabel = ""
    x_min: Number
    x_max: Number
    y_min: Number
    y_max: Number
    series: Annotated[list[FunctionSeries | DataSeries], Field(min_length=1, max_length=4)]

    @model_validator(mode="before")
    @classmethod
    def ignore_sent_plotted(cls, data: object) -> object:
        if isinstance(data, dict) and "series" in data:
            return {**data, "series": _drop_plotted(data["series"])}
        return data

    @model_validator(mode="after")
    def plot_the_series(self) -> Self:
        if self.x_min >= self.x_max:
            raise ValueError("x_min must be less than x_max")
        if self.y_min >= self.y_max:
            raise ValueError("y_min must be less than y_max")
        minimum = ANIMATION_LIMITS.min_graph_extent
        if self.width < minimum or self.height < minimum:
            raise ValueError(f"a graph must be at least {minimum:g} by {minimum:g}")
        for series in self.series:
            if isinstance(series, FunctionSeries):
                series.plotted = [
                    DataPoint(x=x_value, y=y_value)
                    for x_value, y_value in plot_expression(
                        series.expression, self.x_min, self.x_max, series.sample_count
                    )
                ]
            else:
                series.plotted = [DataPoint(x=p.x, y=p.y) for p in series.points]
        return self


Element = Annotated[
    RectangleElement
    | EllipseElement
    | LineElement
    | ArrowElement
    | PathElement
    | TextElement
    | MathElement
    | CodeElement
    | GraphElement,
    Field(discriminator="kind"),
]


class ActionBase(AnimationModel):
    element: Identifier
    start_ms: Milliseconds = 0
    duration_ms: Milliseconds = 600


class AppearAction(ActionBase):
    action: Literal["appear"]


class DisappearAction(ActionBase):
    action: Literal["disappear"]


class MoveAction(ActionBase):
    """Moves the element so its anchor lands on ``to``."""

    action: Literal["move"]
    to: Point


class FollowPath(AnimationModel):
    """Anchor positions given as points, or as x(t) and y(t). plotted is computed."""

    points: list[Point] | None = None
    x_expression: ExpressionSource | None = None
    y_expression: ExpressionSource | None = None
    t_min: Number = 0
    t_max: Number = 1
    sample_count: SampleCount = 60
    plotted: list[Point] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def ignore_sent_plotted(cls, data: object) -> object:
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if key != "plotted"}
        return data

    @model_validator(mode="after")
    def sample_the_path(self) -> Self:
        has_points = self.points is not None
        has_expressions = self.x_expression is not None or self.y_expression is not None
        if has_points == has_expressions:
            raise ValueError("needs points, or x_expression and y_expression")
        if self.points is not None:
            if len(self.points) < 2:
                raise ValueError("needs at least 2 points")
            _path_points(self.points)
            self.plotted = [Point(x=p.x, y=p.y) for p in self.points]
            return self
        if self.x_expression is None or self.y_expression is None:
            raise ValueError("needs both x_expression and y_expression")
        if self.t_min >= self.t_max:
            raise ValueError("t_min must be less than t_max")
        xs = plot_expression(
            self.x_expression, self.t_min, self.t_max, self.sample_count, variable="t"
        )
        ys = plot_expression(
            self.y_expression, self.t_min, self.t_max, self.sample_count, variable="t"
        )
        try:
            self.plotted = [Point(x=x, y=y) for (_t, x), (_u, y) in zip(xs, ys)]
        except ValidationError:
            raise ValueError("the path goes out of range") from None
        return self


class FollowAction(ActionBase):
    """Moves the element's anchor along a path, starting at its first point."""

    action: Literal["follow"]
    path: FollowPath


class TraceAction(ActionBase):
    """Draws a line, arrow, path, or graph series from its start to its end."""

    action: Literal["trace"]
    series: int | None = None


class HighlightAction(ActionBase):
    """Changes the colour role. Without keep, it changes back when the step ends."""

    action: Literal["highlight"]
    color: ColorRole = "highlight"
    keep: bool = False


class CountAction(ActionBase):
    """Counts a text element's shown number from one value to another."""

    action: Literal["count"]
    from_value: Number
    to_value: Number
    decimals: Decimals = 0


class ScaleAction(ActionBase):
    """Resizes the element around its centre."""

    action: Literal["scale"]
    to: Scale


Action = Annotated[
    AppearAction
    | DisappearAction
    | MoveAction
    | FollowAction
    | TraceAction
    | HighlightAction
    | CountAction
    | ScaleAction,
    Field(discriminator="action"),
]


class Step(AnimationModel):
    id: Identifier
    caption: Caption
    duration_ms: StepMilliseconds = 2_000
    actions: Annotated[
        list[Action], Field(max_length=ANIMATION_LIMITS.max_actions_per_step)
    ] = Field(default_factory=list)


class Animation(AnimationModel):
    version: Literal[1] = ANIMATION_FORMAT_VERSION
    id: Identifier
    title: Title
    description: Description
    elements: Annotated[
        list[Element], Field(min_length=1, max_length=ANIMATION_LIMITS.max_elements)
    ]
    steps: Annotated[list[Step], Field(min_length=1, max_length=ANIMATION_LIMITS.max_steps)]


@dataclass(frozen=True)
class AnimationCheck:
    """An animation is present only when errors is empty, so bad data is not passed on."""

    animation: Animation | None
    errors: list[str]


class MissingAnimation(Exception):
    def __init__(self) -> None:
        super().__init__("No animation with that id.")


def check_animation(data: object) -> AnimationCheck:
    """Validate animation data and play it forward. Bad input returns errors."""

    try:
        animation = Animation.model_validate(data)
    except ValidationError as exc:
        return AnimationCheck(animation=None, errors=_validation_messages(exc, data))
    errors = _reference_errors(animation)
    if not errors:
        errors = _playback_errors(animation)
    if errors:
        return AnimationCheck(animation=None, errors=errors)
    return AnimationCheck(animation=animation, errors=[])


# ---------------------------------------------------------------------------
# References and timing


_TRACEABLE = (LineElement, ArrowElement, PathElement, GraphElement)

# Actions on the same channel of one element may not overlap in time.
_CHANNELS: dict[str, str] = {
    "appear": "visibility",
    "disappear": "visibility",
    "move": "position",
    "follow": "position",
    "trace": "trace",
    "highlight": "colour",
    "count": "number",
    "scale": "size",
}

_ACTION_VERBS: dict[str, str] = {
    "appear": "shows",
    "disappear": "hides",
    "move": "moves",
    "follow": "moves",
    "trace": "traces",
    "highlight": "highlights",
    "count": "counts",
    "scale": "scales",
}


def _step_name(index: int, step: Step) -> str:
    return f"step {index + 1} ('{step.id}')"


def _reference_errors(animation: Animation) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for item_id in [e.id for e in animation.elements] + [s.id for s in animation.steps]:
        if item_id in seen and item_id not in duplicates:
            duplicates.append(item_id)
        seen.add(item_id)
    if duplicates:
        quoted = ", ".join(f"'{item}'" for item in duplicates)
        errors.append(f"duplicate ids: {quoted}. Element and step ids share one set.")

    elements = {element.id: element for element in animation.elements}
    for index, step in enumerate(animation.steps):
        name = _step_name(index, step)
        busy: dict[tuple[str, str], list[tuple[int, int]]] = {}
        for number, action in enumerate(step.actions, start=1):
            where = f"{name}, action {number}"
            element = elements.get(action.element)
            if element is None:
                errors.append(f"{where}: unknown element '{action.element}'")
                continue
            end = action.start_ms + action.duration_ms
            if end > step.duration_ms:
                errors.append(
                    f"{where}: ends at {end} ms, after the step ends at "
                    f"{step.duration_ms} ms"
                )
            errors.extend(_kind_errors(where, action, element))
            channel = (action.element, _CHANNELS[action.action])
            for other_start, other_end in busy.get(channel, []):
                if action.start_ms < other_end and other_start < end:
                    errors.append(
                        f"{where}: {_ACTION_VERBS[action.action]} '{action.element}' "
                        "while another action in this step is already doing that"
                    )
                    break
            busy.setdefault(channel, []).append((action.start_ms, end))
    return errors


def _kind_errors(where: str, action: Any, element: Any) -> list[str]:
    if isinstance(action, TraceAction):
        if not isinstance(element, _TRACEABLE):
            return [
                f"{where}: cannot trace '{element.id}', a {element.kind}. "
                "Trace works on a line, arrow, path, or graph."
            ]
        if action.series is not None:
            if not isinstance(element, GraphElement):
                return [f"{where}: series is only for a graph"]
            if action.series < 0 or action.series >= len(element.series):
                return [
                    f"{where}: graph '{element.id}' has no series {action.series}. "
                    f"Series are numbered from 0 to {len(element.series) - 1}."
                ]
    if isinstance(action, CountAction) and not isinstance(element, TextElement):
        return [f"{where}: count needs a text element, and '{element.id}' is a {element.kind}"]
    return []


# ---------------------------------------------------------------------------
# Playing the animation forward


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    def moved(self, dx: float, dy: float) -> Box:
        return Box(self.left + dx, self.top + dy, self.right + dx, self.bottom + dy)

    def scaled(self, factor: float) -> Box:
        cx = (self.left + self.right) / 2
        cy = (self.top + self.bottom) / 2
        half_w = (self.right - self.left) * factor / 2
        half_h = (self.bottom - self.top) * factor / 2
        return Box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    def overlaps(self, other: Box) -> bool:
        width = min(self.right, other.right) - max(self.left, other.left)
        height = min(self.bottom, other.bottom) - max(self.top, other.top)
        return width > OVERLAP_TOLERANCE and height > OVERLAP_TOLERANCE


@dataclass
class ElementState:
    visible: bool
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    text: str | None = None


@dataclass
class _Moment:
    """One checked instant. ``texts`` are the visible text-like boxes."""

    label: str
    boxes: dict[str, Box] = field(default_factory=dict)
    texts: dict[str, Box] = field(default_factory=dict)
    text_sizes: dict[str, float] = field(default_factory=dict)


def anchor(element: Any) -> tuple[float, float]:
    """The point that ``move`` and ``follow`` place."""

    if isinstance(element, (LineElement, ArrowElement)):
        return element.start.x, element.start.y
    if isinstance(element, PathElement):
        return element.points[0].x, element.points[0].y
    return element.x, element.y


def _text_extent(text: str, size: float, line_height: float) -> tuple[float, float]:
    lines = text.split("\n") or [""]
    longest = max(len(line) for line in lines)
    return longest * size * TEXT_WIDTH_RATIO, len(lines) * size * line_height


def base_box(element: Any, text: str | None = None) -> Box:
    """The element's box before any move or scale. Text boxes are estimates."""

    if isinstance(element, TextElement):
        width, height = _text_extent(
            text if text is not None else element.text, element.size, TEXT_LINE_HEIGHT
        )
        if element.align == "middle":
            left = element.x - width / 2
        elif element.align == "end":
            left = element.x - width
        else:
            left = element.x
        return Box(left, element.y, left + width, element.y + height)
    if isinstance(element, CodeElement):
        width, height = _text_extent(element.code, element.size, CODE_LINE_HEIGHT)
        return Box(
            element.x,
            element.y,
            element.x + width + 2 * CODE_PADDING,
            element.y + height + 2 * CODE_PADDING,
        )
    if isinstance(element, (LineElement, ArrowElement)):
        xs = (element.start.x, element.end.x)
        ys = (element.start.y, element.end.y)
        return Box(min(xs), min(ys), max(xs), max(ys))
    if isinstance(element, PathElement):
        xs = [p.x for p in element.points]
        ys = [p.y for p in element.points]
        return Box(min(xs), min(ys), max(xs), max(ys))
    return Box(element.x, element.y, element.x + element.width, element.y + element.height)


def _is_text(element: Any) -> bool:
    return isinstance(element, (TextElement, MathElement, CodeElement))


def _count_text(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def _apply(state: ElementState, element: Any, action: Any, progress: float) -> None:
    """Apply ``action`` at ``progress`` (0 to 1) to the state at its start."""

    if isinstance(action, (AppearAction, TraceAction)):
        state.visible = True
    elif isinstance(action, DisappearAction):
        if progress >= 1:
            state.visible = False
    elif isinstance(action, MoveAction):
        ax, ay = anchor(element)
        target_dx = action.to.x - ax
        target_dy = action.to.y - ay
        state.dx += (target_dx - state.dx) * progress
        state.dy += (target_dy - state.dy) * progress
    elif isinstance(action, FollowAction):
        points = action.path.plotted
        ax, ay = anchor(element)
        index = min(len(points) - 1, round(progress * (len(points) - 1)))
        state.dx = points[index].x - ax
        state.dy = points[index].y - ay
    elif isinstance(action, ScaleAction):
        state.scale += (action.to - state.scale) * progress
    elif isinstance(action, CountAction):
        value = action.from_value + (action.to_value - action.from_value) * progress
        state.text = _count_text(value, action.decimals)


def _box(element: Any, state: ElementState) -> Box:
    return base_box(element, state.text).moved(state.dx, state.dy).scaled(state.scale)


def _snapshot(
    label: str, elements: Sequence[Any], states: dict[str, ElementState]
) -> _Moment:
    moment = _Moment(label=label)
    for element in elements:
        state = states[element.id]
        if not state.visible:
            continue
        box = _box(element, state)
        moment.boxes[element.id] = box
        if _is_text(element):
            moment.texts[element.id] = box
            moment.text_sizes[element.id] = element.size * state.scale
    return moment


def _states_at(
    step: Step,
    elements: dict[str, Any],
    start: dict[str, ElementState],
    time_ms: int,
) -> dict[str, ElementState]:
    states = {key: ElementState(**vars(value)) for key, value in start.items()}
    for action in sorted(step.actions, key=lambda a: a.start_ms):
        if action.start_ms > time_ms:
            continue
        end = action.start_ms + action.duration_ms
        progress = 1.0 if time_ms >= end or action.duration_ms == 0 else (
            (time_ms - action.start_ms) / action.duration_ms
        )
        _apply(states[action.element], elements[action.element], action, progress)
    return states


def _boundary_times(step: Step) -> list[int]:
    times = {0, step.duration_ms}
    for action in step.actions:
        times.add(action.start_ms)
        times.add(action.start_ms + action.duration_ms)
    return sorted(times)


def step_end_states(animation: Animation) -> list[dict[str, ElementState]]:
    """The state of every element at the end of each step, in order."""

    elements = {element.id: element for element in animation.elements}
    states = {
        element.id: ElementState(visible=element.visible_at_start)
        for element in animation.elements
    }
    ends: list[dict[str, ElementState]] = []
    for step in animation.steps:
        states = _states_at(step, elements, states, step.duration_ms)
        ends.append(states)
    return ends


def _playback_errors(animation: Animation) -> list[str]:
    elements = {element.id: element for element in animation.elements}
    order = animation.elements
    states = {
        element.id: ElementState(visible=element.visible_at_start)
        for element in animation.elements
    }
    errors: list[str] = []
    reported: set[tuple[str, str, str]] = set()

    def report(scope: str, key: str, kind: str, message: str) -> None:
        if (scope, key, kind) not in reported:
            reported.add((scope, key, kind))
            errors.append(message)

    _check_moment(_snapshot("at the start", order, states), "start", report)
    for index, step in enumerate(animation.steps):
        name = _step_name(index, step)
        for time_ms in _boundary_times(step):
            moment_states = _states_at(step, elements, states, time_ms)
            moment = _snapshot(name, order, moment_states)
            _check_moment(moment, name, report)
        for action in step.actions:
            if isinstance(action, FollowAction):
                before = _states_at(step, elements, states, action.start_ms)
                _check_follow(name, action, elements[action.element], before, report)
        states = _states_at(step, elements, states, step.duration_ms)
    return errors


def _check_moment(moment: _Moment, scope: str, report: Any) -> None:
    for element_id, box in moment.boxes.items():
        message = _outside_message(box)
        if message is not None:
            report(
                scope,
                element_id,
                "canvas",
                f"{moment.label}: '{element_id}' goes {message}",
            )
    for element_id, size in moment.text_sizes.items():
        if size + 1e-9 < ANIMATION_LIMITS.min_text_size:
            report(
                scope,
                element_id,
                "size",
                f"{moment.label}: text '{element_id}' is {size:g} units high, "
                f"below the minimum of {ANIMATION_LIMITS.min_text_size:g}",
            )
    ids = list(moment.texts)
    for first_index, first in enumerate(ids):
        for second in ids[first_index + 1 :]:
            if moment.texts[first].overlaps(moment.texts[second]):
                report(
                    scope,
                    f"{first}|{second}",
                    "overlap",
                    f"{moment.label}: text '{first}' overlaps text '{second}'",
                )


def _outside_message(box: Box) -> str | None:
    width = ANIMATION_LIMITS.canvas_width
    height = ANIMATION_LIMITS.canvas_height
    if box.left < 0:
        return f"off the canvas past the left edge (left at {box.left:g})"
    if box.right > width:
        return (
            f"off the canvas past the right edge (right at {box.right:g}, "
            f"the canvas is {width:g} wide)"
        )
    if box.top < 0:
        return f"off the canvas past the top edge (top at {box.top:g})"
    if box.bottom > height:
        return (
            f"off the canvas past the bottom edge (bottom at {box.bottom:g}, "
            f"the canvas is {height:g} high)"
        )
    return None


def _check_follow(
    name: str,
    action: FollowAction,
    element: Any,
    states: dict[str, ElementState],
    report: Any,
) -> None:
    ax, ay = anchor(element)
    state = states[element.id]
    for point in action.path.plotted:
        moved = ElementState(
            visible=True, dx=point.x - ax, dy=point.y - ay, scale=state.scale, text=state.text
        )
        message = _outside_message(_box(element, moved))
        if message is not None:
            report(name, element.id, "canvas", f"{name}: '{element.id}' goes {message}")
            return


# ---------------------------------------------------------------------------
# Error messages for data that does not parse


def _validation_messages(exc: ValidationError, data: object) -> list[str]:
    messages: list[str] = []
    for error in exc.errors():
        where = _friendly_location(error["loc"], data)
        detail = _detail(error)
        messages.append(f"{where}: {detail}" if where else detail)
    return messages


def _item_id(data: object, key: str, index: int) -> str | None:
    if not isinstance(data, dict):
        return None
    items = data.get(key)
    if not isinstance(items, list) or index >= len(items):
        return None
    item = items[index]
    if isinstance(item, dict) and isinstance(item.get("id"), str):
        return item["id"]
    return None


# Union branch names Pydantic adds to an error location. They mean nothing to the writer.
_TAGS = {
    "rectangle", "ellipse", "line", "arrow", "path", "text", "math", "code", "graph",
    "appear", "disappear", "move", "follow", "trace", "highlight", "count", "scale",
    "FunctionSeries", "DataSeries",
}


def _friendly_location(location: Iterable[object], data: object) -> str:
    parts = list(location)
    out: list[str] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        following = parts[index + 1] if index + 1 < len(parts) else None
        if part in ("steps", "elements") and isinstance(following, int):
            item_id = _item_id(data, str(part), following)
            noun = "step" if part == "steps" else "element"
            label = f"{noun} {following + 1}"
            if item_id:
                label += f" ('{item_id}')"
            out.append(label)
            index += 2
            continue
        if part == "actions" and isinstance(following, int):
            out.append(f"action {following + 1}")
            index += 2
            continue
        # A union tag follows the list index it belongs to.
        if isinstance(part, str) and part in _TAGS and isinstance(parts[index - 1], int):
            index += 1
            continue
        if isinstance(part, int) and out:
            out[-1] = f"{out[-1]}[{part}]"
        else:
            out.append(str(part))
        index += 1
    return ", ".join(out)


def _detail(error: Any) -> str:
    error_type = error.get("type")
    if error_type == "union_tag_invalid":
        ctx = error.get("ctx") or {}
        return f"unknown kind '{ctx.get('tag')}'. Expected one of {ctx.get('expected_tags')}"
    if error_type == "union_tag_not_found":
        ctx = error.get("ctx") or {}
        return f"missing '{ctx.get('discriminator', 'kind').strip(chr(39))}'"
    if error_type == "missing":
        return "missing field"
    if error_type == "extra_forbidden":
        return "unknown field"
    message = str(error.get("msg", "invalid"))
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


# ---------------------------------------------------------------------------
# Text for later turns and for screen readers


def _element_phrase(element: Any) -> str:
    if isinstance(element, TextElement):
        return f"text '{element.id}' \"{element.text}\""
    if isinstance(element, MathElement):
        return f"math '{element.id}' ${element.latex}$"
    if isinstance(element, CodeElement):
        first = element.code.strip().splitlines()[0] if element.code.strip() else ""
        return f"{element.language} code '{element.id}' starting \"{first}\""
    if isinstance(element, GraphElement):
        functions = [s for s in element.series if isinstance(s, FunctionSeries)]
        if len(element.series) == 1 and functions:
            return (
                f"graph '{element.id}' of y = {functions[0].expression} "
                f"from {element.x_min:g} to {element.x_max:g}"
            )
        return f"graph '{element.id}' with {len(element.series)} series"
    return f"{element.kind} '{element.id}'"


def _join(phrases: list[str]) -> str:
    if len(phrases) <= 2:
        return " and ".join(phrases)
    return ", ".join(phrases[:-1]) + ", and " + phrases[-1]


def describe_step(animation: Animation, index: int) -> str:
    """One step for a prompt: its caption, then what it shows and moves."""

    step = animation.steps[index]
    elements = {element.id: element for element in animation.elements}
    line = f"Step {index + 1} ('{step.id}'): {step.caption.strip()}"
    groups: dict[str, list[str]] = {}
    for action in step.actions:
        verb = _ACTION_VERBS[action.action]
        phrase = _element_phrase(elements[action.element])
        if isinstance(action, CountAction):
            phrase = (
                f"text '{action.element}' from "
                f"{_count_text(action.from_value, action.decimals)} to "
                f"{_count_text(action.to_value, action.decimals)}"
            )
        if phrase not in groups.setdefault(verb, []):
            groups[verb].append(phrase)
    details = [f"{verb.capitalize()} {_join(phrases)}." for verb, phrases in groups.items()]
    if details:
        line += " " + " ".join(details)
    return line


def describe_animation(animation: Animation) -> str:
    """Short text for a later turn: the title, the description, and each step (AN-16)."""

    lines = [f"Animation {animation.id}: {animation.title.strip()}"]
    lines.append(animation.description.strip())
    starting = [e for e in animation.elements if e.visible_at_start]
    if starting:
        lines.append(
            "At the start it shows " + _join([_element_phrase(e) for e in starting]) + "."
        )
    lines.extend(describe_step(animation, index) for index in range(len(animation.steps)))
    return "\n".join(lines)


def readable_animation_description(animation: Animation) -> str:
    """Text a screen reader reads for the whole animation (AN-15)."""

    title = animation.title.strip()
    description = animation.description.strip()
    if not description.endswith((".", "!", "?")):
        description += "."
    count = len(animation.steps)
    noun = "step" if count == 1 else "steps"
    return f"{title}. {description} It has {count} {noun}."
