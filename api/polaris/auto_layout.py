"""Turn a described structure into placed elements (WB-17).

The agent can send a layout instead of coordinates: a flow, a sequence, a
cycle, a tree, a two-column comparison, or labeled parts. This module places
it and returns ordinary version 7 elements: boxes with their label inside,
and arrows attached to the boxes they join. check_drawing then checks the
result like any drawing (WB-05), and the stored positions are the ones the
browser draws, so steps, marks, pointing, and simpler redraws keep working.

Sizes come from the same text estimate the layout checks use, so a placed
drawing passes them.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from polaris.layout_check import LAYOUT_LIMITS, font_size, text_block, text_width

LAYOUT_KINDS = ("flow", "sequence", "cycle", "tree", "comparison", "parts")


@dataclass(frozen=True)
class AutoLayoutLimits:
    margin: float = 40
    # Space along the direction of the arrows, and across it.
    main_gap: float = 80
    labeled_main_gap: float = 120
    cross_gap: float = 40
    min_box_width: float = 120
    max_box_width: float = 240
    min_box_height: float = 60
    heading_stroke_width: float = 3.5
    whole_min_width: float = 220
    whole_min_height: float = 160


AUTO_LAYOUT_LIMITS = AutoLayoutLimits()

_STROKE = "#1d1d1d"
_STROKE_WIDTH = 2.0
_ELLIPSE_SHARE = 0.7


@dataclass(frozen=True)
class LayoutExpansion:
    """drawing is the input with the layout placed. It is passed on only when errors is empty."""

    drawing: object
    errors: list[str]


class _LayoutRefusal(Exception):
    """A layout that cannot be placed. Never escapes expand_layout."""


@dataclass
class _Node:
    id: str
    label: str
    shape: str = "rectangle"
    step: str | None = None
    stroke_width: float = _STROKE_WIDTH
    width: float = 0
    height: float = 0
    x: float = 0
    y: float = 0


@dataclass
class _Link:
    start: str
    end: str
    label: str | None = None
    step: str | None = None
    id: str | None = None
    bend: float | None = None


@dataclass
class _Placed:
    nodes: list[_Node] = field(default_factory=list)
    links: list[_Link] = field(default_factory=list)


def expand_layout(data: object) -> LayoutExpansion:
    """Place data["layout"] into its steps. Data without a layout passes through."""

    if not isinstance(data, dict) or "layout" not in data:
        return LayoutExpansion(drawing=data, errors=[])
    try:
        return LayoutExpansion(drawing=_expand(data), errors=[])
    except _LayoutRefusal as refusal:
        return LayoutExpansion(drawing=None, errors=[f"layout: {refusal.args[0]}"])


def _expand(data: dict[str, Any]) -> dict[str, Any]:
    layout = data.get("layout")
    if not isinstance(layout, dict):
        raise _LayoutRefusal("must be an object")
    kind = layout.get("kind")
    placer = _PLACERS.get(kind) if isinstance(kind, str) else None
    if placer is None:
        raise _LayoutRefusal(f"kind must be one of {', '.join(LAYOUT_KINDS)}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise _LayoutRefusal("needs steps, each with id and reply_part")
    step_ids = [step.get("id") if isinstance(step, dict) else None for step in steps]
    if not all(isinstance(step_id, str) and step_id for step_id in step_ids):
        raise _LayoutRefusal("every step needs an id")
    placed = placer(layout)
    _check_steps(placed, step_ids)
    _check_frame(placed, kind)
    by_step = _elements_by_step(placed, step_ids)
    expanded_steps = []
    for step, step_id in zip(steps, step_ids, strict=True):
        elements = step.get("elements", [])
        if not isinstance(elements, list):
            raise _LayoutRefusal(f"step '{step_id}' elements must be a list")
        expanded_steps.append({**step, "elements": [*by_step[step_id], *elements]})
    expanded = {key: value for key, value in data.items() if key != "layout"}
    expanded["steps"] = expanded_steps
    return expanded


# Reading the agent's input.


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _LayoutRefusal(f"{where} needs text")
    return value.strip()


def _optional_text(value: object, where: str) -> str | None:
    if value is None:
        return None
    return _text(value, where)


def _items(layout: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = layout.get(key)
    if not isinstance(value, list) or not value:
        raise _LayoutRefusal(f"{key} needs at least one entry")
    if not all(isinstance(item, dict) for item in value):
        raise _LayoutRefusal(f"each of {key} must be an object")
    return value


def _node(item: dict[str, Any], where: str) -> _Node:
    shape = item.get("shape", "rectangle")
    if shape not in ("rectangle", "ellipse"):
        raise _LayoutRefusal(f"{where}.shape must be rectangle or ellipse")
    return _Node(
        id=_text(item.get("id"), f"{where}.id"),
        label=_text(item.get("label"), f"{where}.label"),
        shape=shape,
        step=_optional_text(item.get("step"), f"{where}.step"),
    )


def _nodes(layout: dict[str, Any]) -> list[_Node]:
    nodes = [_node(item, f"nodes[{index}]") for index, item in enumerate(_items(layout, "nodes"))]
    seen: set[str] = set()
    for node in nodes:
        if node.id in seen:
            raise _LayoutRefusal(f"node id '{node.id}' is used twice")
        seen.add(node.id)
    if len(nodes) > LAYOUT_LIMITS.max_parts // 2:
        raise _LayoutRefusal(
            f"{len(nodes)} nodes is too many for a phone screen. "
            f"Use at most {LAYOUT_LIMITS.max_parts // 2}."
        )
    for node in nodes:
        _size(node)
    return nodes


def _direction(layout: dict[str, Any]) -> str:
    direction = layout.get("direction", "down")
    if direction not in ("down", "right"):
        raise _LayoutRefusal("direction must be down or right")
    return direction


def _links(layout: dict[str, Any], known: set[str]) -> list[_Link]:
    raw = layout.get("links", [])
    if not isinstance(raw, list):
        raise _LayoutRefusal("links must be a list")
    links: list[_Link] = []
    for index, item in enumerate(raw):
        where = f"links[{index}]"
        if not isinstance(item, dict):
            raise _LayoutRefusal(f"{where} must be an object")
        start = _text(item.get("from"), f"{where}.from")
        end = _text(item.get("to"), f"{where}.to")
        for name in (start, end):
            if name not in known:
                raise _LayoutRefusal(f"{where} names unknown node '{name}'")
        if start == end:
            raise _LayoutRefusal(f"{where} must join two different nodes")
        links.append(
            _Link(
                start=start,
                end=end,
                label=_optional_text(item.get("label"), f"{where}.label"),
                step=_optional_text(item.get("step"), f"{where}.step"),
                id=_optional_text(item.get("id"), f"{where}.id"),
            )
        )
    return links


# Sizes.


def _size(node: _Node, min_width: float | None = None, min_height: float | None = None) -> None:
    limits = AUTO_LAYOUT_LIMITS
    share = _ELLIPSE_SHARE if node.shape == "ellipse" else 1.0
    padding = LAYOUT_LIMITS.label_padding * 2
    size = font_size(node.stroke_width)
    room = limits.max_box_width * share - padding
    one_line = text_width(node.label, size)
    width, height = text_block(node.label, min(room, one_line + 1), size)
    node.width = math.ceil(
        max(min_width or limits.min_box_width, (width + padding) / share)
    )
    node.height = math.ceil(
        max(min_height or limits.min_box_height, (height + padding) / share)
    )


def _main_gap(links: list[_Link]) -> float:
    if any(link.label for link in links):
        return AUTO_LAYOUT_LIMITS.labeled_main_gap
    return AUTO_LAYOUT_LIMITS.main_gap


# Placing layers. A layer is a row (down) or a column (right).


def _place_layers(layers: list[list[_Node]], direction: str, main_gap: float) -> None:
    limits = AUTO_LAYOUT_LIMITS
    down = direction == "down"

    def main(node: _Node) -> float:
        return node.height if down else node.width

    def cross(node: _Node) -> float:
        return node.width if down else node.height

    spans = [
        sum(cross(node) for node in layer) + limits.cross_gap * (len(layer) - 1)
        for layer in layers
    ]
    widest = max(spans)
    offset = limits.margin
    for layer, span in zip(layers, spans, strict=True):
        depth = max(main(node) for node in layer)
        along = limits.margin + (widest - span) / 2
        for node in layer:
            centered = offset + (depth - main(node)) / 2
            if down:
                node.x, node.y = along, centered
            else:
                node.x, node.y = centered, along
            along += cross(node) + limits.cross_gap
        offset += depth + main_gap


def _layers(nodes: list[_Node], links: list[_Link], direction: str) -> list[list[_Node]]:
    """Longest-path layers from the sources. A link that closes a loop is ignored."""

    order = {node.id: index for index, node in enumerate(nodes)}
    outgoing: dict[str, list[str]] = {node.id: [] for node in nodes}
    for link in links:
        outgoing[link.start].append(link.end)
    forward: dict[str, list[str]] = {node.id: [] for node in nodes}
    state: dict[str, int] = {}

    def visit(node_id: str) -> None:
        state[node_id] = 1
        for target in outgoing[node_id]:
            if state.get(target) == 1:
                continue
            forward[node_id].append(target)
            if target not in state:
                visit(target)
        state[node_id] = 2

    for node in nodes:
        if node.id not in state:
            visit(node.id)
    layer: dict[str, int] = {node.id: 0 for node in nodes}
    for node_id in _topological(nodes, forward):
        for target in forward[node_id]:
            layer[target] = max(layer[target], layer[node_id] + 1)
    count = max(layer.values()) + 1
    grouped: list[list[_Node]] = [[] for _ in range(count)]
    for node in nodes:
        grouped[layer[node.id]].append(node)
    # A link that skips layers gets a placeholder as wide as a box in each
    # layer it crosses. Rows are centered, so the boxes in those layers move
    # aside and the straight arrow passes between them.
    down = direction == "down"
    across = max((node.width if down else node.height) for node in nodes)
    along = min((node.height if down else node.width) for node in nodes)
    incoming: dict[str, list[str]] = {node.id: [] for node in nodes}
    for source, targets in forward.items():
        for target in targets:
            previous = source
            for between in range(layer[source] + 1, layer[target]):
                gap = _Node(
                    id=f"\0{source}>{target}#{between}",
                    label="",
                    width=across if down else along,
                    height=along if down else across,
                )
                grouped[between].append(gap)
                incoming[gap.id] = [previous]
                order[gap.id] = len(order)
                previous = gap.id
            incoming[target].append(previous)
    # One barycenter pass keeps linked nodes near each other.
    position = {node.id: index for row in grouped for index, node in enumerate(row)}
    for row in grouped[1:]:
        def weight(node: _Node) -> tuple[float, int]:
            parents = incoming[node.id]
            if not parents:
                return (float(position[node.id]), order[node.id])
            return (sum(position[item] for item in parents) / len(parents), order[node.id])

        row.sort(key=weight)
        for index, node in enumerate(row):
            position[node.id] = index
    return grouped


def _topological(nodes: list[_Node], forward: dict[str, list[str]]) -> list[str]:
    indegree = {node.id: 0 for node in nodes}
    for targets in forward.values():
        for target in targets:
            indegree[target] += 1
    ready = [node.id for node in nodes if indegree[node.id] == 0]
    result: list[str] = []
    while ready:
        node_id = ready.pop(0)
        result.append(node_id)
        for target in forward[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return result


# The layout kinds.


def _flow(layout: dict[str, Any]) -> _Placed:
    nodes = _nodes(layout)
    links = _links(layout, {node.id for node in nodes})
    direction = _direction(layout)
    _place_layers(_layers(nodes, links, direction), direction, _main_gap(links))
    _bend_back_links(nodes, links, direction)
    return _Placed(nodes, links)


# Share of an arc's full bend reached a third of the way along it. A back
# link is bent far enough that the boxes it passes there are still clear.
_ARC_THIRD = 0.75


def _bend_back_links(nodes: list[_Node], links: list[_Link], direction: str) -> None:
    """Curve a link that goes back against the flow, so it passes beside the boxes
    between its ends instead of through them."""

    by_id = {node.id: node for node in nodes}
    down = direction == "down"
    clearance = max((node.width if down else node.height) for node in nodes) / 2
    bend = math.ceil((clearance + AUTO_LAYOUT_LIMITS.cross_gap) / _ARC_THIRD)
    for link in links:
        start = by_id[link.start]
        end = by_id[link.end]
        backward = end.y < start.y if down else end.x < start.x
        if backward:
            # Going up, a positive bend curves right. Going left, a negative
            # bend curves down. Both stay inside the drawing area.
            link.bend = bend if down else -bend


def _sequence(layout: dict[str, Any]) -> _Placed:
    nodes = _nodes(layout)
    if "links" in layout:
        raise _LayoutRefusal("a sequence links its nodes in order; do not send links")
    links = [_Link(start=left.id, end=right.id) for left, right in zip(nodes, nodes[1:])]
    _place_layers([[node] for node in nodes], _direction(layout), _main_gap(links))
    return _Placed(nodes, links)


def _cycle(layout: dict[str, Any]) -> _Placed:
    nodes = _nodes(layout)
    if len(nodes) < 3:
        raise _LayoutRefusal("a cycle needs at least 3 nodes")
    if "links" in layout:
        raise _LayoutRefusal("a cycle links its nodes in order; do not send links")
    limits = AUTO_LAYOUT_LIMITS
    biggest = max(math.hypot(node.width, node.height) for node in nodes)
    count = len(nodes)
    radius = max(
        (biggest + limits.cross_gap) / (2 * math.sin(math.pi / count)),
        biggest,
    )
    widest = max(node.width for node in nodes)
    tallest = max(node.height for node in nodes)
    center_x = limits.margin + widest / 2 + radius
    center_y = limits.margin + tallest / 2 + radius
    for index, node in enumerate(nodes):
        angle = -math.pi / 2 + 2 * math.pi * index / count
        node.x = center_x + radius * math.cos(angle) - node.width / 2
        node.y = center_y + radius * math.sin(angle) - node.height / 2
    links = [
        _Link(start=node.id, end=nodes[(index + 1) % count].id)
        for index, node in enumerate(nodes)
    ]
    return _Placed(nodes, links)


def _tree(layout: dict[str, Any]) -> _Placed:
    raw = _items(layout, "nodes")
    nodes = _nodes(layout)
    if "links" in layout:
        raise _LayoutRefusal("a tree links each node to its parent; do not send links")
    known = {node.id for node in nodes}
    parent: dict[str, str | None] = {}
    for index, (item, node) in enumerate(zip(raw, nodes, strict=True)):
        value = _optional_text(item.get("parent"), f"nodes[{index}].parent")
        if value is not None and value not in known:
            raise _LayoutRefusal(f"nodes[{index}].parent names unknown node '{value}'")
        if value == node.id:
            raise _LayoutRefusal(f"node '{node.id}' cannot be its own parent")
        parent[node.id] = value
    roots = [node for node in nodes if parent[node.id] is None]
    if not roots:
        raise _LayoutRefusal("a tree needs one node with no parent")
    children: dict[str, list[_Node]] = {node.id: [] for node in nodes}
    for node in nodes:
        owner = parent[node.id]
        if owner is not None:
            children[owner].append(node)
    direction = _direction(layout)
    down = direction == "down"
    limits = AUTO_LAYOUT_LIMITS
    slot = max((node.width if down else node.height) for node in nodes) + limits.cross_gap
    depth_of: dict[str, int] = {}
    cross_of: dict[str, float] = {}
    next_leaf = [0.0]
    visiting: set[str] = set()

    def place(node: _Node, depth: int) -> None:
        if node.id in visiting or node.id in depth_of:
            raise _LayoutRefusal(f"node '{node.id}' is part of a loop")
        visiting.add(node.id)
        depth_of[node.id] = depth
        kids = children[node.id]
        for kid in kids:
            place(kid, depth + 1)
        if kids:
            cross_of[node.id] = (cross_of[kids[0].id] + cross_of[kids[-1].id]) / 2
        else:
            cross_of[node.id] = next_leaf[0]
            next_leaf[0] += slot
        visiting.discard(node.id)

    for root in roots:
        place(root, 0)
    if len(depth_of) != len(nodes):
        raise _LayoutRefusal("every node must be reachable from a root")
    levels = max(depth_of.values()) + 1
    links = [
        _Link(start=owner, end=node.id)
        for node in nodes
        if (owner := parent[node.id]) is not None
    ]
    gap = _main_gap(links)
    level_depth = [0.0] * levels
    for node in nodes:
        size = node.height if down else node.width
        level_depth[depth_of[node.id]] = max(level_depth[depth_of[node.id]], size)
    level_start = [limits.margin]
    for size in level_depth[:-1]:
        level_start.append(level_start[-1] + size + gap)
    for node in nodes:
        along = limits.margin + cross_of[node.id] + (slot - limits.cross_gap) / 2
        main = level_start[depth_of[node.id]]
        if down:
            node.x, node.y = along - node.width / 2, main
        else:
            node.x, node.y = main, along - node.height / 2
    return _Placed(nodes, links)


def _comparison(layout: dict[str, Any]) -> _Placed:
    columns = _items(layout, "columns")
    if not 2 <= len(columns) <= 3:
        raise _LayoutRefusal("a comparison needs 2 or 3 columns")
    limits = AUTO_LAYOUT_LIMITS
    grid: list[list[_Node]] = []
    seen: set[str] = set()
    for index, column in enumerate(columns):
        where = f"columns[{index}]"
        heading = _Node(
            id=_text(column.get("id"), f"{where}.id"),
            label=_text(column.get("title"), f"{where}.title"),
            step=_optional_text(column.get("step"), f"{where}.step"),
            stroke_width=limits.heading_stroke_width,
        )
        items = column.get("items")
        if not isinstance(items, list) or not items:
            raise _LayoutRefusal(f"{where}.items needs at least one entry")
        cells = [heading]
        for row, item in enumerate(items):
            item_where = f"{where}.items[{row}]"
            if isinstance(item, str):
                item = {"label": item}
            if not isinstance(item, dict):
                raise _LayoutRefusal(f"{item_where} must be text or an object")
            cells.append(
                _Node(
                    id=_optional_text(item.get("id"), f"{item_where}.id")
                    or f"{heading.id}-item-{row + 1}",
                    label=_text(item.get("label"), f"{item_where}.label"),
                    step=_optional_text(item.get("step"), f"{item_where}.step")
                    or heading.step,
                )
            )
        for cell in cells:
            if cell.id in seen:
                raise _LayoutRefusal(f"id '{cell.id}' is used twice")
            seen.add(cell.id)
        grid.append(cells)
    total = sum(len(cells) for cells in grid)
    if total > LAYOUT_LIMITS.max_parts:
        raise _LayoutRefusal(
            f"{total} boxes is too many for a phone screen. Use at most {LAYOUT_LIMITS.max_parts}."
        )
    for cells in grid:
        for cell in cells:
            _size(cell)
    width = max(cell.width for cells in grid for cell in cells)
    for cells in grid:
        for cell in cells:
            _size(cell, min_width=width)
    rows = max(len(cells) for cells in grid)
    heights = [
        max(cells[row].height for cells in grid if row < len(cells)) for row in range(rows)
    ]
    for column, cells in enumerate(grid):
        x = limits.margin + column * (width + limits.cross_gap)
        y = limits.margin
        for row, cell in enumerate(cells):
            cell.x, cell.y = x, y
            cell.height = heights[row]
            y += heights[row] + (limits.cross_gap if row == 0 else limits.cross_gap / 2)
    return _Placed([cell for cells in grid for cell in cells], [])


def _parts(layout: dict[str, Any]) -> _Placed:
    whole_raw = layout.get("whole")
    if not isinstance(whole_raw, dict):
        raise _LayoutRefusal("parts needs a whole with id and label")
    whole = _node({"shape": "ellipse", **whole_raw}, "whole")
    limits = AUTO_LAYOUT_LIMITS
    _size(whole, min_width=limits.whole_min_width, min_height=limits.whole_min_height)
    parts = _nodes(layout)
    if whole.id in {part.id for part in parts}:
        raise _LayoutRefusal(f"id '{whole.id}' is used twice")
    left = parts[0::2]
    right = parts[1::2]
    side_width = max(part.width for part in parts)
    gap = limits.main_gap

    def stack(column: list[_Node]) -> float:
        return sum(part.height for part in column) + limits.cross_gap * (len(column) - 1)

    tallest = max(stack(left), stack(right) if right else 0, whole.height)
    whole.x = limits.margin + side_width + gap
    whole.y = limits.margin + (tallest - whole.height) / 2
    for column, x in ((left, limits.margin), (right, whole.x + whole.width + gap)):
        if not column:
            continue
        y = limits.margin + (tallest - stack(column)) / 2
        for part in column:
            part.x = x + (side_width - part.width if column is left else 0)
            part.y = y
            y += part.height + limits.cross_gap
    links = [_Link(start=part.id, end=whole.id, step=part.step) for part in parts]
    return _Placed([whole, *parts], links)


_PLACERS: dict[str, Callable[[dict[str, Any]], _Placed]] = {
    "flow": _flow,
    "sequence": _sequence,
    "cycle": _cycle,
    "tree": _tree,
    "comparison": _comparison,
    "parts": _parts,
}


# Checks on the placed result.


def _check_steps(placed: _Placed, step_ids: list[str]) -> None:
    known = set(step_ids)
    for node in placed.nodes:
        if node.step is not None and node.step not in known:
            raise _LayoutRefusal(f"node '{node.id}' names unknown step '{node.step}'")
    for link in placed.links:
        if link.step is not None and link.step not in known:
            raise _LayoutRefusal(
                f"link from '{link.start}' to '{link.end}' names unknown step '{link.step}'"
            )


def _check_frame(placed: _Placed, kind: str) -> None:
    right = max(node.x + node.width for node in placed.nodes) + AUTO_LAYOUT_LIMITS.margin
    bottom = max(node.y + node.height for node in placed.nodes) + AUTO_LAYOUT_LIMITS.margin
    if right <= LAYOUT_LIMITS.frame_width and bottom <= LAYOUT_LIMITS.frame_height:
        return
    hint = "Use direction down, " if kind in ("flow", "sequence", "tree") else "Use "
    raise _LayoutRefusal(
        f"the {kind} needs {math.ceil(right)} by {math.ceil(bottom)}, and the drawing area is "
        f"{LAYOUT_LIMITS.frame_width:g} by {LAYOUT_LIMITS.frame_height:g}. "
        f"{hint}fewer nodes, or shorter labels."
    )


# Elements.


def _style() -> dict[str, object]:
    return {"stroke": _STROKE, "fill": None, "stroke_width": _STROKE_WIDTH}


def _box_element(node: _Node) -> dict[str, object]:
    return {
        "id": node.id,
        "kind": node.shape,
        "author": "agent",
        "position": {"x": round(node.x, 2), "y": round(node.y, 2)},
        "size": {"width": round(node.width, 2), "height": round(node.height, 2)},
        "style": {**_style(), "stroke_width": node.stroke_width},
        "label": node.label,
    }


def _edge_point(node: _Node, toward_x: float, toward_y: float) -> tuple[float, float]:
    """Where the line from the node's center toward a point leaves the node."""

    center_x = node.x + node.width / 2
    center_y = node.y + node.height / 2
    dx = toward_x - center_x
    dy = toward_y - center_y
    if dx == 0 and dy == 0:
        return center_x, center_y
    half_width = node.width / 2
    half_height = node.height / 2
    if node.shape == "ellipse":
        scale = 1 / math.sqrt((dx / half_width) ** 2 + (dy / half_height) ** 2)
    else:
        scale = min(
            half_width / abs(dx) if dx else math.inf,
            half_height / abs(dy) if dy else math.inf,
        )
    return center_x + dx * scale, center_y + dy * scale


