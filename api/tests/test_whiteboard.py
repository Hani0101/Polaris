"""The backend checks whiteboard drawing data before it can be drawn (WB-05)."""

import copy
import math

from polaris.whiteboard import (
    DESCRIBED_DRAWING_VERSION,
    DRAWING_FORMAT_VERSION,
    DRAWING_LIMITS,
    MARKED_DRAWING_VERSION,
    apply_marks,
    check_drawing,
    check_learner_drawing,
    describe_pointed,
    describe_whiteboard,
    element_count,
    pointed_element_errors,
    readable_description,
    simpler_count_errors,
)


def _element(element_id: str, kind: str, **fields: object) -> dict[str, object]:
    element: dict[str, object] = {
        "id": element_id,
        "kind": kind,
        "author": "agent",
        "position": {"x": 10, "y": 20},
        "size": {"width": 80, "height": 40},
        "style": {"stroke": "#1f3a5f", "fill": "#f4efe6", "stroke_width": 2},
    }
    element.update(fields)
    return element


def valid_whiteboard() -> dict[str, object]:
    """One whiteboard that uses every element kind this version allows."""

    return {
        "version": 2,
        "id": "wb-1",
        "session_id": "session-1",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": [
                    _element("rect-1", "rectangle"),
                    _element("ellipse-1", "ellipse", author="learner"),
                    _element(
                        "arrow-1",
                        "arrow",
                        start={"x": 10, "y": 20},
                        end={"x": 90, "y": 60},
                    ),
                    _element(
                        "line-1",
                        "line",
                        start={"x": 12, "y": 22},
                        end={"x": 70, "y": 22},
                    ),
                    _element("text-1", "text", text="half"),
                    _element(
                        "freehand-1",
                        "freehand",
                        points=[{"x": 14, "y": 24}, {"x": 40, "y": 50}],
                    ),
                ],
            },
            {
                "id": "step-2",
                "reply_part": "[[step:step-2]]",
                "elements": [
                    _element("rect-2", "rectangle", author="learner"),
                ],
            },
        ],
    }


def test_a_valid_whiteboard_passes_the_check():
    result = check_drawing(valid_whiteboard())

    assert result.errors == []
    assert result.whiteboard is not None
    whiteboard = result.whiteboard
    assert whiteboard.version == DRAWING_FORMAT_VERSION
    assert whiteboard.comments == []
    assert whiteboard.id == "wb-1"
    assert whiteboard.session_id == "session-1"
    assert [step.id for step in whiteboard.steps] == ["step-1", "step-2"]
    assert [step.reply_part for step in whiteboard.steps] == [
        "[[step:step-1]]",
        "[[step:step-2]]",
    ]
    first = whiteboard.steps[0].elements
    assert [element.kind for element in first] == [
        "rectangle",
        "ellipse",
        "arrow",
        "line",
        "text",
        "freehand",
    ]
    assert first[1].author == "learner"
    assert first[2].start.x == 10
    assert first[4].text == "half"
    assert [(point.x, point.y) for point in first[5].points] == [(14, 24), (40, 50)]


def test_a_reply_part_must_name_its_step():
    """A step is tied to the reply by [[step:<that step's id>]], and nothing else."""

    prose = valid_whiteboard()
    prose["steps"][0]["reply_part"] = "The agent draws the idea."
    prose_result = check_drawing(prose)

    assert prose_result.whiteboard is None
    assert any("[[step:step-1]]" in error for error in prose_result.errors)

    other_step = valid_whiteboard()
    other_step["steps"][0]["reply_part"] = "[[step:step-2]]"
    other_result = check_drawing(other_step)

    assert other_result.whiteboard is None
    assert any("[[step:step-1]]" in error for error in other_result.errors)


def test_an_unknown_element_kind_is_rejected():
    data = valid_whiteboard()
    data["steps"][0]["elements"][0]["kind"] = "triangle"

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any(
        "unknown element kind" in error and "triangle" in error
        for error in result.errors
    )


def test_a_missing_field_is_rejected():
    data = valid_whiteboard()
    del data["steps"][0]["elements"][0]["author"]

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("author" in error and "missing" in error for error in result.errors)


def test_duplicate_ids_are_rejected():
    data = valid_whiteboard()
    data["steps"][1]["elements"][0]["id"] = "rect-1"

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("duplicate" in error and "rect-1" in error for error in result.errors)


def test_a_non_finite_number_is_rejected():
    data = valid_whiteboard()
    data["steps"][0]["elements"][0]["position"]["x"] = math.nan

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("finite" in error for error in result.errors)


def test_an_out_of_range_size_or_coordinate_is_rejected():
    data = valid_whiteboard()
    data["steps"][0]["elements"][0]["position"]["y"] = (
        DRAWING_LIMITS.max_coordinate + 1
    )
    data["steps"][0]["elements"][0]["size"]["width"] = DRAWING_LIMITS.min_size - 1

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any(
        "position.y" in error and "out of range" in error for error in result.errors
    )
    assert any(
        "size.width" in error and "out of range" in error for error in result.errors
    )


def test_text_that_is_too_long_is_rejected():
    data = valid_whiteboard()
    data["steps"][0]["elements"][4]["text"] = "a" * (
        DRAWING_LIMITS.max_text_length + 1
    )

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("too long" in error for error in result.errors)


def test_bad_drawing_data_is_refused_and_not_passed_on():
    """WB-05: drawing data that fails the check is not passed on to be drawn."""

    produced = valid_whiteboard()
    produced["steps"][0]["elements"][0]["kind"] = "triangle"

    result = check_drawing(produced)

    assert result.errors
    assert result.whiteboard is None

    refused = check_drawing(None)
    assert refused.errors
    assert refused.whiteboard is None


def _stored():
    result = check_drawing(valid_whiteboard())
    assert result.whiteboard is not None
    return result.whiteboard


def test_an_older_drawing_version_is_rejected():
    data = valid_whiteboard()
    data["version"] = DRAWING_FORMAT_VERSION - 1

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any(str(DRAWING_FORMAT_VERSION) in error for error in result.errors)


