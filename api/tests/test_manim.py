"""The Manim experiment (feat/manim-experiment): static checks, the render
and its layout checks, the write-render-fix loop [AN-05, AN-09, AN-19], and
a Manim job inside the chat: media, step clips, captions, and later turns
[AN-06, AN-12, AN-15, AN-16, AN-17].

Renders here are real and small (about two seconds each at preview size).
"""

from __future__ import annotations

from pathlib import Path

from polaris.animation import CHECKING, FAILED, FAILURE_NOTICE, FIXING, READY, WRITING
from polaris.manim_job import ManimDraftData, captions_vtt, produce_manim
from polaris.manim_render import PREVIEW, RenderResult, check_code, render
from polaris.manim_writer import ManimDraft, WriterRun, preview_tool_result
from polaris.models import Profile
from polaris.teaching import turn_prompt
from test_animation import RecordingStub, _animating_client, _job_from_events
from test_chat import make_client, post_turn  # noqa: F401 - make_client is a fixture

GOOD_SCENE = """
from manim import *
from polaris_manim import *

class Explainer(PolarisScene):
    def construct(self):
        self.step("A circle appears.")
        circle = Circle(radius=1.5, color=ACCENT)
        self.play(Create(circle), run_time=0.5)
        self.step("A label names it.")
        label = Text("circle", font_size=LABEL_SIZE).next_to(circle, DOWN)
        self.play(Write(label), run_time=0.5)
"""

BAD_LAYOUT = """
from manim import *
from polaris_manim import *

class Explainer(PolarisScene):
    def construct(self):
        self.step("Problems.")
        a = Text("Hello", font_size=40)
        b = Text("World", font_size=40).move_to(a)
        tiny = Text("tiny", font_size=20).to_edge(DOWN)
        far = Square().shift(RIGHT * 6)
        self.play(FadeIn(a, b, tiny, far), run_time=0.3)
"""


def test_static_check_refuses_imports_and_escapes():
    errors = check_code("import os\nopen('x')\n().__class__\n")
    assert any("import os" in error for error in errors)
    assert any("open is not allowed" in error for error in errors)
    assert any("__class__" in error for error in errors)
    assert check_code(GOOD_SCENE) == []
    assert check_code("def (:") and "SyntaxError" in check_code("def (:")[0]


def test_a_good_scene_renders_one_clip_and_picture_per_step(tmp_path: Path):
    result = render(GOOD_SCENE, tmp_path / "out", quality=PREVIEW)
    assert result.ok, result.errors
    assert [step.caption for step in result.steps] == ["A circle appears.", "A label names it."]
    assert all(step.video is not None and step.video.is_file() for step in result.steps)
    assert len(result.frames) == 2 and all(frame.is_file() for frame in result.frames)
    assert result.video is not None and result.video.is_file()


def test_layout_checks_name_the_step_and_the_problem(tmp_path: Path):
    result = render(BAD_LAYOUT, tmp_path / "out", quality=PREVIEW)
    assert not result.ok
    text = "\n".join(result.errors)
    assert "Text 'Hello' overlaps text Text 'World'" in text
    assert "Text 'tiny' is font size 20" in text
    assert "Square goes past the right edge" in text
    assert 'step 1 ("Problems.")' in text


def test_animation_before_a_step_and_latex_are_explained(tmp_path: Path):
    no_step = GOOD_SCENE.replace('        self.step("A circle appears.")\n', "")
    result = render(no_step, tmp_path / "a", quality=PREVIEW)
    assert not result.ok and "before the first self.step" in result.errors[0]

    latex = GOOD_SCENE.replace('Text("circle", font_size=LABEL_SIZE)', 'MathTex("x^2")')
    result = render(latex, tmp_path / "b", quality=PREVIEW)
    assert not result.ok and "MathTypst" in result.errors[0]


def test_the_scene_cannot_write_outside_its_folder(tmp_path: Path):
    """The audit hook is not a sandbox, but it stops plain writes elsewhere."""

    outside = tmp_path / "outside.npy"
    code = GOOD_SCENE.replace(
        "from polaris_manim import *",
        "from polaris_manim import *\nimport numpy as np",
    ).replace(
        "        circle = Circle",
        f"        np.save({str(outside)!r}, np.zeros(1))\n        circle = Circle",
    )
    assert check_code(code) == []
    result = render(code, tmp_path / "out", quality=PREVIEW)
    assert not result.ok and "PermissionError" in result.errors[0]
    assert not outside.exists()


