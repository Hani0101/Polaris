"""The animation format check [AN-10, AN-11] and its text [AN-15, AN-16].

The sample is a valid animation. Each test breaks one thing and expects an
error that names the step and the element, so the writer can fix it.
"""

import copy
import json
from pathlib import Path

from polaris.animation_format import (
    ANIMATION_LIMITS,
    check_animation,
    describe_animation,
    readable_animation_description,
    step_end_states,
)

_SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "sample_animation.json").read_text(
        encoding="utf-8"
    )
)


def sample() -> dict:
    return copy.deepcopy(_SAMPLE)


def element(data: dict, element_id: str) -> dict:
    return next(item for item in data["elements"] if item["id"] == element_id)


def errors_of(data: dict) -> list[str]:
    checked = check_animation(data)
    assert checked.animation is None
    assert checked.errors
    return checked.errors


def test_the_sample_passes():
    checked = check_animation(sample())
    assert checked.errors == []
    assert checked.animation is not None
    graph = checked.animation.elements[-1]
    assert len(graph.series[0].plotted) == 40


def test_moving_off_the_canvas_names_the_step_and_element():
    """Scenario: a refused check goes back to the writer [AN-10]."""

    data = sample()
    data["steps"][2]["actions"][0]["to"] = {"x": 420, "y": 180}
    errors = errors_of(data)
    assert any(
        error.startswith("step 3 ('next-middle'): 'pointer' goes off the canvas past the right edge")
        for error in errors
    ), errors


def test_overlapping_text_is_refused():
    """Scenario: the check finds layout problems [AN-11]."""

    data = sample()
    element(data, "checks-label")["x"] = 22
    errors = errors_of(data)
    assert any(
        "text 'checks' overlaps text 'checks-label'" in error and error.startswith("step 1")
        for error in errors
    ), errors


def test_text_visible_at_the_start_is_checked_too():
    data = sample()
    element(data, "target")["y"] = 290
    errors = errors_of(data)
    assert any(error.startswith("at the start: 'target' goes off the canvas") for error in errors)


def test_small_text_is_refused():
    data = sample()
    element(data, "target")["size"] = 12
    errors = errors_of(data)
    assert any("element 3 ('target'), size" in error for error in errors), errors


def test_scaling_text_below_the_minimum_is_refused():
    data = sample()
    data["steps"][0]["actions"].append(
        {"action": "scale", "element": "target", "to": 0.5, "duration_ms": 300}
    )
    errors = errors_of(data)
    assert any(
        error.startswith("step 1 ('middle'): text 'target' is 10 units high") for error in errors
    ), errors


def test_an_unknown_element_is_refused():
    data = sample()
    data["steps"][1]["actions"][0]["element"] = "ghost"
    errors = errors_of(data)
    assert "step 2 ('discard'), action 1: unknown element 'ghost'" in errors


def test_an_action_past_the_step_end_is_refused():
    data = sample()
    data["steps"][0]["actions"][2]["start_ms"] = 1600
    errors = errors_of(data)
    assert (
        "step 1 ('middle'), action 3: ends at 2000 ms, after the step ends at 1800 ms"
        in errors
    )


def test_a_step_duration_outside_the_limits_is_refused():
    data = sample()
    data["steps"][0]["duration_ms"] = 50
    errors = errors_of(data)
    assert any(error.startswith("step 1 ('middle'), duration_ms: must be from") for error in errors)


def test_two_moves_at_once_are_refused():
    data = sample()
    data["steps"][2]["actions"].append(
        {"action": "move", "element": "pointer", "to": {"x": 250, "y": 180}, "start_ms": 400}
    )
    errors = errors_of(data)
    assert any(
        error.startswith("step 3 ('next-middle'), action 3: moves 'pointer' while") for error in errors
    ), errors


def test_a_long_caption_is_refused():
    data = sample()
    data["steps"][1]["caption"] = "x" * (ANIMATION_LIMITS.max_caption_length + 1)
    errors = errors_of(data)
    assert any(
        error.startswith("step 2 ('discard'), caption: is longer than") for error in errors
    )


def test_duplicate_ids_are_refused():
    data = sample()
    data["steps"][0]["id"] = "pointer"
    errors = errors_of(data)
    assert any("duplicate ids: 'pointer'" in error for error in errors)


