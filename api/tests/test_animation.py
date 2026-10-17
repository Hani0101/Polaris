"""Animation jobs: chat stays usable [AN-01, AN-02], no agent code runs [AN-04],
two fixes then stop [AN-05, AN-09], refused checks go back [AN-10], stages [AN-19],
and later turns see the animation [AN-16, AN-17].

A filled profile is seeded so a job can start. The worker that writes and
checks the animation is covered with a fake writer. Operating-system
notices are covered in the web tests.
"""

import asyncio
import copy
import json
import threading
from pathlib import Path

from claude_agent_sdk import ResultMessage

from polaris.animation import (
    FAILED,
    FAILURE_NOTICE,
    MAX_RUNS,
    READY,
    RUNNING,
    CHECKING,
    FIXING,
    MAX_ERRORS_TO_WRITER,
    NOT_AN_OBJECT_ERROR,
    WAITING_NOTICE,
    WRITING,
    errors_for_writer,
    produce,
    submit_animation,
)
from polaris.animation_writer import (
    ClaudeAnimationWriter,
    WriterFailed,
    animation_writer_options,
    writer_prompt,
    writer_schema,
)
from polaris.app import PLAYBACK_HEADERS
from polaris.chat import Chat
from polaris.models import AnimationStep, Profile
from polaris.teaching import turn_prompt
from test_chat import EMPTY_PROFILE_REPLY, TeachingStub, make_client, post_turn, reply_text

FILLED_PROFILE = '{\n  "facts": ["wants short explanations"]\n}\n'
BRIEF = "Show a pizza cut into halves, then quarters."

_SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "sample_animation.json").read_text(
        encoding="utf-8"
    )
)


def _good() -> dict:
    """Writer output: the sample without the id, which the backend sets."""

    data = copy.deepcopy(_SAMPLE)
    data.pop("id")
    return data


def _off_canvas() -> dict:
    """Step 3 moves the pointer past the right edge."""

    data = _good()
    data["steps"][2]["actions"][0]["to"] = {"x": 420, "y": 180}
    return data


class AnimationJobStub:
    """Starts one animation job on the first teaching reply."""

    def __init__(self) -> None:
        self.chat = None
        self.reply_count = 0
        self.closed: list[str] = []

    async def reply(
        self,
        *,
        session_id: str,
        profile,
        learner_message: str,
        prior_turns,
        sdk_session_id: str | None,
        whiteboards=(),
        pointing=None,
        simplify=None,
        **_extra,
    ):
        del learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
        self.reply_count += 1
        if not profile.facts:
            yield EMPTY_PROFILE_REPLY
            return
        if self.reply_count == 1:
            yield "I will make an animation of that."
            assert self.chat is not None
            self.chat.start_animation_job(session_id, BRIEF)
            return
        yield "We can keep talking while that runs."

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


class FakeWriter:
    """Returns scripted animation data. Records what each write received."""

    def __init__(self, outputs: list[object], *, gate: threading.Event | None = None):
        self.outputs = outputs
        self.gate = gate
        self.calls: list[tuple[str, object, list[str] | None]] = []

    async def write(self, brief: str, *, failed_data, errors, job_id=None) -> object:
        if self.gate is not None:
            await asyncio.to_thread(self.gate.wait, 10)
        self.calls.append((brief, failed_data, errors))
        return self.outputs.pop(0)


class BrokenWriter:
    async def write(self, brief: str, *, failed_data, errors, job_id=None) -> dict:
        raise WriterFailed("The animation writer returned no animation.")


def _job_from_events(events: list[dict]) -> dict:
    jobs = [
        event["artifact"]
        for event in events
        if event.get("artifact", {}).get("kind") == "animation"
    ]
    assert len(jobs) == 1
    return jobs[0]


def _animating_client(make_client, writer, agent=None):
    client, _agent = make_client(agent or AnimationJobStub(), profile=FILLED_PROFILE)
    app_chat: Chat = client.app.state.chat
    app_chat._animation_writer = writer
    return client, app_chat


