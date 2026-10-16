"""Whiteboard drawing format, and the check that runs before it is drawn.

The agent writes this format. A later converter turns it into shapes for the
whiteboard UI.

Math is checked with pylatexenc, a pure-Python LaTeX parser. It is not
KaTeX's parser. A graph expression is plotted only by ``_plot_expression``,
using simpleeval and an explicit name whitelist.
"""

import ast
import math
import operator
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pylatexenc.latexwalker import LatexWalker, LatexWalkerParseError
from simpleeval import FunctionNotDefined, InvalidExpression, NameNotDefined, SimpleEval
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_serializer,
    model_validator,
)

DRAWING_FORMAT_VERSION = 2
MARKED_DRAWING_VERSION = 3
DESCRIBED_DRAWING_VERSION = 4
MATH_CODE_DRAWING_VERSION = 5
GRAPH_DRAWING_VERSION = 6
# Every new drawing is this version. A new kind or field joins it without a
# new version (docs/decisions/0006-one-drawing-format-version.md).
CURRENT_DRAWING_VERSION = 7
SUPPORTED_DRAWING_VERSIONS = frozenset(
    {
        DRAWING_FORMAT_VERSION,
        MARKED_DRAWING_VERSION,
        DESCRIBED_DRAWING_VERSION,
        MATH_CODE_DRAWING_VERSION,
        GRAPH_DRAWING_VERSION,
        CURRENT_DRAWING_VERSION,
    }
)
MARK_DRAWING_VERSIONS = frozenset(
    {
        MARKED_DRAWING_VERSION,
        DESCRIBED_DRAWING_VERSION,
        MATH_CODE_DRAWING_VERSION,
        GRAPH_DRAWING_VERSION,
        CURRENT_DRAWING_VERSION,
    }
)
SIMPLER_DRAWING_VERSIONS = frozenset(
    {
        DESCRIBED_DRAWING_VERSION,
        MATH_CODE_DRAWING_VERSION,
        GRAPH_DRAWING_VERSION,
        CURRENT_DRAWING_VERSION,
    }
)
MATH_CODE_DRAWING_VERSIONS = frozenset(
    {MATH_CODE_DRAWING_VERSION, GRAPH_DRAWING_VERSION, CURRENT_DRAWING_VERSION}
)
GRAPH_DRAWING_VERSIONS = frozenset({GRAPH_DRAWING_VERSION, CURRENT_DRAWING_VERSION})


@dataclass(frozen=True)
class DrawingLimits:
    """Bounds for drawing data. Every numeric and text check reads this."""

    max_text_length: int = 4_000
    max_description_length: int = 1_000
    max_latex_length: int = 2_000
    max_language_length: int = 32
    max_code_length: int = 8_000
    max_series: int = 4
    min_samples: int = 2
    max_samples: int = 201
    max_data_points: int = 201
    max_expression_length: int = 200
    max_axis_label_length: int = 80
    min_coordinate: float = -100_000
    max_coordinate: float = 100_000
    min_size: float = 0
    max_size: float = 100_000


DRAWING_LIMITS = DrawingLimits()


@dataclass(frozen=True)
class WhiteboardToolLimits:
    """How many times one turn still asks the agent to correct a refused drawing.

    The original call is not a fix. After this many failed corrections, the
    next call is not shown. check_drawing does not read this.
    """

    max_fix_attempts: int = 2


WHITEBOARD_TOOL_LIMITS = WhiteboardToolLimits()


def _in_range(value: float, low: float, high: float) -> float:
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    if value < low or value > high:
        raise ValueError("is out of range")
    return value


def _coordinate(value: float) -> float:
    return _in_range(
        value,
        DRAWING_LIMITS.min_coordinate,
        DRAWING_LIMITS.max_coordinate,
    )


def _extent(value: float) -> float:
    return _in_range(value, DRAWING_LIMITS.min_size, DRAWING_LIMITS.max_size)


def _bounded_text(value: str) -> str:
    if len(value) > DRAWING_LIMITS.max_text_length:
        raise ValueError("is too long")
    return value


def _comment_text(value: str) -> str:
    text = _bounded_text(value)
    if not text.strip():
        raise ValueError("must not be blank")
    return text


def _latex_parses(value: str) -> bool:
    """True when pylatexenc can read the whole string. Never raises."""

    try:
        walker = LatexWalker(value, tolerant_parsing=False)
        _nodes, _pos, length = walker.get_latex_nodes()
    except LatexWalkerParseError:
        return False
    except Exception:
        return False
    return length == len(value)


def _latex_source(value: str) -> str:
    if len(value) > DRAWING_LIMITS.max_latex_length:
        raise ValueError("is too long")
    if not value.strip():
        raise ValueError("must not be blank")
    if not _latex_parses(value):
        raise ValueError("is not valid LaTeX")
    return value


def _language_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("must not be blank")
    if len(name) > DRAWING_LIMITS.max_language_length:
        raise ValueError("is too long")
    return name


def _code_source(value: str) -> str:
    if len(value) > DRAWING_LIMITS.max_code_length:
        raise ValueError("is too long")
    if not value.strip():
        raise ValueError("must not be blank")
    return value


def _finite_number(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a finite number")
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    return float(value)


def _axis_label(value: str) -> str:
    limit = min(DRAWING_LIMITS.max_axis_label_length, DRAWING_LIMITS.max_text_length)
    if len(value) > limit:
        raise ValueError("is too long")
    return value


def _expression_source(value: str) -> str:
    if len(value) > DRAWING_LIMITS.max_expression_length:
        raise ValueError("is too long")
    if not value.strip():
        raise ValueError("must not be blank")
    return value


def _sample_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("must be an integer")
    low = DRAWING_LIMITS.min_samples
    high = DRAWING_LIMITS.max_samples
    if value < low or value > high:
        raise ValueError(f"must be from {low} to {high}")
    return value


class _ExpressionRefusal(Exception):
    """A graph expression cannot be plotted. Never escapes ``_plot_expression``."""


# Exponents past this bound can build a huge integer before the result is checked.
_MAX_ABS_EXPONENT = 1_000
_MAX_ABS_BASE = 1_000_000

_GRAPH_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
}