def test_trace_needs_a_traceable_element():
    data = sample()
    data["steps"][3]["actions"][1]["element"] = "target"
    errors = errors_of(data)
    assert any("cannot trace 'target', a text" in error for error in errors), errors


def test_count_needs_a_text_element():
    data = sample()
    data["steps"][0]["actions"][2]["element"] = "list"
    errors = errors_of(data)
    assert any("count needs a text element, and 'list' is a rectangle" in e for e in errors)


def test_an_unknown_kind_is_refused():
    data = sample()
    element(data, "list")["kind"] = "star"
    errors = errors_of(data)
    assert any(error.startswith("element 1 ('list'): unknown kind 'star'") for error in errors), errors


def test_colours_are_roles_not_values():
    """Scenario: the animation uses the design system [AN-14]."""

    data = sample()
    element(data, "target")["color"] = "#2563eb"
    errors = errors_of(data)
    assert any(error.startswith("element 3 ('target'), color") for error in errors), errors
    data = sample()
    element(data, "target")["font"] = "system-ui"
    assert any("font: unknown field" in error for error in errors_of(data))


def test_a_follow_path_is_sampled_and_checked():
    data = sample()
    element(data, "pointer")["visible_at_start"] = True
    data["steps"][2]["actions"][0] = {
        "action": "follow",
        "element": "pointer",
        "path": {
            "x_expression": "200 + 100 * sin(t)",
            "y_expression": "180",
            "t_min": 0,
            "t_max": 3.2,
            "sample_count": 30,
        },
        "duration_ms": 800,
    }
    checked = check_animation(data)
    assert checked.errors == []
    assert checked.animation is not None
    path = checked.animation.steps[2].actions[0].path
    assert len(path.plotted) == 30

    data["steps"][2]["actions"][0]["path"]["x_expression"] = "200 + 250 * sin(t)"
    errors = errors_of(data)
    assert any(
        error.startswith("step 3 ('next-middle'): 'pointer' goes off the canvas") for error in errors
    ), errors


def test_a_bad_follow_expression_is_refused():
    data = sample()
    data["steps"][2]["actions"][0] = {
        "action": "follow",
        "element": "pointer",
        "path": {"x_expression": "__import__('os')", "y_expression": "t"},
    }
    errors = errors_of(data)
    assert any(error.startswith("step 3 ('next-middle'), action 1, path") for error in errors), errors


def test_sent_plotted_points_are_replaced():
    data = sample()
    element(data, "curve")["series"][0]["plotted"] = [{"x": 0, "y": 999}]
    checked = check_animation(data)
    assert checked.animation is not None
    plotted = checked.animation.elements[-1].series[0].plotted
    assert plotted[0].y == 0


def test_stored_data_checks_again():
    checked = check_animation(sample())
    assert checked.animation is not None
    again = check_animation(checked.animation.model_dump(mode="json"))
    assert again.errors == []
    assert again.animation == checked.animation


def test_step_end_states_follow_the_actions():
    checked = check_animation(sample())
    assert checked.animation is not None
    ends = step_end_states(checked.animation)
    assert ends[0]["pointer"].visible is True
    assert ends[0]["checks"].text == "1"
    assert ends[2]["pointer"].dx == 100
    assert ends[2]["checks"].text == "3"
    assert ends[3]["pointer"].visible is False


def test_describe_animation_lists_every_step():
    """Scenario: a later turn knows what the animation showed [AN-16]."""

    checked = check_animation(sample())
    assert checked.animation is not None
    text = describe_animation(checked.animation)
    assert text.startswith("Animation sample-binary-search: Binary search halves the list")
    for index, step in enumerate(_SAMPLE["steps"], start=1):
        assert f"Step {index} ('{step['id']}'): {step['caption']}" in text
    assert "Counts text 'checks' from 1 to 3." in text
    assert "Traces graph 'curve' of y = log(x) / log(2) from 1 to 64." in text


def test_readable_description_names_the_steps():
    """Scenario: a screen reader follows the animation [AN-15]."""

    checked = check_animation(sample())
    assert checked.animation is not None
    text = readable_animation_description(checked.animation)
    assert text.startswith("Binary search halves the list. A sorted list")
    assert text.endswith("It has 4 steps.")