def test_the_chat_stays_usable_while_an_animation_job_runs(make_client):
    """Scenario: the chat stays usable [AN-01, AN-02]."""

    gate = threading.Event()
    writer = FakeWriter([_good()], gate=gate)
    client, app_chat = _animating_client(make_client, writer)
    session = client.post("/api/sessions").json()

    # The writer is blocked, so the turn can only finish if it does not wait.
    events = post_turn(client, session["id"], "Show me an animation of fractions.")

    job = _job_from_events(events)
    assert isinstance(job["id"], str) and job["id"]
    assert job["status"] == RUNNING
    assert job["session_id"] == session["id"]
    assert "code" not in job
    assert "media" not in job

    told = reply_text(events)
    assert WAITING_NOTICE in told
    assert events[-1] == {"done": True}

    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert saved["turns"][0]["artifacts"] == [job]
    assert WAITING_NOTICE in saved["turns"][0]["reply"]

    fetched = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == job
    assert job["stage"] == WRITING

    again = post_turn(client, session["id"], "What is a numerator?")
    assert reply_text(again) == "We can keep talking while that runs."
    assert [event for event in again if "artifact" in event] == []
    still = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert still["status"] == RUNNING

    other = client.post("/api/sessions").json()
    assert other["id"] != session["id"]
    assert other["turns"] == []
    hidden = client.get(f"/api/sessions/{other['id']}/jobs/{job['id']}")
    assert hidden.status_code == 404

    gate.set()
    app_chat.wait_for_animation_jobs(10)
    done = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert done["status"] == READY
    assert writer.calls == [(BRIEF, None, None)]


def test_a_missing_animation_job_is_not_found(make_client):
    client, _agent = make_client(profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    missing = client.get(f"/api/sessions/{session['id']}/jobs/missing-job")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "No animation job with that id."


def test_a_job_needs_a_brief(tmp_path: Path):
    chat = Chat(tmp_path, TeachingStub())
    session, _ended = chat.start()
    try:
        chat.start_animation_job(session["id"], "   ")
    except ValueError as exc:
        assert "brief" in str(exc)
    else:
        raise AssertionError("A blank brief started a job.")


def test_two_fixes_then_stop(tmp_path: Path):
    """Scenario: two fixes then stop [AN-05, AN-09]."""

    received: list[list[str] | None] = []

    def write_animation(errors: list[str] | None) -> dict:
        received.append(errors)
        return _off_canvas()

    outcome = produce(job_id="job-1", work_dir=tmp_path, write_animation=write_animation)

    assert outcome.status == FAILED
    assert outcome.runs == MAX_RUNS
    assert outcome.session_notice == FAILURE_NOTICE
    assert len(received) == MAX_RUNS
    assert received[0] is None
    assert received[1] == received[2]
    assert not (tmp_path / "animation.json").exists()


def test_a_refused_check_goes_back_to_the_writer(tmp_path: Path):
    """Scenario: a refused check goes back to the writer [AN-05, AN-10]."""

    outputs = [_off_canvas(), _good()]
    received: list[list[str] | None] = []

    def write_animation(errors: list[str] | None) -> dict:
        received.append(errors)
        return outputs.pop(0)

    outcome = produce(job_id="job-1", work_dir=tmp_path, write_animation=write_animation)

    assert outcome.status == READY
    assert outcome.runs == 2
    assert outcome.session_notice is None
    assert received[0] is None
    assert received[1] is not None
    assert any("step 3 ('next-middle')" in e and "'pointer'" in e for e in received[1])
    stored = json.loads((tmp_path / "animation.json").read_text(encoding="utf-8"))
    assert stored["id"] == "job-1"
    assert stored["steps"][0]["caption"] == _SAMPLE["steps"][0]["caption"]


def test_stages_follow_the_job(tmp_path: Path):
    """Writing, checking, then fixing after a refusal [AN-19]."""

    outputs = [_off_canvas(), _good()]
    stages: list[str] = []
    produce(
        job_id="job-1",
        work_dir=tmp_path,
        write_animation=lambda _errors: outputs.pop(0),
        on_stage=stages.append,
    )
    assert stages == [WRITING, CHECKING, FIXING, CHECKING]


def test_submit_animation_stops_after_three_failures(tmp_path: Path):
    first = submit_animation(_off_canvas(), job_id="j", work_dir=tmp_path, runs_before=0)
    second = submit_animation(_off_canvas(), job_id="j", work_dir=tmp_path, runs_before=1)
    third = submit_animation(_off_canvas(), job_id="j", work_dir=tmp_path, runs_before=2)
    fourth = submit_animation(_good(), job_id="j", work_dir=tmp_path, runs_before=3)

    assert first.status == RUNNING and first.errors
    assert second.status == RUNNING and second.errors
    assert third.status == FAILED
    assert third.session_notice == FAILURE_NOTICE
    assert third.errors
    assert fourth.status == FAILED
    assert fourth.session_notice == FAILURE_NOTICE
    assert fourth.runs == 3
    assert not (tmp_path / "animation.json").exists()


def test_data_that_is_not_an_object_is_a_failed_run(tmp_path: Path):
    attempt = submit_animation(["not", "an", "object"], job_id="j", work_dir=tmp_path, runs_before=0)
    assert attempt.ok is False
    assert attempt.status == RUNNING
    assert attempt.errors == (NOT_AN_OBJECT_ERROR,)


def test_the_writer_gets_a_bounded_error_list():
    errors = [f"error {index}" for index in range(MAX_ERRORS_TO_WRITER + 5)]
    shown = errors_for_writer(errors)
    assert len(shown) == MAX_ERRORS_TO_WRITER + 1
    assert shown[-1] == "... and 5 more errors."


def test_the_worker_sends_the_failed_data_and_errors_to_the_writer(make_client):
    """On failure the errors go back to the agent, which submits a fix [AN-05, AN-10]."""

    bad = _off_canvas()
    writer = FakeWriter([bad, _good()])
    client, app_chat = _animating_client(make_client, writer)
    session = client.post("/api/sessions").json()

    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    assert len(writer.calls) == 2
    assert writer.calls[0] == (BRIEF, None, None)
    brief, failed_data, errors = writer.calls[1]
    assert brief == BRIEF
    assert failed_data == bad
    assert errors and any("'pointer'" in error for error in errors)
    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == READY
    assert "stage" not in public


def test_finished_animation_is_served_as_session_media(make_client):
    """Scenario: finished animation is an artifact the learner can open [AN-06]."""

    writer = FakeWriter([_good()])
    client, app_chat = _animating_client(make_client, writer)
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == READY
    assert "code" not in public

    media = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}/media")
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("application/json")
    served = media.json()
    assert served["id"] == job["id"]
    assert served["title"] == _SAMPLE["title"]
    csp = media.headers["content-security-policy"]
    assert csp == PLAYBACK_HEADERS["Content-Security-Policy"]
    assert csp.startswith("sandbox allow-scripts;")
    assert "allow-same-origin" not in csp
    assert "default-src 'none'" in csp
    assert "webrtc 'block'" in csp
    assert media.headers["x-content-type-options"] == "nosniff"

    reopened = client.get(f"/api/sessions/{session['id']}").json()
    assert reopened["turns"][0]["artifacts"][0]["status"] == READY

    other = client.post("/api/sessions").json()
    hidden = client.get(f"/api/sessions/{other['id']}/jobs/{job['id']}/media")
    assert hidden.status_code == 404


