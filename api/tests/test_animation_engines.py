"""The learner chooses the engine, quality, and frame rate [AN-21, AN-26].

The chat worker's use of the chosen writer and settings is covered with
fake writers, without Claude.
"""

import copy
import json
from pathlib import Path

import pytest

from polaris.animation import CHOOSING, CHOOSING_NOTICE, READY, RUNNING, WRITING
from polaris.animation_engines import (
    ENGINE_OPTIONS,
    LOTTIE,
    MANIM,
    AnimationEngines,
    AnimationSettings,
    IllegalSettings,
    UnknownEngine,
    check_settings,
)
from polaris.chat import Chat
from polaris.lottie_video import check_lottie_video, check_scene
from polaris.lottie_writer import SceneStore, lottie_writer_prompt, starter_scene
from polaris.manim_job import ManimDraftData, produce_manim
from polaris.manim_render import RenderResult
from test_animation import (
    BRIEF,
    AnimationJobStub,
    FakeWriter,
    _animating_client,
    _good,
    _job_from_events,
)
from test_chat import TeachingStub, make_client, post_turn, reply_text  # noqa: F401 - fixture

MANIM_HIGH = {"engine": MANIM, "quality": "1080p", "fps": 60}
LOTTIE_SMOOTH = {"engine": LOTTIE, "quality": "medium", "fps": 60}


@pytest.fixture(autouse=True)
def no_render(monkeypatch):
    monkeypatch.setenv("POLARIS_LOTTIE_RENDER", "off")


class UnusedWriter:
    engine = "manim"

    async def write(self, *args, **kwargs):
        raise AssertionError("The learner chose the other writer.")


def _engine_url(session_id: str, job_id: str) -> str:
    return f"/api/sessions/{session_id}/jobs/{job_id}/engine"


def _lottie_video(fps: int) -> dict:
    scene = starter_scene(fps)
    return {
        "format": "lottie",
        "title": "A dot crosses a line",
        "description": "A line draws on, then a dot travels along it.",
        "scenes": [{"id": "intro", "caption": "A line draws on.", "lottie": scene}],
    }


# --- legal values ----------------------------------------------------------


def test_each_engine_accepts_only_its_own_values():
    for engine, options in ENGINE_OPTIONS.items():
        for quality in options.qualities:
            for fps in options.frame_rates:
                assert check_settings(engine, quality, fps) == AnimationSettings(
                    engine, quality, fps
                )

    with pytest.raises(UnknownEngine):
        check_settings("flash", "high", 30)
    # A Lottie quality is not a Manim quality, and the other way round.
    with pytest.raises(IllegalSettings, match="Manim quality"):
        check_settings(MANIM, "high", 30)
    with pytest.raises(IllegalSettings, match="Lottie quality"):
        check_settings(LOTTIE, "1080p", 30)
    with pytest.raises(IllegalSettings, match="Lottie frame rate"):
        check_settings(LOTTIE, "high", 15)
    for fps in (0, -30, 59, 120, True, "60", 30.5):
        with pytest.raises(IllegalSettings):
            check_settings(MANIM, "720p", fps)


def test_manim_quality_sets_the_final_render_size():
    assert check_settings(MANIM, "480p", 15).manim_output() == (640, 480, 15)
    assert check_settings(MANIM, "720p", 30).manim_output() == (960, 720, 30)
    assert check_settings(MANIM, "1080p", 60).manim_output() == (1440, 1080, 60)


def test_the_final_manim_render_uses_the_chosen_output(tmp_path: Path):
    outputs: list[object] = []

    def renderer(code, out_dir, *, quality, output=None):
        outputs.append((quality, output))
        return RenderResult(ok=False, errors=("stop here",))

    produce_manim(
        job_id="job-1",
        work_dir=tmp_path,
        write_draft=lambda failed, errors: ManimDraftData(title="t", description="d", code="c"),
        renderer=renderer,
        output=(960, 720, 30),
    )

    assert outputs[0] == ("final", (960, 720, 30))


