"""Layout checks, labels inside boxes, attached arrows, and placed layouts (WB-17).

These tests never call the model.
"""

import asyncio
import copy
from pathlib import Path

from polaris.auto_layout import LAYOUT_KINDS, expand_layout
from polaris.layout_check import (
    LAYOUT_LIMITS,
    LAYOUT_PROBLEM_KINDS,
    layout_problems,
    layout_score,
    mark_problems,
)
from polaris.teaching import ClaudeTeachingAgent, submit_marks, submit_whiteboard
from polaris.whiteboard import (
    CURRENT_DRAWING_VERSION,
    WHITEBOARD_TOOL_LIMITS,
    apply_marks,
    check_drawing,
    describe_whiteboard,
    readable_description,
)
from test_whiteboard import _answer_drawing, _circle_mark, _element, _mark_action


def _board(*elements: dict[str, object], version: int = CURRENT_DRAWING_VERSION) -> dict[str, object]:
    return {
        "version": version,
        "id": "wb-layout",
        "session_id": "session-1",
        "description": "Two linked boxes.",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": list(elements),
            }
        ],
    }


def _box(element_id: str, x: float, y: float, **fields: object) -> dict[str, object]:
    return _element(
        element_id,
        "rectangle",
        position={"x": x, "y": y},
        size={"width": 160, "height": 60},
        **fields,
    )


def _arrow(element_id: str, start: dict, end: dict, **fields: object) -> dict[str, object]:
    return _element(
        element_id,
        "arrow",
        position={"x": min(start["x"], end["x"]), "y": min(start["y"], end["y"])},
        size={"width": abs(end["x"] - start["x"]), "height": abs(end["y"] - start["y"])},
        start=start,
        end=end,
        **fields,
    )


def _linked() -> dict[str, object]:
    return _board(
        _box("cause", 40, 40, label="Heat"),
        _box("effect", 40, 200, label="Ice melts"),
        _arrow(
            "link",
            {"x": 120, "y": 100},
            {"x": 120, "y": 200},
            start_element_id="cause",
            end_element_id="effect",
            label="causes",
        ),
    )


def _checked(data: dict[str, object]):
    result = check_drawing(data)
    assert result.errors == []
    assert result.whiteboard is not None
    return result.whiteboard


def _kinds(data: dict[str, object]) -> list[str]:
    return [problem.kind for problem in layout_problems(_checked(data))]


# Version 7: labels inside boxes and attached arrows.


def test_a_box_holds_its_label_and_an_arrow_attaches_to_boxes():
    whiteboard = _checked(_linked())

    cause, effect, link = whiteboard.steps[0].elements
    assert cause.label == "Heat"
    assert link.start_element_id == "cause"
    assert link.end_element_id == "effect"
    assert describe_whiteboard(whiteboard).splitlines()[1:] == [
        '- rectangle cause by agent at (40, 40) "Heat"',
        '- rectangle effect by agent at (40, 200) "Ice melts"',
        '- arrow link by agent from cause to effect "causes"',
    ]
    assert readable_description(whiteboard) == "Two linked boxes."


def test_labels_and_attachments_need_version_7():
    older = _linked()
    older["version"] = 6

    result = check_drawing(older)

    assert result.whiteboard is None
    assert any("version 7" in error for error in result.errors)


def test_an_attached_arrow_must_name_a_part_on_the_board():
    data = _linked()
    data["steps"][0]["elements"][2]["end_element_id"] = "nowhere"

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("nowhere" in error for error in result.errors)


def test_absent_version_7_fields_stay_out_of_the_stored_form():
    data = _board(_box("plain", 40, 40))

    dumped = _checked(data).model_dump(mode="json")

    assert "label" not in dumped["steps"][0]["elements"][0]


def test_older_versions_still_open():
    old = _board(_box("plain", 40, 40), version=2)
    old.pop("description")

    assert _checked(old).version == 2


# Layout checks.


def test_a_clean_drawing_has_no_layout_problems():
    assert _kinds(_linked()) == []
    assert layout_score(_checked(_linked())) == {kind: 0 for kind in LAYOUT_PROBLEM_KINDS}


def test_overlapping_shapes_are_found():
    data = _board(_box("left", 40, 40), _box("right", 100, 60))

    problems = layout_problems(_checked(data))

    assert [problem.kind for problem in problems] == ["overlap"]
    assert problems[0].element_ids == ("left", "right")