def test_a_comment_about_an_element_or_at_a_position_passes():
    data = valid_whiteboard()
    data["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "why this box",
            "element_id": "rect-1",
        },
        {
            "id": "comment-2",
            "author": "learner",
            "text": "here",
            "position": {"x": 30, "y": 40},
        },
    ]

    result = check_drawing(data)

    assert result.errors == []
    assert result.whiteboard is not None
    about, placed = result.whiteboard.comments
    assert about.author == "learner"
    assert about.element_id == "rect-1"
    assert about.position is None
    assert about.text == "why this box"
    assert placed.position is not None
    assert (placed.position.x, placed.position.y) == (30, 40)
    assert placed.element_id is None


def test_a_comment_needs_a_position_or_an_element_id():
    data = valid_whiteboard()
    data["comments"] = [
        {"id": "comment-1", "author": "learner", "text": "why"},
        {
            "id": "comment-2",
            "author": "learner",
            "text": "both",
            "element_id": "rect-1",
            "position": {"x": 1, "y": 2},
        },
    ]

    result = check_drawing(data)

    assert result.whiteboard is None
    assert sum("position or an element id" in error for error in result.errors) == 2


def test_a_comment_about_an_unknown_element_is_rejected():
    data = valid_whiteboard()
    data["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "why",
            "element_id": "missing",
        }
    ]

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("unknown element" in error and "missing" in error for error in result.errors)


def test_a_blank_comment_is_rejected():
    data = valid_whiteboard()
    data["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "   ",
            "element_id": "rect-1",
        }
    ]

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("blank" in error for error in result.errors)


def test_a_comment_id_cannot_repeat_an_element_id():
    data = valid_whiteboard()
    data["comments"] = [
        {
            "id": "rect-1",
            "author": "learner",
            "text": "why",
            "element_id": "text-1",
        }
    ]

    result = check_drawing(data)

    assert result.whiteboard is None
    assert any("duplicate" in error and "rect-1" in error for error in result.errors)


def test_a_learner_element_is_kept_with_author_learner():
    incoming = valid_whiteboard()
    incoming["steps"][1]["elements"].append(
        _element(
            "learner-box",
            "rectangle",
            author="learner",
            position={"x": 120, "y": 40},
        )
    )

    result = check_learner_drawing(_stored(), incoming)

    assert result.errors == []
    assert result.whiteboard is not None
    added = result.whiteboard.steps[1].elements[-1]
    assert added.id == "learner-box"
    assert added.author == "learner"
    assert (added.position.x, added.position.y) == (120, 40)


def test_a_learner_cannot_change_or_remove_an_agent_element():
    moved = valid_whiteboard()
    moved["steps"][0]["elements"][0]["position"] = {"x": 400, "y": 400}
    removed = valid_whiteboard()
    del removed["steps"][0]["elements"][0]

    moved_result = check_learner_drawing(_stored(), moved)
    removed_result = check_learner_drawing(_stored(), removed)

    assert moved_result.whiteboard is None
    assert any(
        "rect-1" in error and "changed" in error for error in moved_result.errors
    )
    assert removed_result.whiteboard is None
    assert any(
        "rect-1" in error and "removed" in error for error in removed_result.errors
    )


def test_bad_learner_data_is_refused_by_the_check():
    incoming = valid_whiteboard()
    incoming["comments"] = [
        {"id": "comment-1", "author": "learner", "text": "why"}
    ]
    incoming["steps"][0]["elements"][0]["kind"] = "triangle"

    result = check_learner_drawing(_stored(), incoming)

    assert result.whiteboard is None
    assert result.errors
    assert any("position or an element id" in error for error in result.errors)


def test_describe_whiteboard_names_kinds_labels_positions_and_comments():
    data = valid_whiteboard()
    data["steps"] = [
        {
            "id": "step-1",
            "reply_part": "[[step:step-1]]",
            "elements": [
                _element("rect-1", "rectangle"),
                _element("text-1", "text", text="half", author="learner"),
            ],
        }
    ]
    data["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "why this box",
            "element_id": "rect-1",
        },
        {
            "id": "comment-2",
            "author": "learner",
            "text": "here",
            "position": {"x": 30, "y": 40},
        },
    ]
    whiteboard = check_drawing(data).whiteboard
    assert whiteboard is not None

    assert describe_whiteboard(whiteboard) == (
        "Whiteboard wb-1:\n"
        "- rectangle rect-1 by agent at (10, 20)\n"
        '- text text-1 by learner at (10, 20) "half"\n'
        '- comment comment-1 by learner about rect-1: "why this box"\n'
        '- comment comment-2 by learner at (30, 40): "here"'
    )


def test_describe_pointed_uses_the_whiteboard_text_form():
    data = valid_whiteboard()
    data["steps"] = [
        {
            "id": "step-1",
            "reply_part": "[[step:step-1]]",
            "elements": [
                _element("rect-1", "rectangle"),
                _element("text-1", "text", text="half", author="learner"),
            ],
        }
    ]
    whiteboard = check_drawing(data).whiteboard
    assert whiteboard is not None

    assert describe_pointed(whiteboard, ["rect-1", "text-1"]) == (
        "The learner pointed at these parts of whiteboard wb-1:\n"
        "- rectangle rect-1 by agent at (10, 20)\n"
        '- text text-1 by learner at (10, 20) "half"'
    )


def _learner_elements(whiteboard) -> list[dict[str, object]]:
    return [
        element.model_dump(mode="json")
        for step in whiteboard.steps
        for element in step.elements
        if element.author == "learner"
    ]


def _answer_drawing() -> dict[str, object]:
    """A version 2 whiteboard whose learner element is the answer being marked."""

    return {
        "version": 2,
        "id": "wb-1",
        "session_id": "session-1",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": [
                    _element(
                        "answer-1",
                        "rectangle",
                        author="learner",
                        position={"x": 40, "y": 50},
                        size={"width": 70, "height": 30},
                    ),
                ],
            }
        ],
        "comments": [
            {
                "id": "comment-1",
                "author": "learner",
                "text": "my answer",
                "element_id": "answer-1",
            }
        ],
    }


def _circle_mark(**fields: object) -> dict[str, object]:
    mark: dict[str, object] = {
        "id": "mark-1",
        "kind": "mark",
        "mark": "circle",
        "author": "agent",
        "target_element_id": "answer-1",
        "position": {"x": 30, "y": 40},
        "size": {"width": 100, "height": 80},
        "style": {"stroke": "#e03131", "fill": None, "stroke_width": 2},
    }
    mark.update(fields)
    return mark