# --- Lottie frame rate and quality ----------------------------------------


def test_a_lottie_scene_must_use_the_chosen_frame_rate():
    assert check_scene("s", starter_scene(60), fps=60) == []
    errors = check_scene("s", starter_scene(30), fps=60)
    assert any("fr must be 60" in error for error in errors)


def test_the_starter_scene_keeps_its_length_at_any_frame_rate():
    for fps in ENGINE_OPTIONS[LOTTIE].frame_rates:
        scene = starter_scene(fps)
        assert scene["fr"] == fps
        assert (scene["op"] - scene["ip"]) / fps == pytest.approx(4.0)


def test_a_lottie_video_refuses_an_illegal_quality_or_frame_rate():
    good = check_lottie_video({**_lottie_video(24), "quality": "low", "fps": 24})
    assert good.video is not None and (good.video.quality, good.video.fps) == ("low", 24)

    bad_quality = check_lottie_video({**_lottie_video(30), "quality": "ultra", "fps": 30})
    assert any("quality must be one of" in error for error in bad_quality.errors)
    bad_fps = check_lottie_video({**_lottie_video(15), "fps": 15})
    assert any("fps must be one of" in error for error in bad_fps.errors)


def test_the_lottie_writer_is_told_the_chosen_frame_rate(tmp_path: Path):
    prompt = lottie_writer_prompt(60)
    assert "Use fr 60" in prompt and "seconds x 60" in prompt

    store = SceneStore(tmp_path, fps=24)
    assert store.write("intro", "A line draws on.", json.dumps(starter_scene(24))) == []
    assert store.write("other", "Wrong rate.", json.dumps(starter_scene(30)))


# --- the choice through the API --------------------------------------------


def test_a_job_waits_for_the_learner_to_choose(make_client):  # noqa: F811
    """Scenario: the learner chooses the engine [AN-21]."""

    lottie = FakeWriter([_lottie_video(60)])
    engines = AnimationEngines(manim=UnusedWriter(), lottie=lottie)
    client, app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    events = post_turn(client, session["id"], "Show me fractions with pizza.")
    job = _job_from_events(events)

    assert job["status"] == RUNNING and job["stage"] == CHOOSING
    assert "settings" not in job
    assert CHOOSING_NOTICE in reply_text(events)
    app_chat.wait_for_animation_jobs(10)
    assert lottie.calls == []

    chosen = client.post(_engine_url(session["id"], job["id"]), json=LOTTIE_SMOOTH)
    assert chosen.status_code == 200
    assert chosen.json()["stage"] == WRITING
    assert chosen.json()["settings"] == LOTTIE_SMOOTH
    app_chat.wait_for_animation_jobs(10)

    assert lottie.calls == [(BRIEF, None, None)]
    assert lottie.settings == [AnimationSettings(LOTTIE, "medium", 60)]
    status = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert status["status"] == READY
    # Scenario: the card shows the settings after the job is done [AN-26].
    assert status["settings"] == LOTTIE_SMOOTH
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert saved["turns"][0]["artifacts"][0]["settings"] == LOTTIE_SMOOTH
    stored = json.loads((app_chat.animation_work_dir(job["id"]) / "animation.json").read_text())
    assert (stored["quality"], stored["fps"]) == ("medium", 60)


def test_illegal_settings_are_refused_and_the_job_keeps_waiting(make_client):  # noqa: F811
    engines = AnimationEngines(manim=UnusedWriter(), lottie=UnusedWriter())
    client, _app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    url = _engine_url(session["id"], job["id"])

    for body in (
        {"engine": "flash", "quality": "high", "fps": 30},
        {"engine": MANIM, "quality": "high", "fps": 30},
        {"engine": MANIM, "quality": "4k", "fps": 60},
        {"engine": LOTTIE, "quality": "high", "fps": 15},
        {"engine": LOTTIE, "quality": "high", "fps": "30"},
        {"engine": LOTTIE, "quality": "high", "fps": True},
        {"engine": LOTTIE, "quality": "high"},
    ):
        assert client.post(url, json=body).status_code == 422, body

    missing = client.post(_engine_url(session["id"], "no-such-job"), json=MANIM_HIGH)
    assert missing.status_code == 404
    status = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert status["stage"] == CHOOSING


