"""The agent's own parts on the pinned board (WB-20).

extend_whiteboard sends a new step of agent parts for a stored board. The
parts are first checked as a drawing of their own, so check_drawing and
layout_problems judge only the agent's parts and the learner's parts are never
at fault. Polaris then moves the whole step, as one group, into free space
beside what is already on the board, and appends it as an added step. The
learner's parts and comments are copied from the stored board unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from polaris.auto_layout import expand_layout
from polaris.layout_check import LAYOUT_LIMITS, LayoutProblem, layout_problems
from polaris.whiteboard import (
    CURRENT_DRAWING_VERSION,
    BLANK_WHITEBOARD_DESCRIPTION,
    Element,
    FreehandElement,
    Whiteboard,
    check_drawing,
)

# Space between what is on the board and the agent's added parts.
EXTENSION_GAP = 80.0


@dataclass(frozen=True)
class ExtensionCheck:
    """whiteboard is the stored board with the added step, present only when errors is empty.

    problems are layout problems in the agent's parts, judged on their own.
    """

    whiteboard: Whiteboard | None
    errors: list[str]
    problems: list[LayoutProblem]


@dataclass(frozen=True)
class _Bounds:
    left: float
    top: float
    right: float
    bottom: float

    def near(self, other: _Bounds, gap: float) -> bool:
        return not (
            self.right + gap <= other.left
            or other.right + gap <= self.left
            or self.bottom + gap <= other.top
            or other.bottom + gap <= self.top
        )


def apply_extension(stored: Whiteboard, action: dict[str, Any]) -> ExtensionCheck:
    """Check the agent's added step, then place it beside the stored board."""

    errors = _action_errors(stored, action)
    if errors:
        return ExtensionCheck(whiteboard=None, errors=errors, problems=[])
    alone = _parts_alone(stored, action)
    if isinstance(alone, list):
        return ExtensionCheck(whiteboard=None, errors=alone, problems=[])
    step = alone.steps[0]
    if len(step.elements) > LAYOUT_LIMITS.max_parts:
        return ExtensionCheck(
            whiteboard=None,
            errors=[
                f"This step has {len(step.elements)} parts. A phone screen shows about "
                f"{LAYOUT_LIMITS.max_parts}. Leave parts out."
            ],
            problems=[],
        )
    problems = layout_problems(alone)
    shift = _shift_beside(_bounds(_all_elements(stored)), _bounds(step.elements))
    placed = step.model_dump(mode="json")
    placed["elements"] = [_moved(element, shift) for element in placed["elements"]]
    placed["extension"] = True
    drawing = stored.model_dump(mode="json")
    drawing["steps"].append(placed)
    checked = check_drawing(drawing)
    if checked.whiteboard is None:
        return ExtensionCheck(whiteboard=None, errors=checked.errors, problems=problems)
    return ExtensionCheck(whiteboard=checked.whiteboard, errors=[], problems=problems)


def _action_errors(stored: Whiteboard, action: dict[str, Any]) -> list[str]:
    if action.get("whiteboard_id") != stored.id:
        return ["whiteboard id cannot change"]
    errors: list[str] = []
    if stored.version != CURRENT_DRAWING_VERSION:
        errors.append(
            "This whiteboard is an older format, so parts cannot be added to it. "
            "Draw a new whiteboard instead."
        )
    step_id = action.get("step_id")
    if not isinstance(step_id, str) or not step_id.strip():
        errors.append("step_id: missing field")
    elements = action.get("elements")
    has_layout = action.get("layout") is not None
    if not has_layout and (not isinstance(elements, list) or not elements):
        errors.append("elements: needs at least one part, or send layout")
    return errors


def _parts_alone(stored: Whiteboard, action: dict[str, Any]) -> Whiteboard | list[str]:
    """The added step as a drawing of its own. Arrows may attach only to its own parts."""

    elements = action.get("elements")
    draft: dict[str, Any] = {
        "version": CURRENT_DRAWING_VERSION,
        "id": stored.id,
        "session_id": stored.session_id,
        "description": BLANK_WHITEBOARD_DESCRIPTION,
        "steps": [
            {
                "id": action.get("step_id"),
                "reply_part": action.get("reply_part"),
                "elements": elements if isinstance(elements, list) else [],
            }
        ],
    }
    if action.get("layout") is not None:
        draft["layout"] = action["layout"]
    expanded = expand_layout(draft)
    if expanded.errors:
        return expanded.errors
    checked = check_drawing(expanded.drawing)
    if checked.whiteboard is None:
        return checked.errors
    return checked.whiteboard


def _all_elements(whiteboard: Whiteboard) -> list[Element]:
    return [element for step in whiteboard.steps for element in step.elements]


def _points(element: Element) -> list[tuple[float, float]]:
    points = [
        (element.position.x, element.position.y),
        (element.position.x + element.size.width, element.position.y + element.size.height),
    ]
    for name in ("start", "end"):
        point = getattr(element, name, None)
        if point is not None:
            points.append((point.x, point.y))
    if isinstance(element, FreehandElement):
        points.extend((point.x, point.y) for point in element.points)
    return points


def _bounds(elements: Iterable[Element]) -> _Bounds | None:
    points = [point for element in elements for point in _points(element)]
    if not points:
        return None
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    return _Bounds(min(xs), min(ys), max(xs), max(ys))


def _shift_beside(board: _Bounds | None, group: _Bounds | None) -> tuple[float, float]:
    """Move the group to the right of the board, tops aligned, when they would touch."""

    if board is None or group is None or not board.near(group, EXTENSION_GAP):
        return (0.0, 0.0)
    return (board.right + EXTENSION_GAP - group.left, board.top - group.top)


def _moved(element: dict[str, Any], shift: tuple[float, float]) -> dict[str, Any]:
    dx, dy = shift
    if dx == 0 and dy == 0:
        return element

    def move(point: dict[str, Any]) -> dict[str, Any]:
        return {**point, "x": point["x"] + dx, "y": point["y"] + dy}

    moved = {**element, "position": move(element["position"])}
    for name in ("start", "end"):
        if isinstance(element.get(name), dict):
            moved[name] = move(element[name])
    if isinstance(element.get("points"), list):
        moved["points"] = [move(point) for point in element["points"]]
    return moved