def _mark_action(marks: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "whiteboard_id": "wb-1",
        "step_id": "step-mark",
        "reply_part": "[[step:step-mark]]",
        "marks": marks if marks is not None else [_circle_mark()],
    }


def test_a_mark_is_version_3_and_targets_a_learner_element():
    """Version 2 still opens. A mark is stored only on version 3."""

    still_opens = check_drawing(valid_whiteboard())
    assert still_opens.errors == []
    assert still_opens.whiteboard is not None
    assert still_opens.whiteboard.version == DRAWING_FORMAT_VERSION

    too_old = _answer_drawing()
    too_old["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    refused = check_drawing(too_old)
    assert refused.whiteboard is None
    assert any("version 3" in error for error in refused.errors)

    marked = copy.deepcopy(too_old)
    marked["version"] = MARKED_DRAWING_VERSION
    result = check_drawing(marked)
    assert result.errors == []
    assert result.whiteboard is not None
    mark = result.whiteboard.steps[-1].elements[0]
    assert mark.kind == "mark"
    assert mark.mark == "circle"
    assert mark.author == "agent"
    assert mark.target_element_id == "answer-1"

    agent_target = copy.deepcopy(marked)
    agent_target["steps"][0]["elements"][0]["author"] = "agent"
    agent_target["steps"][0]["elements"][0]["id"] = "frame-1"
    agent_target["steps"][1]["elements"][0]["target_element_id"] = "frame-1"
    agent_target["comments"] = []
    missed = check_drawing(agent_target)
    assert missed.whiteboard is None
    assert any("learner element" in error for error in missed.errors)


def test_marks_leave_every_learner_element_and_comment_unchanged():
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None
    before_elements = _learner_elements(stored)
    before_comments = [comment.model_dump(mode="json") for comment in stored.comments]

    result = apply_marks(stored, _mark_action())

    assert result.errors == []
    assert result.whiteboard is not None
    assert result.whiteboard.version == MARKED_DRAWING_VERSION
    assert _learner_elements(result.whiteboard) == before_elements
    assert [
        comment.model_dump(mode="json") for comment in result.whiteboard.comments
    ] == before_comments
    added = result.whiteboard.steps[-1]
    assert added.id == "step-mark"
    assert added.reply_part == "[[step:step-mark]]"
    assert [element.kind for element in added.elements] == ["mark"]
    assert [step.id for step in result.whiteboard.steps] == ["step-1", "step-mark"]


def test_an_agent_action_that_edits_a_learner_element_is_refused():
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None

    edited = _answer_drawing()
    edited["version"] = MARKED_DRAWING_VERSION
    edited["steps"][0]["elements"][0]["position"] = {"x": 9, "y": 9}
    edited["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    changed = apply_marks(stored, edited)
    assert changed.whiteboard is None
    assert any(
        "answer-1" in error and "changed" in error for error in changed.errors
    )

    removed = _answer_drawing()
    removed["version"] = MARKED_DRAWING_VERSION
    removed["steps"][0]["elements"] = []
    removed["comments"] = []
    removed["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark(target_element_id="answer-1")],
        }
    )
    deleted = apply_marks(stored, removed)
    assert deleted.whiteboard is None
    assert any(
        "answer-1" in error and "removed" in error for error in deleted.errors
    )

    comment_gone = _answer_drawing()
    comment_gone["version"] = MARKED_DRAWING_VERSION
    comment_gone["comments"] = []
    comment_gone["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    dropped = apply_marks(stored, comment_gone)
    assert dropped.whiteboard is None
    assert any(
        "comment-1" in error and "removed" in error for error in dropped.errors
    )


def test_arrow_and_note_marks_name_their_target():
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None
    arrow = _circle_mark(
        id="mark-arrow",
        mark="arrow",
        start={"x": 30, "y": 40},
        end={"x": 80, "y": 70},
    )
    note = _circle_mark(
        id="mark-note",
        mark="note",
        text="check the sign",
    )
    result = apply_marks(stored, _mark_action([arrow, note]))

    assert result.errors == []
    assert result.whiteboard is not None
    kinds = [element.mark for element in result.whiteboard.steps[-1].elements]
    assert kinds == ["arrow", "note"]
    assert describe_whiteboard(result.whiteboard) == (
        "Whiteboard wb-1:\n"
        "- rectangle answer-1 by learner at (40, 50)\n"
        "- mark arrow mark-arrow by agent on answer-1 at (30, 40)\n"
        "- mark note mark-note by agent on answer-1 at (30, 40) "
        '"check the sign"\n'
        '- comment comment-1 by learner about answer-1: "my answer"'
    )


def test_a_learner_cannot_change_or_remove_a_mark():
    stored_result = apply_marks(
        check_drawing(_answer_drawing()).whiteboard, _mark_action()
    )
    assert stored_result.whiteboard is not None
    stored = stored_result.whiteboard
    incoming = stored.model_dump(mode="json")
    incoming["steps"][-1]["elements"][0]["position"] = {"x": 400, "y": 400}
    moved = check_learner_drawing(stored, incoming)
    assert moved.whiteboard is None
    assert any("mark-1" in error and "changed" in error for error in moved.errors)

    removed = stored.model_dump(mode="json")
    removed["steps"][-1]["elements"] = []
    gone = check_learner_drawing(stored, removed)
    assert gone.whiteboard is None
    assert any("mark-1" in error and "removed" in error for error in gone.errors)


def _described_drawing() -> dict[str, object]:
    """A version 4 whiteboard whose description is what a screen reader reads."""

    return {
        "version": DESCRIBED_DRAWING_VERSION,
        "id": "wb-1",
        "session_id": "session-1",
        "description": "Two boxes show one half of a whole.",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": [_element("rect-1", "rectangle")],
            }
        ],
    }


def test_a_version_4_whiteboard_without_a_description_is_refused():
    missing = _described_drawing()
    del missing["description"]

    result = check_drawing(missing)

    assert result.whiteboard is None
    assert any("description" in error for error in result.errors)


def test_an_empty_or_too_long_description_is_refused():
    empty = _described_drawing()
    empty["description"] = "   "
    blank = check_drawing(empty)
    assert blank.whiteboard is None
    assert any("description" in error for error in blank.errors)

    too_long = _described_drawing()
    too_long["description"] = "a" * (DRAWING_LIMITS.max_description_length + 1)
    refused = check_drawing(too_long)
    assert refused.whiteboard is None
    assert any("too long" in error for error in refused.errors)

    accepted = _described_drawing()
    accepted["description"] = "a" * DRAWING_LIMITS.max_description_length
    assert check_drawing(accepted).errors == []
    assert DRAWING_LIMITS.max_description_length != DRAWING_LIMITS.max_text_length