def test_a_second_choice_does_not_start_a_second_writer(make_client):  # noqa: F811
    lottie = FakeWriter([_lottie_video(60)])
    engines = AnimationEngines(manim=UnusedWriter(), lottie=lottie)
    client, app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))

    first = client.post(_engine_url(session["id"], job["id"]), json=LOTTIE_SMOOTH)
    second = client.post(_engine_url(session["id"], job["id"]), json=MANIM_HIGH)
    app_chat.wait_for_animation_jobs(10)

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(lottie.calls) == 1


def test_the_create_dialog_turn_starts_the_job_with_its_settings(make_client):  # noqa: F811
    """Scenario: an animation from the Create animation dialog [AN-26]."""

    lottie = FakeWriter([_lottie_video(24)])
    engines = AnimationEngines(manim=UnusedWriter(), lottie=lottie)
    client, app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    settings = {"engine": LOTTIE, "quality": "low", "fps": 24}
    events = post_turn(
        client,
        session["id"],
        "Make an animation: fractions with pizza.",
        animation_settings=settings,
    )
    job = _job_from_events(events)
    app_chat.wait_for_animation_jobs(10)

    assert job["stage"] == WRITING
    assert job["settings"] == settings
    assert CHOOSING_NOTICE not in reply_text(events)
    assert lottie.settings == [AnimationSettings(LOTTIE, "low", 24)]


def test_a_turn_with_illegal_settings_is_refused(make_client):  # noqa: F811
    engines = AnimationEngines(manim=UnusedWriter(), lottie=UnusedWriter())
    client, _app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()

    refused = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={
            "message": "Make an animation: fractions.",
            "animation_settings": {"engine": MANIM, "quality": "1080p", "fps": 120},
        },
    )

    assert refused.status_code == 422
    assert client.get(f"/api/sessions/{session['id']}").json()["turns"] == []


def test_a_forced_engine_skips_the_choice(make_client):  # noqa: F811
    """POLARIS_ANIMATION_ENGINE gives one writer, so the job starts at once."""

    writer = FakeWriter([_good()])
    client, app_chat = _animating_client(make_client, writer, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    assert job["stage"] == WRITING
    assert len(writer.calls) == 1
    refused = client.post(_engine_url(session["id"], job["id"]), json=LOTTIE_SMOOTH)
    assert refused.status_code == 409


def test_a_job_waiting_for_a_choice_survives_a_restart(tmp_path: Path):
    """No work was lost, so the job keeps waiting [AN-24]."""

    engines = AnimationEngines(manim=UnusedWriter(), lottie=UnusedWriter())
    first = Chat(tmp_path, TeachingStub(), animation_writer=engines)
    session, _ended = first.start()
    job = first.start_animation_job(session["id"], BRIEF)
    first.close()

    lottie = FakeWriter([copy.deepcopy(_lottie_video(30))])
    second = Chat(
        tmp_path,
        TeachingStub(),
        animation_writer=AnimationEngines(manim=UnusedWriter(), lottie=lottie),
    )
    try:
        waiting = second.get_animation_job(session["id"], str(job["id"]))
        assert (waiting["status"], waiting["stage"]) == (RUNNING, CHOOSING)
        assert second.take_animation_notices(session["id"]) == []

        second.choose_animation_engine(
            session["id"], str(job["id"]), AnimationSettings(LOTTIE, "high", 30)
        )
        second.wait_for_animation_jobs(10)
        assert lottie.calls == [(BRIEF, None, None)]
    finally:
        second.close()