_GRAPH_NODES = (ast.Expr, ast.Name, ast.UnaryOp, ast.BinOp, ast.Call, ast.Constant)


def _real(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _ExpressionRefusal("expression result is not finite")
    if not math.isfinite(value):
        raise _ExpressionRefusal("expression result is not finite")
    return value


def _add(left: object, right: object) -> int | float:
    return operator.add(_real(left), _real(right))


def _sub(left: object, right: object) -> int | float:
    return operator.sub(_real(left), _real(right))


def _mul(left: object, right: object) -> int | float:
    return operator.mul(_real(left), _real(right))


def _div(left: object, right: object) -> int | float:
    return operator.truediv(_real(left), _real(right))


def _floordiv(left: object, right: object) -> int | float:
    return operator.floordiv(_real(left), _real(right))


def _mod(left: object, right: object) -> int | float:
    return operator.mod(_real(left), _real(right))


def _pow(left: object, right: object) -> int | float:
    base = _real(left)
    exponent = _real(right)
    if abs(exponent) > _MAX_ABS_EXPONENT or abs(base) > _MAX_ABS_BASE:
        raise _ExpressionRefusal("expression result is not finite")
    try:
        result = operator.pow(base, exponent)
    except (OverflowError, ZeroDivisionError, ValueError, ArithmeticError):
        raise _ExpressionRefusal("expression result is not finite") from None
    return _real(result)


def _pos(value: object) -> int | float:
    return operator.pos(_real(value))


def _neg(value: object) -> int | float:
    return operator.neg(_real(value))


def _number_constant(node: ast.Constant) -> int | float:
    value = node.value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _ExpressionRefusal("expression is not allowed")
    if not math.isfinite(value):
        raise _ExpressionRefusal("expression result is not finite")
    return value


def _graph_evaluator() -> SimpleEval:
    """simpleeval with arithmetic, ``x``, and the graph function whitelist."""

    evaluator = SimpleEval(
        operators={
            ast.Add: _add,
            ast.Sub: _sub,
            ast.Mult: _mul,
            ast.Div: _div,
            ast.FloorDiv: _floordiv,
            ast.Mod: _mod,
            ast.Pow: _pow,
            ast.UAdd: _pos,
            ast.USub: _neg,
        },
        functions=dict(_GRAPH_FUNCTIONS),
        names={"pi": math.pi, "e": math.e},
    )
    evaluator.nodes = {
        kind: evaluator.nodes[kind] for kind in _GRAPH_NODES if kind in evaluator.nodes
    }
    evaluator.nodes[ast.Constant] = _number_constant
    evaluator.allowed_attrs = {}
    evaluator.ATTR_INDEX_FALLBACK = False
    return evaluator


def _sample_xs(x_min: float, x_max: float, count: int) -> list[float]:
    """``count`` values on the closed interval, including both endpoints."""

    last = count - 1
    span = x_max - x_min
    values = [x_min + span * (index / last) for index in range(count)]
    values[0] = x_min
    values[-1] = x_max
    return values


def _sample_expression(
    expression: str, x_min: float, x_max: float, sample_count: int
) -> list[tuple[float, float]]:
    try:
        ast.parse(expression, mode="eval")
    except SyntaxError:
        raise _ExpressionRefusal("expression does not parse") from None
    evaluator = _graph_evaluator()
    parsed = evaluator.parse(expression)
    points: list[tuple[float, float]] = []
    for x_value in _sample_xs(x_min, x_max, sample_count):
        evaluator.names["x"] = x_value
        raw = evaluator.eval(expression, previously_parsed=parsed)
        points.append((x_value, float(_real(raw))))
    return points


def _plot_expression(
    expression: str, x_min: float, x_max: float, sample_count: int
) -> list[tuple[float, float]]:
    """Plot one function. Raises ValueError and nothing else."""

    try:
        return _sample_expression(expression, x_min, x_max, sample_count)
    except _ExpressionRefusal as refusal:
        raise ValueError(refusal.args[0]) from None
    except NameNotDefined:
        raise ValueError("expression uses an unknown name") from None
    except FunctionNotDefined:
        raise ValueError("expression uses an unknown function") from None
    except SyntaxError:
        raise ValueError("expression does not parse") from None
    except InvalidExpression:
        raise ValueError("expression is not allowed") from None
    except (ZeroDivisionError, OverflowError, ArithmeticError, ValueError):
        raise ValueError("expression result is not finite") from None
    except Exception:
        raise ValueError("expression is not allowed") from None


def _required_id(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    if len(text) > DRAWING_LIMITS.max_text_length:
        raise ValueError("is too long")
    return text


Coordinate = Annotated[float, AfterValidator(_coordinate)]
Extent = Annotated[float, AfterValidator(_extent)]
BoundedText = Annotated[str, AfterValidator(_bounded_text)]
CommentText = Annotated[str, AfterValidator(_comment_text)]
LatexSource = Annotated[str, AfterValidator(_latex_source)]
LanguageName = Annotated[str, AfterValidator(_language_name)]
CodeSource = Annotated[str, AfterValidator(_code_source)]
FiniteNumber = Annotated[float, AfterValidator(_finite_number)]
AxisLabel = Annotated[str, AfterValidator(_axis_label)]
ExpressionSource = Annotated[str, AfterValidator(_expression_source)]
SampleCount = Annotated[int, AfterValidator(_sample_count)]
RequiredId = Annotated[str, AfterValidator(_required_id)]
Author = Literal["agent", "learner"]


class DrawingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(DrawingModel):
    x: Coordinate
    y: Coordinate


class Size(DrawingModel):
    width: Extent
    height: Extent


class Style(DrawingModel):
    """Stroke width uses the same size range as an element's box."""

    stroke: BoundedText
    fill: BoundedText | None = None
    stroke_width: Extent


class ElementBase(DrawingModel):
    id: RequiredId
    author: Author
    position: Point
    size: Size
    style: Style


# Version 7 fields. They are left out of the stored form when absent, so an
# older drawing keeps the exact form it was stored with.
_OPTIONAL_V7_FIELDS = ("label", "start_element_id", "end_element_id")


def _omit_absent_v7_fields(data: object) -> object:
    if isinstance(data, dict):
        for key in _OPTIONAL_V7_FIELDS:
            if key in data and data[key] is None:
                data.pop(key)
    return data


class LabeledBox(ElementBase):
    """A box whose label is drawn inside it, centered. Version 7 only."""

    label: CommentText | None = None

    @model_serializer(mode="wrap")
    def omit_absent_label(self, handler):
        return _omit_absent_v7_fields(handler(self))


class RectangleElement(LabeledBox):
    kind: Literal["rectangle"]


class EllipseElement(LabeledBox):
    kind: Literal["ellipse"]


class ArrowElement(ElementBase):
    """start and end are stored even when an end is attached to an element.

    An attached end names that element. The browser keeps the end on that
    element, and the stored point is where the end meets its edge.
    """

    kind: Literal["arrow"]
    start: Point
    end: Point
    label: CommentText | None = None
    start_element_id: RequiredId | None = None
    end_element_id: RequiredId | None = None

    @model_serializer(mode="wrap")
    def omit_absent_fields(self, handler):
        return _omit_absent_v7_fields(handler(self))


class LineElement(ElementBase):
    kind: Literal["line"]
    start: Point
    end: Point


class TextElement(ElementBase):
    kind: Literal["text"]
    text: BoundedText


class FreehandElement(ElementBase):
    kind: Literal["freehand"]
    points: list[Point] = Field(min_length=1)


class MathElement(ElementBase):
    """A formula stored as LaTeX, drawn as rendered text rather than shapes."""

    kind: Literal["math"]
    latex: LatexSource


class CodeElement(ElementBase):
    """A code block stored as text. language is a short name, not a fixed list."""

    kind: Literal["code"]
    language: LanguageName
    code: CodeSource


class DataPoint(DrawingModel):
    """A number pair on a graph. Finite, and not limited to the position range."""

    x: FiniteNumber
    y: FiniteNumber


def _data_points(value: list[DataPoint]) -> list[DataPoint]:
    if len(value) > DRAWING_LIMITS.max_data_points:
        raise ValueError("too many points")
    return value


class FunctionSeries(DrawingModel):
    """A function sampled on the graph's x range. plotted is computed, not sent."""

    expression: ExpressionSource
    sample_count: SampleCount
    plotted: list[DataPoint] = Field(default_factory=list)


class DataSeries(DrawingModel):
    """Points the agent provided. plotted is those points, unchanged."""

    points: Annotated[list[DataPoint], Field(min_length=1), AfterValidator(_data_points)]
    plotted: list[DataPoint] = Field(default_factory=list)


Series = FunctionSeries | DataSeries


class GraphElement(ElementBase):
    """A graph of a function or of data. The backend stores the plotted points."""

    kind: Literal["graph"]
    author: Literal["agent"]
    x_label: AxisLabel
    y_label: AxisLabel
    x_min: Coordinate
    x_max: Coordinate
    y_min: Coordinate
    y_max: Coordinate
    series: list[Series] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def ignore_sent_plotted(cls, data: object) -> object:
        """The agent does not send plotted points. Any that arrive are dropped."""

        if not isinstance(data, dict):
            return data
        raw_series = data.get("series")
        if not isinstance(raw_series, list):
            return data
        cleaned: list[object] = []
        for item in raw_series:
            if isinstance(item, dict):
                cleaned.append(
                    {key: value for key, value in item.items() if key != "plotted"}
                )
            else:
                cleaned.append(item)
        return {**data, "series": cleaned}

    @model_validator(mode="after")
    def plot_the_series(self) -> Self:
        if len(self.series) > DRAWING_LIMITS.max_series:
            raise ValueError("too many series")
        if self.x_min >= self.x_max:
            raise ValueError("x_min must be less than x_max")
        if self.y_min >= self.y_max:
            raise ValueError("y_min must be less than y_max")
        for series in self.series:
            if isinstance(series, FunctionSeries):
                series.plotted = [
                    DataPoint(x=x_value, y=y_value)
                    for x_value, y_value in _plot_expression(
                        series.expression, self.x_min, self.x_max, series.sample_count
                    )
                ]
            else:
                series.plotted = [
                    DataPoint(x=point.x, y=point.y) for point in series.points
                ]
        return self


class MarkElement(ElementBase):
    """A circle, arrow, or note on one learner element. The learner did not draw it."""

    kind: Literal["mark"]
    author: Literal["agent"]
    mark: Literal["circle", "arrow", "note"]
    target_element_id: RequiredId
    text: CommentText | None = None
    start: Point | None = None
    end: Point | None = None

    @model_validator(mode="after")
    def fields_match_the_mark(self) -> Self:
        if self.mark == "circle":
            if self.text is not None or self.start is not None or self.end is not None:
                raise ValueError("a circle mark has position and size only")
        elif self.mark == "arrow":
            if self.start is None or self.end is None:
                raise ValueError("an arrow mark needs a start and an end")
            if self.text is not None:
                raise ValueError("an arrow mark has no text")
        elif self.text is None:
            raise ValueError("a note needs text")
        elif self.start is not None or self.end is not None:
            raise ValueError("a note has no start or end")
        return self


Element = Annotated[
    RectangleElement
    | EllipseElement
    | ArrowElement
    | LineElement
    | TextElement
    | FreehandElement
    | MathElement
    | CodeElement
    | GraphElement
    | MarkElement,
    Field(discriminator="kind"),
]

_ELEMENT_ADAPTER: TypeAdapter[Element] = TypeAdapter(Element)


def step_marker(step_id: str) -> str:
    """The reply text that unlocks this step. The agent writes the same marker."""

    return f"[[step:{step_id}]]"


class Step(DrawingModel):
    id: RequiredId
    reply_part: BoundedText
    elements: list[Element]

    @model_validator(mode="after")
    def reply_part_names_this_step(self) -> Self:
        expected = step_marker(self.id)
        if self.reply_part != expected:
            raise ValueError(f"reply_part must be {expected}")
        return self


class Comment(DrawingModel):
    """A note on the drawing. It sits at a position, or names one element."""

    id: RequiredId
    author: Author
    text: CommentText
    position: Point | None = None
    element_id: RequiredId | None = None

    @model_validator(mode="after")
    def one_target(self) -> Self:
        has_position = self.position is not None
        has_element = self.element_id is not None
        if has_position == has_element:
            raise ValueError("needs a position or an element id")
        return self


def _duplicate_ids(ids: list[str]) -> str | None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item_id in ids:
        if item_id in seen and item_id not in duplicates:
            duplicates.append(item_id)
        seen.add(item_id)
    if not duplicates:
        return None
    quoted = ", ".join(f"'{item_id}'" for item_id in duplicates)
    return f"duplicate ids: {quoted}"


class Whiteboard(DrawingModel):
    version: int
    id: RequiredId
    session_id: RequiredId
    description: str | None = None
    simplifies: RequiredId | None = None
    steps: list[Step]
    comments: list[Comment] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def version_is_supported(cls, value: int) -> int:
        if value not in SUPPORTED_DRAWING_VERSIONS:
            raise ValueError("must be 2, 3, 4, 5, 6, or 7")
        return value

    @model_serializer(mode="wrap")
    def omit_absent_fields(self, handler):
        data = handler(self)
        if isinstance(data, dict) and data.get("description") is None:
            data.pop("description", None)
        if isinstance(data, dict) and data.get("simplifies") is None:
            data.pop("simplifies", None)
        return data

    @model_validator(mode="after")
    def ids_are_unique(self) -> Self:
        """Step, element, and comment ids share one set, so a part can be pointed at."""

        ids = [self.id]
        element_ids: set[str] = set()
        for step in self.steps:
            ids.append(step.id)
            for element in step.elements:
                ids.append(element.id)
                element_ids.add(element.id)
        ids.extend(comment.id for comment in self.comments)
        message = _duplicate_ids(ids)
        if message is not None:
            raise ValueError(message)
        for index, comment in enumerate(self.comments):
            if comment.element_id is not None and comment.element_id not in element_ids:
                raise ValueError(
                    f"comments[{index}].element_id: unknown element '{comment.element_id}'"
                )
        return self

    @model_validator(mode="after")
    def marks_target_learner_elements(self) -> Self:
        learner_ids = {
            element.id
            for element in _elements(self)
            if element.author == "learner"
        }
        has_mark = False
        for element in _elements(self):
            if not isinstance(element, MarkElement):
                continue
            has_mark = True
            if element.target_element_id not in learner_ids:
                raise ValueError(
                    f"mark '{element.id}' must target a learner element"
                )
        if has_mark and self.version not in MARK_DRAWING_VERSIONS:
            raise ValueError("a whiteboard with marks must be version 3, 4, 5, 6, or 7")
        return self

    @model_validator(mode="after")
    def description_matches_the_version(self) -> Self:
        text = self.description
        if self.version in SIMPLER_DRAWING_VERSIONS:
            if text is None or not text.strip():
                raise ValueError("description is required")
        elif text is not None and not text.strip():
            raise ValueError("description is required")
        if text is not None and len(text) > DRAWING_LIMITS.max_description_length:
            raise ValueError("description is too long")
        return self

    @model_validator(mode="after")
    def simpler_redraw_stays_described(self) -> Self:
        """A simpler redraw names another whiteboard and stays version 4, 5, 6, or 7."""

        if self.simplifies is None:
            return self
        if self.simplifies == self.id:
            raise ValueError("simplifies must name another whiteboard")
        if self.version not in SIMPLER_DRAWING_VERSIONS:
            raise ValueError("a simpler whiteboard must be version 4, 5, 6, or 7")
        return self

    @model_validator(mode="after")
    def math_and_code_are_version_5(self) -> Self:
        if any(isinstance(element, (MathElement, CodeElement)) for element in _elements(self)):
            if self.version not in MATH_CODE_DRAWING_VERSIONS:
                raise ValueError("a whiteboard with math or code must be version 5, 6, or 7")
        return self

    @model_validator(mode="after")
    def graphs_are_version_6(self) -> Self:
        if any(isinstance(element, GraphElement) for element in _elements(self)):
            if self.version not in GRAPH_DRAWING_VERSIONS:
                raise ValueError("a whiteboard with a graph must be version 6 or 7")
        return self

    @model_validator(mode="after")
    def labels_and_attachments_are_version_7(self) -> Self:
        """Labels and attached arrow ends exist on version 7 only, and name real parts."""

        elements = _elements(self)
        uses_v7 = any(
            getattr(element, field, None) is not None
            for element in elements
            for field in _OPTIONAL_V7_FIELDS
        )
        if uses_v7 and self.version != CURRENT_DRAWING_VERSION:
            raise ValueError("labels and attached arrows need version 7")
        targets = {
            element.id
            for element in elements
            if not isinstance(element, (ArrowElement, LineElement, MarkElement))
        }
        for element in elements:
            if not isinstance(element, ArrowElement):
                continue
            for field in ("start_element_id", "end_element_id"):
                target = getattr(element, field)
                if target is None:
                    continue
                if target not in targets:
                    raise ValueError(
                        f"arrow '{element.id}' {field} must name a box, text, or "
                        f"other shape on this whiteboard, not '{target}'"
                    )
        return self


class MissingWhiteboard(Exception):
    def __init__(self) -> None:
        super().__init__("No whiteboard with that id.")


class WhiteboardUnreadable(Exception):
    def __init__(self) -> None:
        super().__init__("That whiteboard could not be opened.")


@dataclass(frozen=True)
class DrawingCheck:
    """A whiteboard is present only when errors is empty, so bad data is not passed on."""

    whiteboard: Whiteboard | None
    errors: list[str]


def check_drawing(data: object) -> DrawingCheck:
    """Validate drawing data. Bad input returns errors and does not raise."""

    try:
        whiteboard = Whiteboard.model_validate(data)
    except ValidationError as exc:
        return DrawingCheck(whiteboard=None, errors=_error_messages(exc))
    return DrawingCheck(whiteboard=whiteboard, errors=[])


def _elements(whiteboard: Whiteboard) -> list[Element]:
    return [element for step in whiteboard.steps for element in step.elements]


def _step_id(whiteboard: Whiteboard, element_id: str) -> str | None:
    for step in whiteboard.steps:
        if any(element.id == element_id for element in step.elements):
            return step.id
    return None


def _keep_stored_description(stored: Whiteboard, incoming: object) -> object:
    """A learner save cannot replace the description, the version, or simplifies."""

    if not isinstance(incoming, dict):
        return incoming
    payload = dict(incoming)
    payload["version"] = stored.version
    if stored.description is None:
        payload.pop("description", None)
    else:
        payload["description"] = stored.description
    if stored.simplifies is None:
        payload.pop("simplifies", None)
    else:
        payload["simplifies"] = stored.simplifies
    return payload


def check_learner_drawing(stored: Whiteboard, incoming: object) -> DrawingCheck:
    """Check a learner's copy. Agent elements and agent comments stay as stored."""

    checked = check_drawing(_keep_stored_description(stored, incoming))
    if checked.whiteboard is None:
        return checked
    updated = checked.whiteboard
    errors = _learner_change_errors(stored, updated)
    if errors:
        return DrawingCheck(whiteboard=None, errors=errors)
    return checked


def apply_marks(stored: Whiteboard, incoming: object) -> DrawingCheck:
    """Append agent marks. Learner elements and comments stay as stored.

    A full drawing is refused when a learner element or learner comment is
    missing, changed, added, or reordered. Missing learner elements are deletions.
    The mark action (whiteboard id, step marker, and marks) copies the stored
    learner drawing and only appends a new step.
    """

    if not isinstance(incoming, dict):
        return DrawingCheck(whiteboard=None, errors=["marks must be an object"])
    if "steps" in incoming:
        return _apply_drawing_marks(stored, incoming)
    return _apply_mark_action(stored, incoming)


def _apply_mark_action(stored: Whiteboard, incoming: dict[str, object]) -> DrawingCheck:
    if incoming.get("whiteboard_id") != stored.id:
        return DrawingCheck(whiteboard=None, errors=["whiteboard id cannot change"])
    step_id = incoming.get("step_id")
    marks = incoming.get("marks")
    errors: list[str] = []
    if not isinstance(step_id, str) or not step_id.strip():
        errors.append("step_id: missing field")
    if not isinstance(marks, list) or not marks:
        errors.append("marks: needs at least one mark")
    if errors:
        return DrawingCheck(whiteboard=None, errors=errors)
    drawing = stored.model_dump(mode="json")
    drawing["version"] = _version_after_marks(stored)
    drawing["steps"].append(
        {
            "id": step_id,
            "reply_part": incoming.get("reply_part"),
            "elements": marks,
        }
    )
    return check_drawing(drawing)


def _apply_drawing_marks(stored: Whiteboard, incoming: dict[str, object]) -> DrawingCheck:
    if incoming.get("id") != stored.id:
        return DrawingCheck(whiteboard=None, errors=["whiteboard id cannot change"])
    proposed = {**incoming, "session_id": stored.session_id}
    errors = _incoming_learner_errors(stored, proposed)
    if errors:
        return DrawingCheck(whiteboard=None, errors=errors)
    checked = check_drawing(proposed)
    if checked.whiteboard is None:
        return checked
    updated = checked.whiteboard
    errors = _append_only_errors(stored, updated)
    if errors:
        return DrawingCheck(whiteboard=None, errors=errors)
    return _append_new_mark_steps(stored, updated)


def _incoming_learner_errors(stored: Whiteboard, data: dict[str, object]) -> list[str]:
    element_rows, element_errors = _parse_learner_elements(data)
    if element_errors:
        return element_errors
    errors = _learner_row_errors(stored, element_rows)
    comment_dumps, comment_errors = _parse_learner_comments(data)
    if comment_errors:
        return errors + comment_errors
    errors.extend(
        _named_list_errors(
            _learner_comment_dumps(stored),
            comment_dumps,
            "learner comment",
        )
    )
    return errors


def _parse_learner_elements(
    data: dict[str, object],
) -> tuple[list[tuple[str, dict[str, object]]], list[str]]:
    steps = data.get("steps")
    if not isinstance(steps, list):
        return [], ["steps: missing field"]
    rows: list[tuple[str, dict[str, object]]] = []
    errors: list[str] = []
    for step_index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{step_index}]: invalid")
            continue
        step_id = step.get("id")
        elements = step.get("elements")
        if not isinstance(step_id, str) or not isinstance(elements, list):
            errors.append(f"steps[{step_index}]: invalid")
            continue
        for element_index, element in enumerate(elements):
            if not isinstance(element, dict) or element.get("author") != "learner":
                continue
            try:
                parsed = _ELEMENT_ADAPTER.validate_python(element)
            except ValidationError as exc:
                errors.extend(
                    f"steps[{step_index}].elements[{element_index}]: {message}"
                    for message in _error_messages(exc)
                )
                continue
            rows.append((step_id, parsed.model_dump(mode="json")))
    return rows, errors


def _parse_learner_comments(
    data: dict[str, object],
) -> tuple[list[dict[str, object]], list[str]]:
    raw = data.get("comments", [])
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        return [], ["comments: invalid"]
    dumps: list[dict[str, object]] = []
    errors: list[str] = []
    for index, comment in enumerate(raw):
        if not isinstance(comment, dict) or comment.get("author") != "learner":
            continue
        try:
            parsed = Comment.model_validate(comment)
        except ValidationError as exc:
            errors.extend(
                f"comments[{index}]: {message}" for message in _error_messages(exc)
            )
            continue
        dumps.append(parsed.model_dump(mode="json"))
    return dumps, errors


def _learner_element_rows(whiteboard: Whiteboard) -> list[tuple[str, dict[str, object]]]:
    return [
        (step.id, element.model_dump(mode="json"))
        for step in whiteboard.steps
        for element in step.elements
        if element.author == "learner"
    ]


def _learner_comment_dumps(whiteboard: Whiteboard) -> list[dict[str, object]]:
    return [
        comment.model_dump(mode="json")
        for comment in whiteboard.comments
        if comment.author == "learner"
    ]


def _learner_row_errors(
    stored: Whiteboard, incoming_rows: list[tuple[str, dict[str, object]]]
) -> list[str]:
    stored_rows = _learner_element_rows(stored)
    errors = _named_list_errors(
        [row[1] for row in stored_rows],
        [row[1] for row in incoming_rows],
        "learner element",
    )
    if errors:
        return errors
    stored_steps = {row[1]["id"]: row[0] for row in stored_rows}
    incoming_steps = {row[1]["id"]: row[0] for row in incoming_rows}
    for element_id, step_id in stored_steps.items():
        if incoming_steps.get(element_id) != step_id:
            errors.append(f"learner element '{element_id}' was moved")
    return errors


def _named_list_errors(
    stored_items: list[dict[str, object]],
    incoming_items: list[dict[str, object]],
    noun: str,
) -> list[str]:
    errors: list[str] = []
    stored_by = {str(item["id"]): item for item in stored_items}
    incoming_by = {str(item["id"]): item for item in incoming_items}
    for item_id, item in stored_by.items():
        found = incoming_by.get(item_id)
        if found is None:
            errors.append(f"{noun} '{item_id}' was removed")
        elif found != item:
            errors.append(f"{noun} '{item_id}' was changed")
    for item_id in incoming_by:
        if item_id not in stored_by:
            errors.append(f"{noun} '{item_id}' was added")
    stored_ids = [str(item["id"]) for item in stored_items]
    incoming_ids = [str(item["id"]) for item in incoming_items]
    if not errors and stored_ids != incoming_ids:
        errors.append(f"{noun}s were reordered")
    return errors


def _append_only_errors(stored: Whiteboard, updated: Whiteboard) -> list[str]:
    stored_ids = [step.id for step in stored.steps]
    updated_ids = [step.id for step in updated.steps]
    if updated_ids[: len(stored_ids)] != stored_ids:
        return ["steps cannot be reordered or removed"]
    for left, right in zip(stored.steps, updated.steps, strict=False):
        if left.model_dump(mode="json") != right.model_dump(mode="json"):
            return [f"step '{left.id}' was changed"]
    new_steps = updated.steps[len(stored.steps) :]
    if not new_steps:
        return ["marks: needs at least one mark"]
    errors: list[str] = []
    for step in new_steps:
        if not step.elements:
            errors.append(f"step '{step.id}' needs at least one mark")
            continue
        if any(not isinstance(element, MarkElement) for element in step.elements):
            errors.append(f"step '{step.id}' can only add marks")
    return errors


def _version_after_marks(stored: Whiteboard) -> int:
    """Marks stay on version 3 unless keeping a description would drop it.

    Version 5 stays version 5 so its math and code remain valid.
    Version 6 stays version 6 so its graph remains valid.
    Version 7 stays version 7 so its labels and attached arrows remain valid.
    """

    if stored.version in {
        MATH_CODE_DRAWING_VERSION,
        GRAPH_DRAWING_VERSION,
        CURRENT_DRAWING_VERSION,
    }:
        return stored.version
    if stored.description and stored.description.strip():
        return DESCRIBED_DRAWING_VERSION
    return MARKED_DRAWING_VERSION


def _append_new_mark_steps(stored: Whiteboard, updated: Whiteboard) -> DrawingCheck:
    drawing = stored.model_dump(mode="json")
    drawing["version"] = _version_after_marks(stored)
    drawing["steps"].extend(
        step.model_dump(mode="json") for step in updated.steps[len(stored.steps) :]
    )
    return check_drawing(drawing)


def _learner_change_errors(stored: Whiteboard, updated: Whiteboard) -> list[str]:
    errors: list[str] = []
    if updated.id != stored.id:
        errors.append("whiteboard id cannot change")
    if updated.session_id != stored.session_id:
        errors.append("session_id cannot change")
    stored_step_ids = [step.id for step in stored.steps]
    updated_step_ids = [step.id for step in updated.steps]
    if updated_step_ids != stored_step_ids:
        errors.append("steps cannot be added, removed, or reordered")
    else:
        for left, right in zip(stored.steps, updated.steps, strict=True):
            if left.reply_part != right.reply_part:
                errors.append("a step's reply text cannot change")
                break

    stored_agents = {
        element.id: element
        for element in _elements(stored)
        if element.author == "agent"
    }
    updated_by_id = {element.id: element for element in _elements(updated)}
    for element_id, element in stored_agents.items():
        found = updated_by_id.get(element_id)
        if found is None:
            errors.append(f"agent element '{element_id}' was removed")
            continue
        if found.model_dump(mode="json") != element.model_dump(mode="json"):
            errors.append(f"agent element '{element_id}' was changed")
        if _step_id(stored, element_id) != _step_id(updated, element_id):
            errors.append(f"agent element '{element_id}' was moved to another step")

    for element in _elements(updated):
        if element.id not in stored_agents and element.author != "learner":
            errors.append(f"element '{element.id}' must be authored by the learner")

    stored_agent_comments = {
        comment.id: comment for comment in stored.comments if comment.author == "agent"
    }
    updated_comments = {comment.id: comment for comment in updated.comments}
    for comment_id, comment in stored_agent_comments.items():
        found = updated_comments.get(comment_id)
        if found is None:
            errors.append(f"agent comment '{comment_id}' was removed")
        elif found.model_dump(mode="json") != comment.model_dump(mode="json"):
            errors.append(f"agent comment '{comment_id}' was changed")
    for comment in updated.comments:
        if comment.id not in stored_agent_comments and comment.author != "learner":
            errors.append(f"comment '{comment.id}' must be authored by the learner")
    return errors


def describe_pointed(whiteboard: Whiteboard, element_ids: Sequence[str]) -> str:
    """Name pointed-at elements in the same text form as describe_whiteboard."""

    by_id = {element.id: element for element in _elements(whiteboard)}
    lines = [f"The learner pointed at these parts of whiteboard {whiteboard.id}:"]
    for element_id in element_ids:
        element = by_id.get(element_id)
        if element is None:
            raise ValueError(f"element '{element_id}' is not on that whiteboard")
        lines.append(_describe_element(element))
    return "\n".join(lines)


def pointed_element_errors(whiteboard: Whiteboard, element_ids: Sequence[str]) -> list[str]:
    """Ids that cannot be pointed at on this whiteboard. Empty means the ids are ok."""

    if not element_ids:
        return ["needs at least one element"]
    known = {element.id for element in _elements(whiteboard)}
    errors: list[str] = []
    seen: set[str] = set()
    for element_id in element_ids:
        if element_id in seen:
            errors.append(f"element '{element_id}' is listed more than once")
            continue
        seen.add(element_id)
        if element_id not in known:
            errors.append(f"element '{element_id}' is not on that whiteboard")
    return errors


def element_count(whiteboard: Whiteboard) -> int:
    """Elements across every step, including marks. Comments do not count."""

    return sum(len(step.elements) for step in whiteboard.steps)


def simpler_count_errors(original: Whiteboard, simpler: Whiteboard) -> list[str]:
    """Refuse a simpler redraw that is empty or not strictly smaller."""

    count = element_count(simpler)
    previous = element_count(original)
    errors: list[str] = []
    if count < 1:
        errors.append("a simpler whiteboard needs at least one element")
    if count >= previous:
        errors.append("a simpler whiteboard needs fewer elements than the original")
    return errors


def describe_whiteboard(whiteboard: Whiteboard) -> str:
    """Short text for a later turn. Kinds, labels, positions, and comments."""

    lines = [f"Whiteboard {whiteboard.id}:"]
    for step in whiteboard.steps:
        lines.extend(_describe_element(element) for element in step.elements)
    lines.extend(_describe_comment(comment) for comment in whiteboard.comments)
    if whiteboard.simplifies:
        lines.append(f"Simpler version of whiteboard {whiteboard.simplifies}.")
    return "\n".join(lines)


def summarize_whiteboard(whiteboard: Whiteboard) -> str:
    """One line for a whiteboard the turn is not about. No ids or positions."""

    elements = _elements(whiteboard)
    learner = sum(1 for element in elements if element.author == "learner")
    noun = "part" if len(elements) == 1 else "parts"
    about = whiteboard.description.strip() if whiteboard.description else ""
    if not about:
        about = _drawing_summary(whiteboard)
    if not about.endswith((".", "!", "?")):
        about += "."
    line = f"Whiteboard {whiteboard.id} (summary): {about} {len(elements)} {noun}"
    if learner:
        line += f", {learner} by the learner"
    if whiteboard.comments:
        count = len(whiteboard.comments)
        line += f", {count} {'comment' if count == 1 else 'comments'}"
    line += "."
    if whiteboard.simplifies:
        line += f" Simpler version of whiteboard {whiteboard.simplifies}."
    return line


def readable_description(whiteboard: Whiteboard) -> str:
    """Text a screen reader reads. Not the prompt form from describe_whiteboard.

    The stored agent description comes first. A sentence built from learner
    shapes and learner comments is appended when the learner added any.
    An older drawing with no description uses a summary of the whole drawing
    so the board is never unnamed.
    """

    learner = _learner_sentence(whiteboard)
    stored = whiteboard.description.strip() if whiteboard.description else ""
    base = stored if stored else _drawing_summary(whiteboard)
    extras = _math_code_lines(whiteboard)
    if extras:
        text = "\n".join([base, *extras])
        if not learner:
            return text
        return f"{text}\n{learner}"
    if not learner:
        return base
    if base.endswith((".", "!", "?")):
        return f"{base} {learner}"
    return f"{base}. {learner}"


def _graph_line(element: GraphElement) -> str:
    functions = [series for series in element.series if isinstance(series, FunctionSeries)]
    start = _number(element.x_min)
    end = _number(element.x_max)
    if len(element.series) == 1 and functions:
        return f"graph of y = {functions[0].expression} from {start} to {end}"
    count = len(element.series)
    return f"graph with {count} series from {start} to {end}"


def _math_code_lines(whiteboard: Whiteboard) -> list[str]:
    lines: list[str] = []
    for element in _elements(whiteboard):
        if isinstance(element, MathElement):
            lines.append(f"math formula: {element.latex}")
        elif isinstance(element, CodeElement):
            count = len(element.code.splitlines()) or 1
            lines.append(f"code block in {element.language}, {count} lines")
        elif isinstance(element, GraphElement):
            lines.append(_graph_line(element))
    return lines


def _learner_shapes(whiteboard: Whiteboard) -> list[Element]:
    """Learner shapes. Marks, formulas, and code blocks are not shapes."""

    return [
        element
        for element in _elements(whiteboard)
        if element.author == "learner"
        and not isinstance(element, (MarkElement, MathElement, CodeElement, GraphElement))
    ]


def _learner_sentence(whiteboard: Whiteboard) -> str:
    elements = _learner_shapes(whiteboard)
    comments = [comment for comment in whiteboard.comments if comment.author == "learner"]
    if not elements and not comments:
        return ""
    counts: list[str] = []
    if elements:
        noun = "shape" if len(elements) == 1 else "shapes"
        counts.append(f"{len(elements)} {noun}")
    if comments:
        noun = "comment" if len(comments) == 1 else "comments"
        counts.append(f"{len(comments)} {noun}")
    details = [_screen_phrase(element) for element in elements]
    details.extend(f'"{comment.text}"' for comment in comments)
    return f"Learner added {' and '.join(counts)}: {', '.join(details)}."


def _drawing_summary(whiteboard: Whiteboard) -> str:
    phrases = [
        _screen_phrase(element)
        for element in _elements(whiteboard)
        if not isinstance(element, (MathElement, CodeElement, GraphElement))
    ]
    phrases.extend(
        f'a comment "{comment.text}"' for comment in whiteboard.comments
    )
    if not phrases:
        return "An empty whiteboard."
    return f"{_capitalize(_join_phrases(phrases))}."


def _screen_phrase(element: Element) -> str:
    if isinstance(element, MarkElement):
        if element.mark == "note" and element.text:
            return f'a note "{element.text}"'
        return _an(f"{element.mark} mark")
    if isinstance(element, TextElement):
        if element.text.strip():
            return f'text reading "{element.text}"'
        return "text"
    if isinstance(element, FreehandElement):
        return "a freehand line"
    if isinstance(element, (RectangleElement, EllipseElement, ArrowElement)) and element.label:
        return f'{_an(element.kind)} labeled "{element.label}"'
    return _an(element.kind)


def _an(name: str) -> str:
    article = "an" if name[:1].lower() in "aeiou" else "a"
    return f"{article} {name}"


def _join_phrases(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return f"{', '.join(phrases[:-1])}, and {phrases[-1]}"


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _number(value: float) -> str:
    if value == math.trunc(value):
        return str(int(value))
    return format(value, "f").rstrip("0").rstrip(".")


def _place(point: Point) -> str:
    return f"({_number(point.x)}, {_number(point.y)})"


def _describe_series(series: Series) -> str:
    if isinstance(series, FunctionSeries):
        return f"y = {series.expression}"
    return "data"


def _describe_element(element: Element) -> str:
    if isinstance(element, GraphElement):
        series = "; ".join(_describe_series(item) for item in element.series)
        return (
            f"- graph {element.id} by {element.author} "
            f"at {_place(element.position)}: "
            f'x-axis "{element.x_label}" from {_number(element.x_min)} to {_number(element.x_max)}, '
            f'y-axis "{element.y_label}" from {_number(element.y_min)} to {_number(element.y_max)}; '
            f"{series}"
        )
    if isinstance(element, MathElement):
        return (
            f"- math {element.id} by {element.author} "
            f"at {_place(element.position)}: {element.latex}"
        )
    if isinstance(element, CodeElement):
        return (
            f"- code {element.id} by {element.author} "
            f"at {_place(element.position)} in {element.language}:\n{element.code}"
        )
    if isinstance(element, MarkElement):
        note = ""
        if element.mark == "note" and element.text:
            note = f' "{element.text}"'
        return (
            f"- mark {element.mark} {element.id} by {element.author} "
            f"on {element.target_element_id} at {_place(element.position)}{note}"
        )
    label = ""
    if isinstance(element, TextElement) and element.text:
        label = f' "{element.text}"'
    elif isinstance(element, (RectangleElement, EllipseElement, ArrowElement)) and element.label:
        label = f' "{element.label}"'
    if isinstance(element, ArrowElement) and (
        element.start_element_id or element.end_element_id
    ):
        start = element.start_element_id or _place(element.start)
        end = element.end_element_id or _place(element.end)
        return f"- arrow {element.id} by {element.author} from {start} to {end}{label}"
    return (
        f"- {element.kind} {element.id} by {element.author} "
        f"at {_place(element.position)}{label}"
    )


def _describe_comment(comment: Comment) -> str:
    if comment.element_id is not None:
        where = f"about {comment.element_id}"
    else:
        assert comment.position is not None
        where = f"at {_place(comment.position)}"
    return f'- comment {comment.id} by {comment.author} {where}: "{comment.text}"'


def _error_messages(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for error in exc.errors():
        where = _where(error["loc"])
        detail = _detail(error)
        messages.append(f"{where}: {detail}" if where else detail)
    return messages


def _where(location: tuple[object, ...]) -> str:
    parts: list[str] = []
    for part in location:
        if isinstance(part, int) and parts:
            parts[-1] = f"{parts[-1]}[{part}]"
        else:
            parts.append(str(part))
    return ".".join(parts)


def _detail(error: dict[str, object]) -> str:
    error_type = error.get("type")
    if error_type == "union_tag_invalid":
        ctx = error.get("ctx")
        tag = ctx.get("tag") if isinstance(ctx, dict) else None
        if tag is None:
            return "unknown element kind"
        return f"unknown element kind '{tag}'"
    if error_type == "missing":
        return "missing field"
    message = str(error.get("msg", "invalid"))
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message