def test_version_2_and_3_drawings_without_a_description_still_pass():
    older = check_drawing(valid_whiteboard())
    assert older.errors == []
    assert older.whiteboard is not None
    assert older.whiteboard.version == DRAWING_FORMAT_VERSION
    assert older.whiteboard.description is None

    marked = _answer_drawing()
    marked["version"] = MARKED_DRAWING_VERSION
    marked["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    result = check_drawing(marked)
    assert result.errors == []
    assert result.whiteboard is not None
    assert result.whiteboard.version == MARKED_DRAWING_VERSION
    assert result.whiteboard.description is None


def test_learner_changes_update_the_description():
    """The stored description stays. Learner shapes and comments are appended in code."""

    described = _described_drawing()
    described["steps"][0]["elements"].append(
        _element("box-2", "rectangle", author="learner")
    )
    described["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "my answer",
            "element_id": "box-2",
        }
    ]
    whiteboard = check_drawing(described).whiteboard
    assert whiteboard is not None
    assert whiteboard.description == "Two boxes show one half of a whole."
    assert readable_description(whiteboard) == (
        "Two boxes show one half of a whole. "
        'Learner added 1 shape and 1 comment: a rectangle, "my answer".'
    )

    incoming = whiteboard.model_dump(mode="json")
    incoming["description"] = "The learner rewrote this."
    incoming["version"] = DRAWING_FORMAT_VERSION
    kept = check_learner_drawing(whiteboard, incoming)
    assert kept.errors == []
    assert kept.whiteboard is not None
    assert kept.whiteboard.description == "Two boxes show one half of a whole."
    assert kept.whiteboard.version == DESCRIBED_DRAWING_VERSION

    omitted = whiteboard.model_dump(mode="json")
    del omitted["description"]
    kept_omitted = check_learner_drawing(whiteboard, omitted)
    assert kept_omitted.errors == []
    assert kept_omitted.whiteboard is not None
    assert kept_omitted.whiteboard.description == "Two boxes show one half of a whole."

    older = check_drawing(valid_whiteboard()).whiteboard
    assert older is not None
    assert readable_description(older) == (
        'A rectangle, an ellipse, an arrow, a line, text reading "half", '
        "a freehand line, and a rectangle. "
        "Learner added 2 shapes: an ellipse, a rectangle."
    )


def test_marks_keep_a_stored_description_and_do_not_invent_one():
    described = _answer_drawing()
    described["version"] = DESCRIBED_DRAWING_VERSION
    described["description"] = "The learner's box is the answer."
    stored = check_drawing(described).whiteboard
    assert stored is not None

    marked = apply_marks(stored, _mark_action())
    assert marked.errors == []
    assert marked.whiteboard is not None
    assert marked.whiteboard.version == DESCRIBED_DRAWING_VERSION
    assert marked.whiteboard.description == "The learner's box is the answer."

    carried = _answer_drawing()
    carried["description"] = "The learner's box is the answer."
    version_2 = check_drawing(carried).whiteboard
    assert version_2 is not None
    bumped = apply_marks(version_2, _mark_action())
    assert bumped.errors == []
    assert bumped.whiteboard is not None
    assert bumped.whiteboard.version == DESCRIBED_DRAWING_VERSION
    assert bumped.whiteboard.description == "The learner's box is the answer."

    plain = apply_marks(check_drawing(_answer_drawing()).whiteboard, _mark_action())
    assert plain.whiteboard is not None
    assert plain.whiteboard.version == MARKED_DRAWING_VERSION
    assert plain.whiteboard.description is None


def test_a_screen_reader_reads_the_drawing():
    """Scenario: a screen reader reads the drawing [WB-10]."""

    whiteboard = check_drawing(_described_drawing()).whiteboard
    assert whiteboard is not None

    assert readable_description(whiteboard) == "Two boxes show one half of a whole."
    assert describe_whiteboard(whiteboard).startswith("Whiteboard wb-1:")


def test_pointed_element_errors_name_unknown_and_repeated_ids():
    data = valid_whiteboard()
    data["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "why this box",
            "element_id": "rect-1",
        }
    ]
    whiteboard = check_drawing(data).whiteboard
    assert whiteboard is not None

    assert pointed_element_errors(whiteboard, ["rect-1"]) == []
    assert pointed_element_errors(whiteboard, ["shape:rect-1"]) == [
        "element 'shape:rect-1' is not on that whiteboard"
    ]
    assert pointed_element_errors(whiteboard, ["comment-1"]) == [
        "element 'comment-1' is not on that whiteboard"
    ]
    assert pointed_element_errors(whiteboard, ["rect-1", "rect-1"]) == [
        "element 'rect-1' is listed more than once"
    ]
    assert pointed_element_errors(whiteboard, []) == ["needs at least one element"]


def _counted_drawing(count: int, **fields: object) -> dict[str, object]:
    """A version 4 redraw with `count` elements and a link to wb-1."""

    data: dict[str, object] = {
        "version": DESCRIBED_DRAWING_VERSION,
        "id": "wb-simple",
        "session_id": "session-1",
        "description": "One box stands for the whole.",
        "simplifies": "wb-1",
        "steps": [
            {
                "id": "step-simple",
                "reply_part": "[[step:step-simple]]",
                "elements": [
                    _element(f"box-{index}", "rectangle") for index in range(count)
                ],
            }
        ],
    }
    data.update(fields)
    return data


def test_a_simpler_whiteboard_has_fewer_elements_and_links_to_the_original():
    original = check_drawing(valid_whiteboard()).whiteboard
    assert original is not None
    assert element_count(original) == 7
    assert "simplifies" not in original.model_dump(mode="json")

    result = check_drawing(_counted_drawing(1))

    assert result.errors == []
    assert result.whiteboard is not None
    assert result.whiteboard.version == DESCRIBED_DRAWING_VERSION
    assert result.whiteboard.simplifies == "wb-1"
    assert element_count(result.whiteboard) == 1
    assert simpler_count_errors(original, result.whiteboard) == []
    assert describe_whiteboard(result.whiteboard).endswith(
        "Simpler version of whiteboard wb-1."
    )