def test_an_older_html_animation_still_opens(make_client):
    """A job finished before decision 0006 kept animation.html [AN-06]."""

    client, app_chat = _animating_client(make_client, None)
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.animation_work_dir(job["id"]).joinpath("animation.html").write_text(
        "<html><body>fractions</body></html>", encoding="utf-8"
    )
    app_chat._set_animation_status(job["id"], READY)

    media = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}/media")
    assert media.status_code == 200
    assert "html" in media.headers["content-type"]
    assert b"fractions" in media.content
    # Older HTML gets an opaque origin and no network, even when opened directly.
    assert media.headers["content-security-policy"].startswith("sandbox allow-scripts;")
    assert app_chat.animations_for_reply(session["id"]) == []


def test_running_job_has_no_media(make_client):
    client, _agent = make_client(AnimationJobStub(), profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    events = post_turn(client, session["id"], "Animate fractions.")
    job = _job_from_events(events)
    media = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}/media")
    assert media.status_code == 404
    assert media.json()["detail"] == "No animation playback for that job."


def test_session_is_told_after_two_fixes_fail(make_client):
    """Scenario: two fixes then stop [AN-05, AN-09]. The session receives FAILURE_NOTICE."""

    writer = FakeWriter([_off_canvas() for _ in range(MAX_RUNS)])
    client, app_chat = _animating_client(make_client, writer)
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == FAILED
    assert "stage" not in public
    assert len(writer.calls) == MAX_RUNS

    again = post_turn(client, session["id"], "Are you there?")
    assert FAILURE_NOTICE in reply_text(again)
    assert app_chat.take_animation_notices(session["id"]) == []


def test_a_writer_failure_fails_the_job(make_client):
    """If no animation can be written, the session is told to try later [AN-09]."""

    client, app_chat = _animating_client(make_client, BrokenWriter())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == FAILED
    assert app_chat.take_animation_notices(session["id"]) == [FAILURE_NOTICE]


def test_a_job_running_when_polaris_stopped_fails_on_restart(tmp_path: Path):
    """The worker is gone after a restart, so the job cannot finish [AN-09]."""

    first = Chat(tmp_path, TeachingStub())
    session, _ended = first.start()
    job = first.start_animation_job(session["id"], BRIEF)
    first.close()

    second = Chat(tmp_path, TeachingStub())
    try:
        assert second.get_animation_job(session["id"], str(job["id"]))["status"] == FAILED
        assert second.take_animation_notices(session["id"]) == [FAILURE_NOTICE]
    finally:
        second.close()


def _result(**overrides) -> ResultMessage:
    fields = dict(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="writer-1",
        structured_output=_good(),
    )
    fields.update(overrides)
    return ResultMessage(**fields)