def _arrow_element(link: _Link, start: _Node, end: _Node) -> dict[str, object]:
    start_x, start_y = _edge_point(start, end.x + end.width / 2, end.y + end.height / 2)
    end_x, end_y = _edge_point(end, start.x + start.width / 2, start.y + start.height / 2)
    left = min(start_x, end_x)
    top = min(start_y, end_y)
    element: dict[str, object] = {
        "id": link.id or f"{link.start}-to-{link.end}",
        "kind": "arrow",
        "author": "agent",
        "position": {"x": round(left, 2), "y": round(top, 2)},
        "size": {
            "width": round(abs(end_x - start_x), 2),
            "height": round(abs(end_y - start_y), 2),
        },
        "style": _style(),
        "start": {"x": round(start_x, 2), "y": round(start_y, 2)},
        "end": {"x": round(end_x, 2), "y": round(end_y, 2)},
        "start_element_id": link.start,
        "end_element_id": link.end,
    }
    if link.label:
        element["label"] = link.label
    if link.bend:
        element["bend"] = link.bend
    return element


def _elements_by_step(placed: _Placed, step_ids: list[str]) -> dict[str, list[dict[str, object]]]:
    first = step_ids[0]
    rank = {step_id: index for index, step_id in enumerate(step_ids)}
    by_id = {node.id: node for node in placed.nodes}
    grouped: dict[str, list[dict[str, object]]] = {step_id: [] for step_id in step_ids}
    for node in placed.nodes:
        grouped[node.step or first].append(_box_element(node))
    for link in placed.links:
        start = by_id[link.start]
        end = by_id[link.end]
        # An arrow appears with the later of the two boxes it joins.
        step = link.step or max(start.step or first, end.step or first, key=rank.__getitem__)
        grouped[step].append(_arrow_element(link, start, end))
    return grouped