def test_a_simpler_whiteboard_with_the_same_or_more_elements_is_refused():
    original = check_drawing(valid_whiteboard()).whiteboard
    assert original is not None

    same = check_drawing(_counted_drawing(7))
    more = check_drawing(_counted_drawing(8, id="wb-more"))
    assert same.whiteboard is not None
    assert more.whiteboard is not None

    assert simpler_count_errors(original, same.whiteboard) == [
        "a simpler whiteboard needs fewer elements than the original"
    ]
    assert simpler_count_errors(original, more.whiteboard) == [
        "a simpler whiteboard needs fewer elements than the original"
    ]


def test_a_simpler_whiteboard_with_zero_elements_is_refused():
    original = check_drawing(valid_whiteboard()).whiteboard
    assert original is not None
    empty = _counted_drawing(0)
    empty["comments"] = [
        {
            "id": "comment-1",
            "author": "agent",
            "text": "still empty",
            "position": {"x": 4, "y": 8},
        }
    ]
    result = check_drawing(empty)
    assert result.whiteboard is not None

    assert simpler_count_errors(original, result.whiteboard) == [
        "a simpler whiteboard needs at least one element"
    ]


def test_element_count_includes_marks_and_skips_comments():
    stored = check_drawing(_answer_drawing()).whiteboard
    assert stored is not None
    assert element_count(stored) == 1
    marked = apply_marks(stored, _mark_action())
    assert marked.whiteboard is not None
    assert element_count(marked.whiteboard) == 2

    same_as_marks = check_drawing(_counted_drawing(2))
    fewer_than_marks = check_drawing(_counted_drawing(1, id="wb-fewer"))
    assert same_as_marks.whiteboard is not None
    assert fewer_than_marks.whiteboard is not None
    assert simpler_count_errors(marked.whiteboard, same_as_marks.whiteboard) == [
        "a simpler whiteboard needs fewer elements than the original"
    ]
    assert simpler_count_errors(marked.whiteboard, fewer_than_marks.whiteboard) == []


def test_a_learner_save_cannot_replace_simplifies():
    stored = check_drawing(_counted_drawing(1)).whiteboard
    assert stored is not None
    incoming = stored.model_dump(mode="json")
    incoming["simplifies"] = "wb-other"
    replaced = check_learner_drawing(stored, incoming)
    assert replaced.errors == []
    assert replaced.whiteboard is not None
    assert replaced.whiteboard.simplifies == "wb-1"

    dropped = dict(incoming)
    dropped.pop("simplifies")
    kept = check_learner_drawing(stored, dropped)
    assert kept.errors == []
    assert kept.whiteboard is not None
    assert kept.whiteboard.simplifies == "wb-1"


def test_simplifies_must_name_another_version_4_whiteboard():
    same_id = _counted_drawing(1, id="wb-1", simplifies="wb-1")
    refused = check_drawing(same_id)
    assert refused.whiteboard is None
    assert any("another whiteboard" in error for error in refused.errors)

    older = _counted_drawing(1)
    older["version"] = DRAWING_FORMAT_VERSION
    version = check_drawing(older)
    assert version.whiteboard is None
    assert any("version 4" in error for error in version.errors)


def _formula_drawing() -> dict[str, object]:
    """A version 5 whiteboard with one formula and one code block."""

    return {
        "version": 5,
        "id": "wb-formula",
        "session_id": "session-1",
        "description": "The area of a circle.",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": [
                    _element("formula-1", "math", latex=r"A = \pi r^{2}"),
                    _element(
                        "snippet-1",
                        "code",
                        language="python",
                        code="def area(r):\n    return r * r",
                    ),
                ],
            }
        ],
    }


def test_math_and_code_elements_pass_the_check():
    """WB-12: a formula and a code block are elements, not hand-drawn shapes."""

    result = check_drawing(_formula_drawing())

    assert result.errors == []
    assert result.whiteboard is not None
    assert result.whiteboard.version == 5
    formula, snippet = result.whiteboard.steps[0].elements
    assert formula.kind == "math"
    assert formula.author == "agent"
    assert formula.latex == r"A = \pi r^{2}"
    assert snippet.kind == "code"
    assert snippet.author == "agent"
    assert snippet.language == "python"
    assert snippet.code == "def area(r):\n    return r * r"


def test_invalid_latex_is_refused_and_does_not_raise():
    drawing = _formula_drawing()
    drawing["steps"][0]["elements"] = [
        _element("formula-1", "math", latex=r"\frac{1}{2")
    ]

    result = check_drawing(drawing)

    assert result.whiteboard is None
    assert any("LaTeX" in error for error in result.errors)


def test_blank_or_overlong_math_and_code_are_refused():
    blank_latex = _formula_drawing()
    blank_latex["steps"][0]["elements"] = [_element("formula-1", "math", latex="   ")]
    blank = check_drawing(blank_latex)
    assert blank.whiteboard is None
    assert any("latex" in error for error in blank.errors)

    long_latex = _formula_drawing()
    long_latex["steps"][0]["elements"] = [
        _element("formula-1", "math", latex="a" * (DRAWING_LIMITS.max_latex_length + 1))
    ]
    too_long = check_drawing(long_latex)
    assert too_long.whiteboard is None
    assert any("too long" in error for error in too_long.errors)

    blank_language = _formula_drawing()
    blank_language["steps"][0]["elements"] = [
        _element("snippet-1", "code", language="  ", code="return 1")
    ]
    empty_name = check_drawing(blank_language)
    assert empty_name.whiteboard is None
    assert any("language" in error for error in empty_name.errors)

    long_language = _formula_drawing()
    long_language["steps"][0]["elements"] = [
        _element(
            "snippet-1",
            "code",
            language="p" * (DRAWING_LIMITS.max_language_length + 1),
            code="return 1",
        )
    ]
    long_name = check_drawing(long_language)
    assert long_name.whiteboard is None
    assert any("too long" in error for error in long_name.errors)

    blank_code = _formula_drawing()
    blank_code["steps"][0]["elements"] = [
        _element("snippet-1", "code", language="python", code="  ")
    ]
    empty_code = check_drawing(blank_code)
    assert empty_code.whiteboard is None
    assert any("code" in error for error in empty_code.errors)

    long_code = _formula_drawing()
    long_code["steps"][0]["elements"] = [
        _element(
            "snippet-1",
            "code",
            language="python",
            code="x" * (DRAWING_LIMITS.max_code_length + 1),
        )
    ]
    huge = check_drawing(long_code)
    assert huge.whiteboard is None
    assert any("too long" in error for error in huge.errors)

    new_language = _formula_drawing()
    new_language["steps"][0]["elements"][1]["language"] = "zig"
    assert check_drawing(new_language).errors == []