def test_the_preview_tool_returns_errors_and_pictures(tmp_path: Path):
    result = render(GOOD_SCENE, tmp_path / "out", quality=PREVIEW)
    payload = preview_tool_result(result, previews_left=3)
    kinds = [block["type"] for block in payload["content"]]
    assert kinds.count("image") == 2
    assert payload["is_error"] is False
    assert "Previews left: 3." in payload["content"][0]["text"]


class _Renders:
    """Fake renderer that returns scripted results and records each call."""

    def __init__(self, results: list[RenderResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def __call__(self, code: str, out_dir: Path, *, quality: str) -> RenderResult:
        self.calls.append(code)
        return self.results.pop(0)


def test_two_fixes_then_stop(tmp_path: Path):
    """Scenario: two fixes then stop [AN-05, AN-09]."""

    renders = _Renders([RenderResult(ok=False, errors=("bad",))] * 3)
    seen: list[tuple[str | None, list[str] | None]] = []
    stages: list[str] = []

    def write(failed_code, errors):
        seen.append((failed_code, errors))
        return ManimDraftData(title="t", description="d", code=f"code {len(seen)}")

    result = produce_manim(
        job_id="job", work_dir=tmp_path, write_draft=write, on_stage=stages.append,
        renderer=renders,
    )
    assert result.status == FAILED and result.runs == 3
    assert result.session_notice == FAILURE_NOTICE
    assert seen == [(None, None), ("code 1", ["bad"]), ("code 2", ["bad"])]
    assert stages == [WRITING, CHECKING, FIXING, CHECKING, FIXING, CHECKING]


def test_captions_have_one_cue_per_step():
    vtt = captions_vtt(
        [
            {"caption": "One.", "start_s": 0.0, "duration_s": 2.5},
            {"caption": "Two.", "start_s": 2.5, "duration_s": 61.0},
        ]
    )
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:02.500\nOne." in vtt
    assert "00:00:02.500 --> 00:01:03.500\nTwo." in vtt


class FakeManimWriter:
    engine = "manim"

    def __init__(self, codes: list[str]) -> None:
        self.codes = codes
        self.calls: list[tuple[str | None, list[str] | None]] = []

    async def write(self, brief, *, failed_code=None, errors=None, preview_dir=None):
        self.calls.append((failed_code, errors))
        return ManimDraft(
            title="Circle", description="A circle and its label.", code=self.codes.pop(0),
            run=WriterRun(),
        )


def test_a_manim_job_plays_in_steps_and_later_turns_see_it(make_client):
    """A ready Manim job: video, steps, captions; code is not served [AN-06, AN-16, AN-17]."""

    agent = RecordingStub()
    writer = FakeManimWriter([BAD_LAYOUT, GOOD_SCENE])
    client, app_chat = _animating_client(make_client, writer, agent)
    agent.chat = app_chat
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate a circle."))
    app_chat.wait_for_animation_jobs(240)

    assert writer.calls[0] == (None, None)
    assert writer.calls[1][0] == BAD_LAYOUT and writer.calls[1][1]
    base = f"/api/sessions/{session['id']}/jobs/{job['id']}"
    assert client.get(base).json()["status"] == READY
    media = client.get(f"{base}/media")
    assert media.status_code == 200 and media.headers["content-type"] == "video/mp4"
    manifest = client.get(f"{base}/manim/manim.json").json()
    assert [step["caption"] for step in manifest["steps"]] == [
        "A circle appears.",
        "A label names it.",
    ]
    assert client.get(f"{base}/manim/steps/step-02.mp4").status_code == 200
    assert client.get(f"{base}/manim/posters/step-01.png").status_code == 200
    assert "A label names it." in client.get(f"{base}/manim/captions.vtt").text
    assert client.get(f"{base}/manim/source/scene.py").status_code == 404
    assert client.get(f"{base}/manim/../manim.json").status_code == 404

    asked = {"job_id": job["id"], "step_id": "step-2"}
    post_turn(client, session["id"], "Why a label?", animation_step=asked)
    seen = agent.seen[-1]
    prompt = turn_prompt(
        Profile(facts=("x",)),
        "Why?",
        animations=seen["animations"],
        animation_step=seen["animation_step"],
    )
    assert f"Animation {job['id']}: Circle" in prompt
    assert "A circle appears." in prompt
    assert f"step 2 of 2 of animation {job['id']}" in prompt

