"""The learner chooses Manim or Lottie before the writer starts [AN-21].

The chat worker's use of the chosen writer is covered with fake writers,
without Claude.
"""

from pathlib import Path

from polaris.animation import CHOOSING, CHOOSING_NOTICE, READY, RUNNING, WRITING
from polaris.animation_engines import LOTTIE, MANIM, AnimationEngines
from polaris.chat import Chat
from test_animation import (
    BRIEF,
    AnimationJobStub,
    FakeWriter,
    _animating_client,
    _good,
    _job_from_events,
)
from test_chat import TeachingStub, make_client, post_turn, reply_text  # noqa: F401 - fixture


class UnusedWriter:
    engine = "manim"

    async def write(self, *args, **kwargs):
        raise AssertionError("The learner chose the other writer.")


def _engine_url(session_id: str, job_id: str) -> str:
    return f"/api/sessions/{session_id}/jobs/{job_id}/engine"


def test_a_job_waits_for_the_learner_to_choose(make_client):  # noqa: F811
    """Scenario: the learner chooses the engine [AN-21]."""

    lottie = FakeWriter([_good()])
    engines = AnimationEngines(manim=UnusedWriter(), lottie=lottie)
    client, app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    events = post_turn(client, session["id"], "Show me fractions with pizza.")
    job = _job_from_events(events)

    assert job["status"] == RUNNING and job["stage"] == CHOOSING
    assert CHOOSING_NOTICE in reply_text(events)
    app_chat.wait_for_animation_jobs(10)
    assert lottie.calls == []

    chosen = client.post(_engine_url(session["id"], job["id"]), json={"engine": LOTTIE})
    assert chosen.status_code == 200
    assert chosen.json()["stage"] == WRITING
    app_chat.wait_for_animation_jobs(10)

    assert lottie.calls == [(BRIEF, None, None)]
    status = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert status["status"] == READY


def test_a_second_choice_does_not_start_a_second_writer(make_client):  # noqa: F811
    lottie = FakeWriter([_good()])
    engines = AnimationEngines(manim=UnusedWriter(), lottie=lottie)
    client, app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))

    first = client.post(_engine_url(session["id"], job["id"]), json={"engine": LOTTIE})
    second = client.post(_engine_url(session["id"], job["id"]), json={"engine": MANIM})
    app_chat.wait_for_animation_jobs(10)

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(lottie.calls) == 1


def test_an_unknown_engine_is_refused(make_client):  # noqa: F811
    engines = AnimationEngines(manim=UnusedWriter(), lottie=UnusedWriter())
    client, _app_chat = _animating_client(make_client, engines, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))

    refused = client.post(_engine_url(session["id"], job["id"]), json={"engine": "flash"})
    missing = client.post(_engine_url(session["id"], "no-such-job"), json={"engine": LOTTIE})

    assert refused.status_code == 422
    assert missing.status_code == 404
    status = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert status["stage"] == CHOOSING


def test_a_forced_engine_skips_the_choice(make_client):  # noqa: F811
    """POLARIS_ANIMATION_ENGINE gives one writer, so the job starts at once."""

    writer = FakeWriter([_good()])
    client, app_chat = _animating_client(make_client, writer, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    assert job["stage"] == WRITING
    assert len(writer.calls) == 1
    refused = client.post(_engine_url(session["id"], job["id"]), json={"engine": LOTTIE})
    assert refused.status_code == 409


def test_a_job_waiting_for_a_choice_survives_a_restart(tmp_path: Path):
    """No work was lost, so the job keeps waiting [AN-24]."""

    engines = AnimationEngines(manim=UnusedWriter(), lottie=UnusedWriter())
    first = Chat(tmp_path, TeachingStub(), animation_writer=engines)
    session, _ended = first.start()
    job = first.start_animation_job(session["id"], BRIEF)
    first.close()

    lottie = FakeWriter([_good()])
    second = Chat(
        tmp_path,
        TeachingStub(),
        animation_writer=AnimationEngines(manim=UnusedWriter(), lottie=lottie),
    )
    try:
        waiting = second.get_animation_job(session["id"], str(job["id"]))
        assert (waiting["status"], waiting["stage"]) == (RUNNING, CHOOSING)
        assert second.take_animation_notices(session["id"]) == []

        second.choose_animation_engine(session["id"], str(job["id"]), LOTTIE)
        second.wait_for_animation_jobs(10)
        assert lottie.calls == [(BRIEF, None, None)]
    finally:
        second.close()