def test_text_inside_a_box_is_not_an_overlap_but_two_texts_are():
    inside = _board(
        _box("frame", 40, 40),
        _element("caption", "text", text="hi", position={"x": 60, "y": 50}, size={"width": 80, "height": 30}),
    )
    assert _kinds(inside) == []

    stacked = _board(
        _element("first", "text", text="one", position={"x": 40, "y": 40}, size={"width": 80, "height": 30}),
        _element("second", "text", text="two", position={"x": 50, "y": 50}, size={"width": 80, "height": 30}),
    )
    assert _kinds(stacked) == ["overlap"]


def test_a_label_that_does_not_fit_its_box_is_found():
    data = _board(
        _element(
            "tiny",
            "rectangle",
            position={"x": 40, "y": 40},
            size={"width": 60, "height": 40},
            label="Photosynthesis turns light into sugar",
        )
    )

    problems = layout_problems(_checked(data))

    assert [problem.kind for problem in problems] == ["text_spill"]
    assert "tiny" in problems[0].message


def test_text_that_spills_out_of_its_box_is_found():
    data = _board(
        _element(
            "long",
            "text",
            text="A sentence much too long for a narrow box of text",
            position={"x": 40, "y": 40},
            size={"width": 100, "height": 30},
        )
    )

    assert _kinds(data) == ["text_spill"]


def test_a_part_outside_the_drawing_is_found():
    data = _board(_box("far", LAYOUT_LIMITS.frame_width - 20, 40))

    assert _kinds(data) == ["outside"]


def test_an_arrow_end_that_touches_nothing_is_found():
    data = _board(
        _box("only", 40, 40),
        _arrow("loose", {"x": 260, "y": 70}, {"x": 400, "y": 70}),
    )

    problems = layout_problems(_checked(data))

    assert [problem.kind for problem in problems] == ["loose_arrow", "loose_arrow"]
    assert "start" in problems[0].message and "end" in problems[1].message

    touching = _board(
        _box("only", 40, 40),
        _arrow("near", {"x": 205, "y": 70}, {"x": 400, "y": 70}, end_element_id="only"),
    )
    assert _kinds(touching) == []


