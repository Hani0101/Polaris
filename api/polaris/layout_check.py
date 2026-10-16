"""Layout checks for a drawing that has already passed check_drawing.

check_drawing checks the data format (WB-05). These checks look at where
the agent's parts sit: shapes that overlap, text that spills out of its box,
parts outside the drawing area, arrow ends that touch nothing, and more
parts than a phone screen can show (WB-16). The teaching agent gets the
problems back through the same fix limit as a format error. The drawing
evals count the same problems as a score.

Text size is an estimate. It uses tldraw's font sizes and a wide average
character, so a label that fits here fits in the browser. The browser is
not asked.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from polaris.whiteboard import (
    ArrowElement,
    CodeElement,
    Element,
    EllipseElement,
    FreehandElement,
    GraphElement,
    LineElement,
    MarkElement,
    MathElement,
    Point,
    RectangleElement,
    TextElement,
    Whiteboard,
)


@dataclass(frozen=True)
class LayoutLimits:
    """Every layout check and the auto layout read this."""

    # The area a new drawing uses. It is portrait so it fits a phone.
    frame_width: float = 1_000
    frame_height: float = 1_400
    # Agent parts, marks excluded. More than this is hard to read on a phone.
    max_parts: int = 24
    # How far an arrow end may sit from a part and still touch it.
    touch_distance: float = 12
    # Overlap smaller than this, in square units, is a shared edge.
    overlap_area: float = 16
    # Space between a box's edge and its label (tldraw's label padding).
    label_padding: float = 16
    # Average character width as a share of the font size. Wide on purpose.
    char_width: float = 0.6
    line_height: float = 1.35


LAYOUT_LIMITS = LayoutLimits()

# tldraw draws text at these sizes. A Polaris stroke width maps to a size
# the same way web/src/whiteboard/style.ts strokeSize does.
_FONT_SIZES = (
    (2.0, 18.0),
    (3.5, 24.0),
    (5.0, 36.0),
)
_XL_FONT_SIZE = 44.0

# An ellipse's usable label area, as a share of its box.
_ELLIPSE_LABEL_SHARE = 0.7


def font_size(stroke_width: float) -> float:
    for max_width, size in _FONT_SIZES:
        if stroke_width <= max_width:
            return size
    return _XL_FONT_SIZE


def wrap_lines(text: str, width: float, size: float) -> list[str]:
    """Greedy word wrap at the estimated character width. Long words stay whole."""

    per_line = max(1, math.floor(width / (size * LAYOUT_LIMITS.char_width)))
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if len(candidate) <= per_line or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def text_width(text: str, size: float) -> float:
    longest = max((len(line) for line in text.splitlines()), default=0)
    return longest * size * LAYOUT_LIMITS.char_width


def text_block(text: str, width: float, size: float) -> tuple[float, float]:
    """Width of the longest wrapped line, and the height of all lines."""

    lines = wrap_lines(text, width, size)
    widest = max((len(line) for line in lines), default=0)
    height = len(lines) * size * LAYOUT_LIMITS.line_height
    return widest * size * LAYOUT_LIMITS.char_width, height


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def area(self) -> float:
        return max(0.0, self.right - self.left) * max(0.0, self.bottom - self.top)

    def overlap(self, other: "Box") -> float:
        width = min(self.right, other.right) - max(self.left, other.left)
        height = min(self.bottom, other.bottom) - max(self.top, other.top)
        if width <= 0 or height <= 0:
            return 0.0
        return width * height

    def contains(self, other: "Box") -> bool:
        return (
            self.left <= other.left
            and self.top <= other.top
            and self.right >= other.right
            and self.bottom >= other.bottom
        )

    def distance(self, point: Point) -> float:
        dx = max(self.left - point.x, 0.0, point.x - self.right)
        dy = max(self.top - point.y, 0.0, point.y - self.bottom)
        return math.hypot(dx, dy)


@dataclass(frozen=True)
class LayoutProblem:
    """kind is one of LAYOUT_PROBLEM_KINDS. message is what the agent reads."""

    kind: str
    element_ids: tuple[str, ...]
    message: str


LAYOUT_PROBLEM_KINDS = (
    "overlap",
    "text_spill",
    "outside",
    "loose_arrow",
    "too_many_parts",
    "misplaced_mark",
)

# Parts with an area. Arrows, lines, freehand lines, and marks are not.
_SOLID = (RectangleElement, EllipseElement, TextElement, MathElement, CodeElement, GraphElement)
_CONTAINERS = (RectangleElement, EllipseElement)


def _box(element: Element) -> Box:
    left = element.position.x
    top = element.position.y
    height = element.size.height
    if isinstance(element, TextElement) and element.text.strip():
        # tldraw grows a fixed-width text shape downward to fit its lines.
        _width, needed = text_block(
            element.text, element.size.width, font_size(element.style.stroke_width)
        )
        height = max(height, needed)
    return Box(left, top, left + element.size.width, top + height)


def _points(element: Element) -> list[Point]:
    if isinstance(element, (ArrowElement, LineElement)):
        return [element.start, element.end]
    if isinstance(element, FreehandElement):
        return list(element.points)
    return []


def _overlap_problems(solid: list[Element]) -> list[LayoutProblem]:
    problems: list[LayoutProblem] = []
    boxes = [(element, _box(element)) for element in solid]
    for index, (left, left_box) in enumerate(boxes):
        for right, right_box in boxes[index + 1 :]:
            if left_box.overlap(right_box) <= LAYOUT_LIMITS.overlap_area:
                continue
            both_text = isinstance(left, TextElement) and isinstance(right, TextElement)
            if not both_text:
                if isinstance(left, _CONTAINERS) and left_box.contains(right_box):
                    continue
                if isinstance(right, _CONTAINERS) and right_box.contains(left_box):
                    continue
            problems.append(
                LayoutProblem(
                    "overlap",
                    (left.id, right.id),
                    f"'{left.id}' and '{right.id}' overlap. Move one of them, "
                    "or put a label inside its box with label.",
                )
            )
    return problems


def _label_problem(element: RectangleElement | EllipseElement) -> LayoutProblem | None:
    if not element.label:
        return None
    padding = LAYOUT_LIMITS.label_padding * 2
    share = _ELLIPSE_LABEL_SHARE if isinstance(element, EllipseElement) else 1.0
    room_width = element.size.width * share - padding
    room_height = element.size.height * share - padding
    size = font_size(element.style.stroke_width)
    if room_width <= 0 or room_height <= 0:
        return LayoutProblem(
            "text_spill",
            (element.id,),
            f"The label of '{element.id}' does not fit: the box is too small for any text.",
        )
    width, height = text_block(element.label, room_width, size)
    if width <= room_width and height <= room_height:
        return None
    need_width = math.ceil(min(width, text_width(element.label, size)) / share + padding)
    need_height = math.ceil(height / share + padding)
    return LayoutProblem(
        "text_spill",
        (element.id,),
        f"The label of '{element.id}' does not fit its box. Make the box about "
        f"{max(need_width, math.ceil(element.size.width))} wide and "
        f"{max(need_height, math.ceil(element.size.height))} tall, or shorten the label.",
    )


def _text_problem(element: TextElement) -> LayoutProblem | None:
    if not element.text.strip():
        return None
    size = font_size(element.style.stroke_width)
    width, height = text_block(element.text, element.size.width, size)
    if width <= element.size.width + 1 and height <= element.size.height + 1:
        return None
    return LayoutProblem(
        "text_spill",
        (element.id,),
        f"The text in '{element.id}' spills out of its box. Make it about "
        f"{math.ceil(max(width, element.size.width))} wide and "
        f"{math.ceil(max(height, element.size.height))} tall, or shorten the text.",
    )


def _outside_problem(element: Element) -> LayoutProblem | None:
    frame = Box(0, 0, LAYOUT_LIMITS.frame_width, LAYOUT_LIMITS.frame_height)
    inside = frame.contains(_box(element)) if isinstance(element, _SOLID) else True
    inside = inside and all(frame.distance(point) == 0 for point in _points(element))
    if inside:
        return None
    return LayoutProblem(
        "outside",
        (element.id,),
        f"'{element.id}' is outside the drawing area. Keep every part between "
        f"(0, 0) and ({LAYOUT_LIMITS.frame_width:g}, {LAYOUT_LIMITS.frame_height:g}).",
    )


def _loose_arrow_problems(
    arrow: ArrowElement, targets: list[Element]
) -> list[LayoutProblem]:
    problems: list[LayoutProblem] = []
    ends = (
        ("start", arrow.start, arrow.start_element_id),
        ("end", arrow.end, arrow.end_element_id),
    )
    for name, point, attached in ends:
        if attached is not None:
            continue
        touching = any(
            _box(target).distance(point) <= LAYOUT_LIMITS.touch_distance
            for target in targets
            if target.id != arrow.id
        )
        if touching:
            continue
        problems.append(
            LayoutProblem(
                "loose_arrow",
                (arrow.id,),
                f"The {name} of arrow '{arrow.id}' touches nothing. Attach it with "
                f"{name}_element_id, or move it onto the part it points at.",
            )
        )
    return problems


def layout_problems(
    whiteboard: Whiteboard, element_ids: Iterable[str] | None = None
) -> list[LayoutProblem]:
    """Problems with the agent's parts. Learner parts and marks are never at fault.

    element_ids limits the check to problems that involve those parts. None
    checks every agent part.
    """

    elements = [element for step in whiteboard.steps for element in step.elements]
    agent = [
        element
        for element in elements
        if element.author == "agent" and not isinstance(element, MarkElement)
    ]
    wanted = None if element_ids is None else set(element_ids)

    def involved(problem: LayoutProblem) -> bool:
        return wanted is None or any(item in wanted for item in problem.element_ids)

    problems: list[LayoutProblem] = []
    if len(agent) > LAYOUT_LIMITS.max_parts:
        problems.append(
            LayoutProblem(
                "too_many_parts",
                tuple(element.id for element in agent),
                f"This drawing has {len(agent)} parts. A phone screen shows about "
                f"{LAYOUT_LIMITS.max_parts}. Leave parts out, or split the idea "
                "into two whiteboards.",
            )
        )
    problems.extend(_overlap_problems([item for item in agent if isinstance(item, _SOLID)]))
    for element in agent:
        if isinstance(element, (RectangleElement, EllipseElement)):
            found = _label_problem(element)
        elif isinstance(element, TextElement):
            found = _text_problem(element)
        else:
            found = None
        if found is not None:
            problems.append(found)
    for element in agent:
        found = _outside_problem(element)
        if found is not None:
            problems.append(found)
    targets = [item for item in elements if isinstance(item, _SOLID) or isinstance(item, FreehandElement)]
    for element in agent:
        if isinstance(element, ArrowElement):
            problems.extend(_loose_arrow_problems(element, targets))
    return [problem for problem in problems if involved(problem)]


def _note_box(mark: MarkElement) -> Box:
    left = mark.position.x
    top = mark.position.y
    return Box(left, top, left + mark.size.width, top + mark.size.height)


def _mark_problem(
    mark: MarkElement, target: Element | None, learner: list[Element], notes: list[MarkElement]
) -> list[LayoutProblem]:
    if target is None:
        return []
    target_box = _box(target)
    if mark.mark == "circle":
        circle = _note_box(mark)
        if circle.overlap(target_box) <= 0:
            return [
                LayoutProblem(
                    "misplaced_mark",
                    (mark.id,),
                    f"Circle mark '{mark.id}' does not surround '{target.id}'. "
                    f"Put it around that element's box.",
                )
            ]
        return []
    if mark.mark == "arrow":
        assert mark.end is not None
        if target_box.distance(mark.end) <= LAYOUT_LIMITS.touch_distance:
            return []
        return [
            LayoutProblem(
                "misplaced_mark",
                (mark.id,),
                f"The end of arrow mark '{mark.id}' does not reach '{target.id}'. "
                "Move its end onto that element.",
            )
        ]
    problems: list[LayoutProblem] = []
    note = _note_box(mark)
    covered = [
        element.id
        for element in learner
        if note.overlap(_box(element)) > LAYOUT_LIMITS.overlap_area
    ]
    if covered:
        names = ", ".join(f"'{item}'" for item in covered)
        problems.append(
            LayoutProblem(
                "misplaced_mark",
                (mark.id,),
                f"Note '{mark.id}' covers the learner's drawing ({names}). "
                "Move it into empty space next to the element it is about.",
            )
        )
    for other in notes:
        if other.id != mark.id and note.overlap(_note_box(other)) > LAYOUT_LIMITS.overlap_area:
            problems.append(
                LayoutProblem(
                    "overlap",
                    (mark.id, other.id),
                    f"Notes '{mark.id}' and '{other.id}' overlap. Move one of them.",
                )
            )
    if mark.text:
        size = font_size(mark.style.stroke_width)
        room_width = mark.size.width - LAYOUT_LIMITS.label_padding * 2
        room_height = mark.size.height - LAYOUT_LIMITS.label_padding * 2
        width, height = text_block(mark.text, max(room_width, 1), size)
        if room_width <= 0 or width > room_width or height > room_height:
            problems.append(
                LayoutProblem(
                    "text_spill",
                    (mark.id,),
                    f"The text of note '{mark.id}' does not fit. Make the note about "
                    f"{math.ceil(width + LAYOUT_LIMITS.label_padding * 2)} wide and "
                    f"{math.ceil(height + LAYOUT_LIMITS.label_padding * 2)} tall, "
                    "or shorten the text.",
                )
            )
    return problems


def mark_problems(whiteboard: Whiteboard, mark_ids: Iterable[str]) -> list[LayoutProblem]:
    """Problems with these marks: a circle that misses its target, an arrow that
    does not reach it, a note that covers the learner's drawing or another note,
    or note text that does not fit."""

    wanted = set(mark_ids)
    elements = [element for step in whiteboard.steps for element in step.elements]
    by_id = {element.id: element for element in elements}
    learner = [
        element
        for element in elements
        if element.author == "learner" and isinstance(element, (*_SOLID, FreehandElement))
    ]
    marks = [element for element in elements if isinstance(element, MarkElement)]
    notes = [mark for mark in marks if mark.mark == "note"]
    problems: list[LayoutProblem] = []
    reported: set[frozenset[str]] = set()
    for mark in marks:
        if mark.id not in wanted:
            continue
        for problem in _mark_problem(mark, by_id.get(mark.target_element_id), learner, notes):
            key = frozenset(problem.element_ids)
            if problem.kind == "overlap" and key in reported:
                continue
            reported.add(key)
            problems.append(problem)
    return problems


def layout_score(whiteboard: Whiteboard) -> dict[str, int]:
    """Problem counts by kind, every kind present. The drawing evals read this."""

    counts = {kind: 0 for kind in LAYOUT_PROBLEM_KINDS}
    for problem in layout_problems(whiteboard):
        counts[problem.kind] += 1
    return counts