def test_a_drawing_with_math_or_code_must_be_version_5():
    too_old = _formula_drawing()
    too_old["version"] = DESCRIBED_DRAWING_VERSION
    refused = check_drawing(too_old)
    assert refused.whiteboard is None
    assert any("version 5" in error for error in refused.errors)

    code_only = _formula_drawing()
    code_only["version"] = DRAWING_FORMAT_VERSION
    code_only["steps"][0]["elements"] = [
        _element("snippet-1", "code", language="python", code="return 1")
    ]
    del code_only["description"]
    also_refused = check_drawing(code_only)
    assert also_refused.whiteboard is None
    assert any("version 5" in error for error in also_refused.errors)


def test_version_5_without_math_or_code_needs_a_description():
    plain = _described_drawing()
    plain["version"] = 5
    accepted = check_drawing(plain)
    assert accepted.errors == []
    assert accepted.whiteboard is not None
    assert accepted.whiteboard.version == 5

    missing = _formula_drawing()
    del missing["description"]
    refused = check_drawing(missing)
    assert refused.whiteboard is None
    assert any("description" in error for error in refused.errors)


def test_version_2_3_and_4_drawings_without_math_or_code_still_pass():
    version_2 = check_drawing(valid_whiteboard())
    assert version_2.errors == []
    assert version_2.whiteboard is not None
    assert version_2.whiteboard.version == DRAWING_FORMAT_VERSION

    marked = _answer_drawing()
    marked["version"] = MARKED_DRAWING_VERSION
    marked["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    version_3 = check_drawing(marked)
    assert version_3.errors == []
    assert version_3.whiteboard is not None
    assert version_3.whiteboard.version == MARKED_DRAWING_VERSION

    version_4 = check_drawing(_described_drawing())
    assert version_4.errors == []
    assert version_4.whiteboard is not None
    assert version_4.whiteboard.version == DESCRIBED_DRAWING_VERSION


def test_a_screen_reader_reads_each_formula_and_code_block():
    whiteboard = check_drawing(_formula_drawing()).whiteboard
    assert whiteboard is not None

    assert readable_description(whiteboard) == (
        "The area of a circle.\n"
        "math formula: A = \\pi r^{2}\n"
        "code block in python, 2 lines"
    )
    described = describe_whiteboard(whiteboard)
    assert "math formula-1 by agent" in described
    assert r"A = \pi r^{2}" in described
    assert "code snippet-1 by agent" in described
    assert "in python" in described
    assert "def area(r):" in described
    assert "return r * r" in described


def test_a_learner_save_cannot_change_agent_math_or_code():
    stored = check_drawing(_formula_drawing()).whiteboard
    assert stored is not None

    edited = stored.model_dump(mode="json")
    edited["steps"][0]["elements"][0]["latex"] = r"E = mc^{2}"
    changed = check_learner_drawing(stored, edited)
    assert changed.whiteboard is None
    assert any("formula-1" in error and "changed" in error for error in changed.errors)

    removed = stored.model_dump(mode="json")
    removed["steps"][0]["elements"] = [removed["steps"][0]["elements"][1]]
    gone = check_learner_drawing(stored, removed)
    assert gone.whiteboard is None
    assert any("formula-1" in error and "removed" in error for error in gone.errors)

    rewritten = stored.model_dump(mode="json")
    rewritten["version"] = DESCRIBED_DRAWING_VERSION
    rewritten["description"] = "The learner rewrote this."
    rewritten["simplifies"] = "wb-other"
    kept = check_learner_drawing(stored, rewritten)
    assert kept.errors == []
    assert kept.whiteboard is not None
    assert kept.whiteboard.version == 5
    assert kept.whiteboard.description == "The area of a circle."
    assert kept.whiteboard.simplifies is None
    assert kept.whiteboard.steps[0].elements[0].latex == r"A = \pi r^{2}"


def test_marks_and_a_simpler_redraw_keep_working_with_math():
    drawing = _formula_drawing()
    drawing["id"] = "wb-1"
    drawing["steps"][0]["elements"].append(
        _element("answer-1", "rectangle", author="learner")
    )
    stored = check_drawing(drawing).whiteboard
    assert stored is not None

    marked = apply_marks(stored, _mark_action())
    assert marked.errors == []
    assert marked.whiteboard is not None
    assert marked.whiteboard.version == 5
    assert marked.whiteboard.description == "The area of a circle."
    assert marked.whiteboard.steps[0].elements[0].kind == "math"
    assert marked.whiteboard.steps[0].elements[0].latex == r"A = \pi r^{2}"
    assert [element.kind for element in marked.whiteboard.steps[-1].elements] == ["mark"]

    simpler = _formula_drawing()
    simpler["id"] = "wb-simple"
    simpler["simplifies"] = "wb-1"
    simpler["steps"][0]["elements"] = [simpler["steps"][0]["elements"][0]]
    redraw = check_drawing(simpler)
    assert redraw.errors == []
    assert redraw.whiteboard is not None
    assert redraw.whiteboard.version == 5
    assert redraw.whiteboard.simplifies == "wb-1"
    assert simpler_count_errors(marked.whiteboard, redraw.whiteboard) == []


def _graph_element(**fields: object) -> dict[str, object]:
    """One agent graph of y = 2*x+1 on three exact samples from 0 to 2."""

    base: dict[str, object] = {
        "x_label": "x",
        "y_label": "y",
        "x_min": 0,
        "x_max": 2,
        "y_min": -1,
        "y_max": 6,
        "series": [{"expression": "2*x+1", "sample_count": 3}],
    }
    base.update(fields)
    return _element("graph-1", "graph", **base)


def _graph_drawing() -> dict[str, object]:
    """A version 6 whiteboard with one function graph."""

    return {
        "version": 6,
        "id": "wb-graph",
        "session_id": "session-1",
        "description": "A straight line.",
        "steps": [
            {
                "id": "step-1",
                "reply_part": "[[step:step-1]]",
                "elements": [_graph_element()],
            }
        ],
    }


def test_a_graph_matches_its_numbers():
    """WB-13: plotted points are the function on the sample grid, computed here."""

    result = check_drawing(_graph_drawing())

    assert result.errors == []
    assert result.whiteboard is not None
    assert result.whiteboard.version == 6
    graph = result.whiteboard.steps[0].elements[0]
    assert graph.kind == "graph"
    assert graph.author == "agent"
    series = graph.series[0]
    assert [(point.x, point.y) for point in series.plotted] == [
        (0.0, 1.0),
        (1.0, 3.0),
        (2.0, 5.0),
    ]

    lied = _graph_drawing()
    lied["steps"][0]["elements"][0]["series"] = [
        {
            "expression": "2*x+1",
            "sample_count": 3,
            "plotted": [{"x": 9, "y": 9}, {"x": 8, "y": 8}, {"x": 7, "y": 7}],
        }
    ]
    replaced = check_drawing(lied)
    assert replaced.errors == []
    assert replaced.whiteboard is not None
    plotted = replaced.whiteboard.steps[0].elements[0].series[0].plotted
    assert [(point.x, point.y) for point in plotted] == [
        (0.0, 1.0),
        (1.0, 3.0),
        (2.0, 5.0),
    ]

    absolute = _graph_drawing()
    absolute["steps"][0]["elements"][0]["series"] = [
        {"expression": "abs(x)", "sample_count": 3}
    ]
    absolute["steps"][0]["elements"][0]["x_min"] = -2
    absolute["steps"][0]["elements"][0]["x_max"] = 2
    called = check_drawing(absolute)
    assert called.errors == []
    assert called.whiteboard is not None
    assert [
        (point.x, point.y)
        for point in called.whiteboard.steps[0].elements[0].series[0].plotted
    ] == [(-2.0, 2.0), (0.0, 0.0), (2.0, 2.0)]


def test_data_points_are_stored_unchanged():
    points = [{"x": 0.5, "y": -2}, {"x": 4, "y": 0.25}]
    drawing = _graph_drawing()
    drawing["steps"][0]["elements"][0]["series"] = [
        {"points": points, "plotted": [{"x": 1, "y": 1}]}
    ]

    result = check_drawing(drawing)

    assert result.errors == []
    assert result.whiteboard is not None
    series = result.whiteboard.steps[0].elements[0].series[0]
    assert [(point.x, point.y) for point in series.plotted] == [(0.5, -2), (4, 0.25)]
    assert [(point.x, point.y) for point in series.points] == [(0.5, -2), (4, 0.25)]


def test_invalid_or_unsafe_graph_expressions_are_refused():
    """Bad input returns errors. The check does not raise or run the expression."""

    for expression in (
        "__import__('os')",
        "x.real",
        "[1, 2][0]",
        "pow(x, 2)",
        "y",
        "   ",
    ):
        drawing = _graph_drawing()
        drawing["steps"][0]["elements"][0]["series"] = [
            {"expression": expression, "sample_count": 3}
        ]
        result = check_drawing(drawing)
        assert result.whiteboard is None, expression
        assert result.errors
        assert any("expression" in error for error in result.errors), result.errors


def test_graph_limits_are_enforced():
    too_many_samples = _graph_drawing()
    too_many_samples["steps"][0]["elements"][0]["series"] = [
        {"expression": "2*x+1", "sample_count": DRAWING_LIMITS.max_samples + 1}
    ]
    samples = check_drawing(too_many_samples)
    assert samples.whiteboard is None
    assert any("sample_count" in error for error in samples.errors)

    too_few_samples = _graph_drawing()
    too_few_samples["steps"][0]["elements"][0]["series"] = [
        {"expression": "2*x+1", "sample_count": DRAWING_LIMITS.min_samples - 1}
    ]
    few = check_drawing(too_few_samples)
    assert few.whiteboard is None
    assert any("sample_count" in error for error in few.errors)

    at_most = _graph_drawing()
    at_most["steps"][0]["elements"][0]["series"] = [
        {"expression": "2*x+1", "sample_count": DRAWING_LIMITS.max_samples}
    ]
    assert check_drawing(at_most).errors == []

    points = [{"x": index, "y": index} for index in range(DRAWING_LIMITS.max_data_points + 1)]
    too_many_points = _graph_drawing()
    too_many_points["steps"][0]["elements"][0]["series"] = [{"points": points}]
    crowded = check_drawing(too_many_points)
    assert crowded.whiteboard is None
    assert any("point" in error for error in crowded.errors)

    enough_points = _graph_drawing()
    enough_points["steps"][0]["elements"][0]["series"] = [
        {"points": points[: DRAWING_LIMITS.max_data_points]}
    ]
    assert check_drawing(enough_points).errors == []

    too_many_series = _graph_drawing()
    too_many_series["steps"][0]["elements"][0]["series"] = [
        {"expression": "2*x+1", "sample_count": 2}
        for _ in range(DRAWING_LIMITS.max_series + 1)
    ]
    series = check_drawing(too_many_series)
    assert series.whiteboard is None
    assert any("series" in error for error in series.errors)

    four = _graph_drawing()
    four["steps"][0]["elements"][0]["series"] = [
        {"expression": "2*x+1", "sample_count": 2} for _ in range(DRAWING_LIMITS.max_series)
    ]
    assert check_drawing(four).errors == []

    long_expression = _graph_drawing()
    long_expression["steps"][0]["elements"][0]["series"] = [
        {"expression": "x" + " " * DRAWING_LIMITS.max_expression_length, "sample_count": 2}
    ]
    huge = check_drawing(long_expression)
    assert huge.whiteboard is None
    assert any("expression" in error and "too long" in error for error in huge.errors)

    long_label = _graph_drawing()
    long_label["steps"][0]["elements"][0]["x_label"] = "a" * (
        DRAWING_LIMITS.max_axis_label_length + 1
    )
    label = check_drawing(long_label)
    assert label.whiteboard is None
    assert any("x_label" in error for error in label.errors)

    backwards = _graph_drawing()
    backwards["steps"][0]["elements"][0]["x_min"] = 2
    backwards["steps"][0]["elements"][0]["x_max"] = 2
    flat = check_drawing(backwards)
    assert flat.whiteboard is None
    assert any("x_min" in error for error in flat.errors)


def test_non_finite_graph_results_are_refused():
    cases = (
        ("1/x", -1, 1),
        ("sqrt(x)", -1, 1),
        ("exp(1000)", 0, 1),
    )
    for expression, x_min, x_max in cases:
        drawing = _graph_drawing()
        element = drawing["steps"][0]["elements"][0]
        element["x_min"] = x_min
        element["x_max"] = x_max
        element["series"] = [{"expression": expression, "sample_count": 3}]
        result = check_drawing(drawing)
        assert result.whiteboard is None, expression
        assert any("finite" in error for error in result.errors), result.errors


def test_a_graph_requires_version_6_and_older_drawings_still_open():
    for version in (2, 3, 4, 5):
        drawing = _graph_drawing()
        drawing["version"] = version
        if version < 4:
            del drawing["description"]
        refused = check_drawing(drawing)
        assert refused.whiteboard is None
        assert any("version 6" in error for error in refused.errors)

    plain = _described_drawing()
    plain["version"] = 6
    accepted = check_drawing(plain)
    assert accepted.errors == []
    assert accepted.whiteboard is not None
    assert accepted.whiteboard.version == 6

    formula = _formula_drawing()
    formula["version"] = 6
    with_math = check_drawing(formula)
    assert with_math.errors == []
    assert with_math.whiteboard is not None

    missing = _graph_drawing()
    del missing["description"]
    undescribed = check_drawing(missing)
    assert undescribed.whiteboard is None
    assert any("description" in error for error in undescribed.errors)

    version_2 = check_drawing(valid_whiteboard())
    assert version_2.errors == []
    assert version_2.whiteboard is not None
    assert version_2.whiteboard.version == DRAWING_FORMAT_VERSION

    marked = _answer_drawing()
    marked["version"] = MARKED_DRAWING_VERSION
    marked["steps"].append(
        {
            "id": "step-mark",
            "reply_part": "[[step:step-mark]]",
            "elements": [_circle_mark()],
        }
    )
    version_3 = check_drawing(marked)
    assert version_3.errors == []

    version_4 = check_drawing(_described_drawing())
    assert version_4.errors == []

    version_5 = check_drawing(_formula_drawing())
    assert version_5.errors == []
    assert version_5.whiteboard is not None
    assert version_5.whiteboard.version == 5


def test_a_screen_reader_reads_each_graph():
    whiteboard = check_drawing(_graph_drawing()).whiteboard
    assert whiteboard is not None
    assert readable_description(whiteboard) == (
        "A straight line.\ngraph of y = 2*x+1 from 0 to 2"
    )
    assert describe_whiteboard(whiteboard) == (
        "Whiteboard wb-graph:\n"
        "- graph graph-1 by agent at (10, 20): "
        'x-axis "x" from 0 to 2, y-axis "y" from -1 to 6; y = 2*x+1'
    )

    mixed = _graph_drawing()
    mixed["steps"][0]["elements"][0]["series"] = [
        {"expression": "2*x+1", "sample_count": 2},
        {"points": [{"x": 0, "y": 42.25}, {"x": 2, "y": 1}]},
    ]
    both = check_drawing(mixed)
    assert both.errors == []
    assert both.whiteboard is not None
    assert readable_description(both.whiteboard) == (
        "A straight line.\ngraph with 2 series from 0 to 2"
    )
    described = describe_whiteboard(both.whiteboard)
    assert "y = 2*x+1" in described
    assert "data" in described
    assert 'x-axis "x" from 0 to 2' in described
    assert 'y-axis "y" from -1 to 6' in described
    assert "42.25" not in described


def test_a_learner_save_cannot_change_an_agent_graph():
    stored = check_drawing(_graph_drawing()).whiteboard
    assert stored is not None

    edited = stored.model_dump(mode="json")
    edited["steps"][0]["elements"][0]["series"][0]["expression"] = "x"
    changed = check_learner_drawing(stored, edited)
    assert changed.whiteboard is None
    assert any("graph-1" in error and "changed" in error for error in changed.errors)

    removed = stored.model_dump(mode="json")
    removed["steps"][0]["elements"] = []
    gone = check_learner_drawing(stored, removed)
    assert gone.whiteboard is None
    assert any("graph-1" in error and "removed" in error for error in gone.errors)

    rewritten = stored.model_dump(mode="json")
    rewritten["version"] = 4
    rewritten["description"] = "The learner rewrote this."
    rewritten["simplifies"] = "wb-other"
    kept = check_learner_drawing(stored, rewritten)
    assert kept.errors == []
    assert kept.whiteboard is not None
    assert kept.whiteboard.version == 6
    assert kept.whiteboard.description == "A straight line."
    assert kept.whiteboard.simplifies is None
    assert kept.whiteboard.steps[0].elements[0].series[0].expression == "2*x+1"


def test_marks_math_and_a_simpler_redraw_keep_working_with_a_graph():
    drawing = _graph_drawing()
    drawing["id"] = "wb-1"
    drawing["steps"][0]["elements"].append(_element("formula-1", "math", latex=r"A = \pi r^{2}"))
    drawing["steps"][0]["elements"].append(
        _element("answer-1", "rectangle", author="learner")
    )
    stored = check_drawing(drawing).whiteboard
    assert stored is not None

    marked = apply_marks(stored, _mark_action())
    assert marked.errors == []
    assert marked.whiteboard is not None
    assert marked.whiteboard.version == 6
    assert marked.whiteboard.steps[0].elements[0].kind == "graph"
    assert [(point.x, point.y) for point in marked.whiteboard.steps[0].elements[0].series[0].plotted] == [
        (0.0, 1.0),
        (1.0, 3.0),
        (2.0, 5.0),
    ]
    assert [element.kind for element in marked.whiteboard.steps[-1].elements] == ["mark"]

    simpler = _graph_drawing()
    simpler["id"] = "wb-simple"
    simpler["simplifies"] = "wb-1"
    redraw = check_drawing(simpler)
    assert redraw.errors == []
    assert redraw.whiteboard is not None
    assert redraw.whiteboard.version == 6
    assert redraw.whiteboard.simplifies == "wb-1"
    assert simpler_count_errors(marked.whiteboard, redraw.whiteboard) == []