def test_too_many_parts_for_a_phone_are_found():
    boxes = [
        _element(
            f"dot-{index}",
            "ellipse",
            position={"x": 20 + (index % 8) * 120, "y": 20 + (index // 8) * 120},
            size={"width": 40, "height": 40},
        )
        for index in range(LAYOUT_LIMITS.max_parts + 1)
    ]

    assert _kinds(_board(*boxes)) == ["too_many_parts"]


def test_learner_parts_and_marks_are_never_at_fault():
    data = _board(
        _box("agent-box", 40, 40),
        _box("learner-box", 60, 50, author="learner"),
    )

    assert _kinds(data) == []


# Placed layouts.


def _steps(*ids: str) -> list[dict[str, object]]:
    return [{"id": step_id, "reply_part": f"[[step:{step_id}]]"} for step_id in ids]


def _laid_out(layout: dict[str, object], *step_ids: str) -> dict[str, object]:
    return {
        "version": CURRENT_DRAWING_VERSION,
        "id": "wb-auto",
        "session_id": "session-1",
        "description": "A placed drawing.",
        "steps": _steps(*(step_ids or ("step-1",))),
        "layout": layout,
    }


LAYOUTS: dict[str, dict[str, object]] = {
    "flow": {
        "kind": "flow",
        "nodes": [
            {"id": "sun", "label": "Sunlight"},
            {"id": "leaf", "label": "Leaf"},
            {"id": "sugar", "label": "Sugar"},
            {"id": "growth", "label": "The plant grows taller"},
        ],
        "links": [
            {"from": "sun", "to": "leaf", "label": "hits"},
            {"from": "leaf", "to": "sugar"},
            {"from": "sugar", "to": "growth"},
            {"from": "sun", "to": "sugar"},
        ],
    },
    "sequence": {
        "kind": "sequence",
        "direction": "right",
        "nodes": [{"id": f"s{index}", "label": f"Step {index}"} for index in range(4)],
    },
    "cycle": {
        "kind": "cycle",
        "nodes": [
            {"id": "evaporate", "label": "Evaporation"},
            {"id": "condense", "label": "Condensation"},
            {"id": "rain", "label": "Rain"},
            {"id": "collect", "label": "Collection"},
        ],
    },
    "tree": {
        "kind": "tree",
        "nodes": [
            {"id": "animal", "label": "Animals"},
            {"id": "mammal", "label": "Mammals", "parent": "animal"},
            {"id": "bird", "label": "Birds", "parent": "animal"},
            {"id": "dog", "label": "Dogs", "parent": "mammal"},
            {"id": "cat", "label": "Cats", "parent": "mammal"},
        ],
    },
    "comparison": {
        "kind": "comparison",
        "columns": [
            {"id": "mitosis", "title": "Mitosis", "items": ["Two cells", "Same chromosomes"]},
            {"id": "meiosis", "title": "Meiosis", "items": ["Four cells", "Half the chromosomes"]},
        ],
    },
    "parts": {
        "kind": "parts",
        "whole": {"id": "cell", "label": "Animal cell"},
        "nodes": [
            {"id": "nucleus", "label": "Nucleus"},
            {"id": "mito", "label": "Mitochondria"},
            {"id": "membrane", "label": "Membrane"},
        ],
    },
}


def test_every_layout_kind_is_placed_with_no_layout_problems():
    assert set(LAYOUTS) == set(LAYOUT_KINDS)
    for kind, layout in LAYOUTS.items():
        expanded = expand_layout(_laid_out(layout))
        assert expanded.errors == [], kind
        assert "layout" not in expanded.drawing
        whiteboard = _checked(expanded.drawing)
        assert layout_problems(whiteboard) == [], kind
        boxes = [e for e in whiteboard.steps[0].elements if e.kind in ("rectangle", "ellipse")]
        assert boxes and all(box.label for box in boxes), kind


def test_a_flow_attaches_each_arrow_to_its_boxes():
    expanded = expand_layout(_laid_out(LAYOUTS["flow"]))
    elements = {e["id"]: e for e in expanded.drawing["steps"][0]["elements"]}

    arrow = elements["sun-to-leaf"]
    assert arrow["start_element_id"] == "sun"
    assert arrow["end_element_id"] == "leaf"
    assert arrow["label"] == "hits"
    sun = elements["sun"]
    leaf = elements["leaf"]
    # Stored points sit on the box edges, so the text description matches the picture.
    assert arrow["start"]["y"] == sun["position"]["y"] + sun["size"]["height"]
    assert arrow["end"]["y"] == leaf["position"]["y"]
    assert leaf["position"]["y"] > sun["position"]["y"]


def test_a_layout_part_appears_in_the_step_it_names():
    layout = copy.deepcopy(LAYOUTS["sequence"])
    layout["nodes"][2]["step"] = "step-2"
    layout["nodes"][3]["step"] = "step-2"

    expanded = expand_layout(_laid_out(layout, "step-1", "step-2"))

    first, second = expanded.drawing["steps"]
    assert [e["id"] for e in first["elements"]] == ["s0", "s1", "s0-to-s1"]
    assert [e["id"] for e in second["elements"]] == ["s2", "s3", "s1-to-s2", "s2-to-s3"]


def test_a_layout_keeps_the_steps_own_elements():
    data = _laid_out(LAYOUTS["cycle"])
    extra = _element(
        "formula", "math", latex="x", position={"x": 40, "y": 900}, size={"width": 80, "height": 40}
    )
    data["steps"][0]["elements"] = [extra]

    expanded = expand_layout(data)

    assert expanded.drawing["steps"][0]["elements"][-1] == extra


def test_a_bad_layout_says_what_to_fix():
    cases = {
        "kind must be one of": {"kind": "spiral"},
        "unknown node 'moon'": {
            "kind": "flow",
            "nodes": [{"id": "sun", "label": "Sun"}],
            "links": [{"from": "sun", "to": "moon"}],
        },
        "used twice": {
            "kind": "flow",
            "nodes": [{"id": "a", "label": "A"}, {"id": "a", "label": "B"}],
        },
        "unknown step 'later'": {
            "kind": "flow",
            "nodes": [{"id": "a", "label": "A", "step": "later"}],
        },
        "at least 3 nodes": {"kind": "cycle", "nodes": [{"id": "a", "label": "A"}]},
        "the sequence needs": {
            "kind": "sequence",
            "direction": "right",
            "nodes": [{"id": f"n{i}", "label": "A long label here"} for i in range(8)],
        },
    }
    for expected, layout in cases.items():
        expanded = expand_layout(_laid_out(layout))
        assert expanded.drawing is None
        assert len(expanded.errors) == 1
        assert expanded.errors[0].startswith("layout: ")
        assert expected in expanded.errors[0], expanded.errors


# The teaching tool.


def _store(stored: list[dict]):
    def store(_session_id: str, drawing: dict) -> dict:
        stored.append(drawing)
        return {"id": drawing["id"]}

    return store


def test_the_tool_places_a_layout_and_stores_version_7(tmp_path: Path):
    stored: list[dict] = []
    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session_id, _spec: {"id": "quiz"}, _store(stored))
    args = _laid_out(LAYOUTS["tree"])
    del args["version"], args["session_id"]

    payload = asyncio.run(agent.handle_draw_whiteboard("session-9", args))

    assert payload.get("is_error") is not True, payload
    assert stored[0]["version"] == CURRENT_DRAWING_VERSION
    assert stored[0]["session_id"] == "session-9"
    assert "layout" not in stored[0]


def test_layout_problems_are_refused_while_fixes_remain():
    stored: list[dict] = []
    crowded = _board(_box("left", 40, 40), _box("right", 100, 60))

    first = submit_whiteboard("session-1", crowded, failures=0, store=_store(stored))

    assert stored == []
    assert first.failures == 1
    assert first.tool_result["is_error"] is True
    text = first.tool_result["content"][0]["text"]
    assert "'left' and 'right' overlap" in text
    assert "call draw_whiteboard again" in text


def test_a_drawing_with_only_layout_problems_is_shown_once_fixes_run_out():
    stored: list[dict] = []
    crowded = _board(_box("left", 40, 40), _box("right", 100, 60))
    limit = WHITEBOARD_TOOL_LIMITS.max_fix_attempts

    last = submit_whiteboard("session-1", crowded, failures=limit, store=_store(stored))

    assert len(stored) == 1
    assert last.failures == limit
    assert last.tool_result.get("is_error") is not True
    text = last.tool_result["content"][0]["text"]
    assert "still has layout problems" in text
    assert "Do not redraw it this turn" in text


def test_a_new_drawing_without_a_description_is_refused():
    stored: list[dict] = []
    data = _linked()
    del data["description"]

    result = submit_whiteboard("session-1", data, failures=0, store=_store(stored))

    assert stored == []
    assert "description is required" in result.tool_result["content"][0]["text"]


# Marks.


def _marked(*marks: dict[str, object]):
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None
    result = apply_marks(stored, _mark_action(list(marks)))
    assert result.errors == []
    assert result.whiteboard is not None
    return result.whiteboard


def _mark(mark_id: str, kind: str, **fields: object) -> dict[str, object]:
    base = _circle_mark(id=mark_id, mark=kind)
    base.update(fields)
    return base


def test_well_placed_marks_have_no_problems():
    whiteboard = _marked(
        _mark("circle", "circle"),
        _mark(
            "pointer",
            "arrow",
            start={"x": 200, "y": 120},
            end={"x": 110, "y": 70},
            position={"x": 110, "y": 70},
            size={"width": 90, "height": 50},
        ),
        _mark(
            "note",
            "note",
            text="Check the sign",
            position={"x": 140, "y": 40},
            size={"width": 200, "height": 60},
        ),
    )

    assert mark_problems(whiteboard, ["circle", "pointer", "note"]) == []


def test_misplaced_marks_are_found():
    whiteboard = _marked(
        _mark("far-circle", "circle", position={"x": 400, "y": 400}),
        _mark(
            "short-arrow",
            "arrow",
            start={"x": 400, "y": 300},
            end={"x": 300, "y": 300},
            position={"x": 300, "y": 300},
            size={"width": 100, "height": 1},
        ),
        _mark(
            "cover",
            "note",
            text="Here",
            position={"x": 40, "y": 50},
            size={"width": 120, "height": 60},
        ),
        _mark(
            "tiny",
            "note",
            text="A long explanation of the mistake",
            position={"x": 400, "y": 40},
            size={"width": 60, "height": 30},
        ),
    )

    problems = mark_problems(whiteboard, ["far-circle", "short-arrow", "cover", "tiny"])

    assert [(problem.kind, problem.element_ids) for problem in problems] == [
        ("misplaced_mark", ("far-circle",)),
        ("misplaced_mark", ("short-arrow",)),
        ("misplaced_mark", ("cover",)),
        ("text_spill", ("tiny",)),
    ]
    assert "covers the learner's drawing ('answer-1')" in problems[2].message


def test_misplaced_marks_are_refused_while_fixes_remain():
    stored: list[dict] = []
    far = _mark("far-circle", "circle", position={"x": 400, "y": 400})

    def preview(_session_id: str, _action: dict):
        return _marked(far)

    def store(_session_id: str, action: dict) -> dict:
        stored.append(action)
        return {"id": "wb-1"}

    first = submit_marks(
        "session-1", _mark_action([far]), failures=0, store=store, preview=preview
    )
    last = submit_marks(
        "session-1",
        _mark_action([far]),
        failures=WHITEBOARD_TOOL_LIMITS.max_fix_attempts,
        store=store,
        preview=preview,
    )

    assert first.tool_result["is_error"] is True
    assert "does not surround 'answer-1'" in first.tool_result["content"][0]["text"]
    assert "call mark_whiteboard again" in first.tool_result["content"][0]["text"]
    assert len(stored) == 1
    assert "still have layout problems" in last.tool_result["content"][0]["text"]