def test_the_writer_returns_structured_animation_data(tmp_path: Path):
    """No code comes back from the writer [AN-04]."""

    seen: list[tuple[str, object]] = []

    async def fake_query(*, prompt, options):
        seen.append((prompt, options))
        yield _result()

    writer = ClaudeAnimationWriter(tmp_path, query_fn=fake_query)
    data = asyncio.run(writer.write(BRIEF, failed_data=None, errors=None))

    assert data == _good()
    prompt, options = seen[0]
    assert BRIEF in prompt
    assert "refused" not in prompt
    assert options.tools == []
    assert options.allowed_tools == []
    assert options.setting_sources == []
    assert options.output_format == {"type": "json_schema", "schema": writer_schema()}


def test_the_writer_schema_uses_only_accepted_keywords():
    text = json.dumps(writer_schema())
    for keyword in ("oneOf", "discriminator", "minLength", "maxLength", "minimum", "maximum", "$defs", "plotted"):
        assert f'"{keyword}"' not in text
    schema = writer_schema()
    assert "id" not in schema["properties"]
    assert "version" not in schema["properties"]
    assert set(schema["required"]) == {"title", "description", "elements", "steps"}


def test_the_writer_raises_when_no_animation_comes_back(tmp_path: Path):
    async def fake_query(*, prompt, options):
        del prompt, options
        yield _result(structured_output=None, subtype="error_max_turns", is_error=True)

    writer = ClaudeAnimationWriter(tmp_path, query_fn=fake_query)
    try:
        asyncio.run(writer.write(BRIEF, failed_data=None, errors=None))
    except WriterFailed:
        pass
    else:
        raise AssertionError("A result without an animation was accepted.")


def test_a_fix_prompt_carries_the_failed_data_and_errors(tmp_path: Path):
    prompt = writer_prompt(
        BRIEF, failed_data={"title": "DATA-A"}, errors=["step 3 ('x'): 'ball' goes off"]
    )
    assert BRIEF in prompt
    assert "DATA-A" in prompt
    assert "- step 3 ('x'): 'ball' goes off" in prompt
    system = animation_writer_options(cwd=tmp_path).system_prompt
    assert "400 units wide" in system
    assert "never code" in system


class RecordingStub(AnimationJobStub):
    """Starts a job on the first reply, then records what later replies see."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[dict] = []

    async def reply(self, **kwargs):
        self.seen.append(kwargs)
        async for chunk in super().reply(**kwargs):
            yield chunk


def test_a_later_turn_knows_what_the_animation_showed(make_client):
    """Scenario: a later turn knows what the animation showed [AN-16]."""

    agent = RecordingStub()
    client, app_chat = _animating_client(make_client, FakeWriter([_good()]), agent)
    agent.chat = app_chat
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate binary search."))
    app_chat.wait_for_animation_jobs(10)

    post_turn(client, session["id"], "Why only three checks?")
    animations = agent.seen[-1]["animations"]
    assert [animation.id for animation in animations] == [job["id"]]

    prompt = turn_prompt(Profile(facts=("x",)), "Why?", animations=animations)
    assert "Animations in this session:" in prompt
    assert f"Animation {job['id']}: {_SAMPLE['title']}" in prompt
    for step in _SAMPLE["steps"]:
        assert step["caption"] in prompt


def test_the_learner_asks_about_a_step(make_client):
    """Scenario: the learner asks about a step [AN-17]."""

    agent = RecordingStub()
    client, app_chat = _animating_client(make_client, FakeWriter([_good()]), agent)
    agent.chat = app_chat
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate binary search."))
    app_chat.wait_for_animation_jobs(10)

    asked = {"job_id": job["id"], "step_id": "discard"}
    events = post_turn(
        client, session["id"], "Why throw that half away?", animation_step=asked
    )
    assert events[-1] == {"done": True}
    seen = agent.seen[-1]
    assert seen["animation_step"] == AnimationStep(job_id=job["id"], step_id="discard")

    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert saved["turns"][-1]["animation_step"] == asked

    prompt = turn_prompt(
        Profile(facts=("x",)),
        "Why?",
        animations=seen["animations"],
        animation_step=seen["animation_step"],
    )
    assert f"step 2 of 4 of animation {job['id']}" in prompt
    assert _SAMPLE["steps"][1]["caption"] in prompt

    bad = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": "?", "animation_step": {"job_id": job["id"], "step_id": "nope"}},
    )
    assert bad.status_code == 422


def test_the_eval_briefs_are_fixed_and_unique():
    """The animation eval is a fixed set of about ten briefs."""

    path = Path(__file__).resolve().parents[1] / "evals" / "animation_briefs.json"
    briefs = json.loads(path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in briefs]
    assert len(ids) >= 10
    assert len(set(ids)) == len(ids)
    assert all(item["brief"].strip() for item in briefs)
