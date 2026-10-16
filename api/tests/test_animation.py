"""Animation jobs: chat stays usable [AN-01, AN-02], two fixes then stop [AN-05, AN-09].

A filled profile is seeded so a job can start. The worker that writes and
runs the animation is covered with a fake writer and a fake sandbox.
Operating-system notices are covered in the web tests.
"""

import asyncio
import threading
from pathlib import Path

from claude_agent_sdk import ResultMessage

from polaris.animation import (
    FAILED,
    FAILURE_NOTICE,
    MAX_RUNS,
    READY,
    RUNNING,
    WAITING_NOTICE,
    produce,
    submit_code,
)
from polaris.animation_writer import (
    CODE_SCHEMA,
    ClaudeAnimationWriter,
    WriterFailed,
    animation_writer_options,
    writer_prompt,
)
from polaris.app import PLAYBACK_HEADERS
from polaris.chat import Chat
from polaris.sandbox import SandboxResult
from test_chat import EMPTY_PROFILE_REPLY, TeachingStub, make_client, post_turn, reply_text

FILLED_PROFILE = '{\n  "facts": ["wants short explanations"]\n}\n'
BRIEF = "Show a pizza cut into halves, then quarters."

_FAILING_CODE = "raise RuntimeError('animation boom')\n"
_OK_CODE = (
    "from pathlib import Path\n"
    "Path('animation.html').write_text('<html><body>ready</body></html>')\n"
)
_NO_PLAYBACK_CODE = "from pathlib import Path\nPath('ok.txt').write_text('ready')\n"


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
    """Returns scripted code. Records what each write received."""

    def __init__(self, codes: list[str], *, gate: threading.Event | None = None):
        self.codes = codes
        self.gate = gate
        self.calls: list[tuple[str, str | None, str | None]] = []

    async def write(self, brief: str, *, failed_code: str | None, error: str | None) -> str:
        if self.gate is not None:
            await asyncio.to_thread(self.gate.wait, 10)
        self.calls.append((brief, failed_code, error))
        return self.codes.pop(0)


class BrokenWriter:
    async def write(self, brief: str, *, failed_code: str | None, error: str | None) -> str:
        raise WriterFailed("The animation writer returned no code.")


def _job_from_events(events: list[dict]) -> dict:
    jobs = [
        event["artifact"]
        for event in events
        if event.get("artifact", {}).get("kind") == "animation"
    ]
    assert len(jobs) == 1
    return jobs[0]


def _fake_sandbox(outcomes: list[SandboxResult], *, write_playback: bool = False):
    calls: list[str] = []

    def run(code: str, *, work_dir, time_limit_seconds=120):
        del time_limit_seconds
        calls.append(code)
        if not outcomes:
            raise AssertionError("No further sandbox runs expected.")
        result = outcomes.pop(0)
        if write_playback and result.ok:
            Path(work_dir).joinpath("animation.html").write_text(
                "<html><body>fractions</body></html>", encoding="utf-8"
            )
        return result

    run.calls = calls
    return run


def _animating_client(make_client, writer, sandbox):
    client, _agent = make_client(AnimationJobStub(), profile=FILLED_PROFILE)
    app_chat: Chat = client.app.state.chat
    app_chat._animation_writer = writer
    app_chat._animation_sandbox = sandbox
    return client, app_chat


def test_the_chat_stays_usable_while_an_animation_job_runs(make_client):
    """Scenario: the chat stays usable [AN-01, AN-02]."""

    gate = threading.Event()
    writer = FakeWriter([_OK_CODE], gate=gate)
    sandbox = _fake_sandbox([SandboxResult(ok=True, error=None)], write_playback=True)
    client, app_chat = _animating_client(make_client, writer, sandbox)
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

    errors: list[str | None] = []
    sandbox = _fake_sandbox(
        [
            SandboxResult(ok=False, error="first fail"),
            SandboxResult(ok=False, error="second fail"),
            SandboxResult(ok=False, error="third fail"),
            SandboxResult(ok=False, error="should not run"),
        ]
    )

    def write_code(error: str | None) -> str:
        errors.append(error)
        return _FAILING_CODE

    outcome = produce(
        work_dir=tmp_path,
        write_code=write_code,
        run_sandbox=sandbox,
    )

    assert outcome.status == FAILED
    assert outcome.runs == MAX_RUNS
    assert outcome.session_notice == FAILURE_NOTICE
    assert sandbox.calls == [_FAILING_CODE, _FAILING_CODE, _FAILING_CODE]
    assert errors == [None, "first fail", "second fail"]


def test_a_fix_can_make_the_animation_ready(tmp_path: Path):
    """On failure the error goes back to the agent; a fix may succeed [AN-05]."""

    sandbox = _fake_sandbox(
        [
            SandboxResult(ok=False, error="needs fix"),
            SandboxResult(ok=True, error=None),
        ],
        write_playback=True,
    )
    codes = [_FAILING_CODE, _OK_CODE]

    def write_code(error: str | None) -> str:
        if error is None:
            return codes[0]
        assert error == "needs fix"
        return codes[1]

    outcome = produce(
        work_dir=tmp_path,
        write_code=write_code,
        run_sandbox=sandbox,
    )

    assert outcome.status == READY
    assert outcome.runs == 2
    assert outcome.session_notice is None
    assert len(sandbox.calls) == 2


def test_submit_code_stops_after_three_failures(tmp_path: Path):
    sandbox = _fake_sandbox(
        [
            SandboxResult(ok=False, error="a"),
            SandboxResult(ok=False, error="b"),
            SandboxResult(ok=False, error="c"),
        ]
    )

    first = submit_code(
        _FAILING_CODE, work_dir=tmp_path, runs_before=0, run_sandbox=sandbox
    )
    second = submit_code(
        _FAILING_CODE, work_dir=tmp_path, runs_before=1, run_sandbox=sandbox
    )
    third = submit_code(
        _FAILING_CODE, work_dir=tmp_path, runs_before=2, run_sandbox=sandbox
    )
    fourth = submit_code(
        _FAILING_CODE, work_dir=tmp_path, runs_before=3, run_sandbox=sandbox
    )

    assert first.status == RUNNING and first.error == "a"
    assert second.status == RUNNING and second.error == "b"
    assert third.status == FAILED
    assert third.session_notice == FAILURE_NOTICE
    assert third.error == "c"
    assert fourth.status == FAILED
    assert fourth.session_notice == FAILURE_NOTICE
    assert fourth.runs == 3
    assert len(sandbox.calls) == 3


def test_a_run_without_playback_stays_running_for_a_fix(tmp_path: Path):
    sandbox = _fake_sandbox([SandboxResult(ok=True, error=None)])
    attempt = submit_code(
        _NO_PLAYBACK_CODE, work_dir=tmp_path, runs_before=0, run_sandbox=sandbox
    )
    assert attempt.ok is False
    assert attempt.status == RUNNING
    assert "playback file" in (attempt.error or "")


def test_the_worker_sends_the_failed_code_and_error_to_the_writer(make_client):
    """On failure the error goes back to the agent, which submits a fix [AN-05]."""

    writer = FakeWriter(["CODE-A\n", "CODE-B\n"])
    sandbox = _fake_sandbox(
        [SandboxResult(ok=False, error="NameError: x"), SandboxResult(ok=True, error=None)],
        write_playback=True,
    )
    client, app_chat = _animating_client(make_client, writer, sandbox)
    session = client.post("/api/sessions").json()

    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    assert sandbox.calls == ["CODE-A\n", "CODE-B\n"]
    assert writer.calls == [(BRIEF, None, None), (BRIEF, "CODE-A\n", "NameError: x")]
    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == READY
    assert "CODE-" not in str(public)


def test_finished_animation_is_served_as_session_media(make_client):
    """Scenario: finished animation is an artifact the learner can open [AN-06]."""

    writer = FakeWriter([_OK_CODE])
    sandbox = _fake_sandbox([SandboxResult(ok=True, error=None)], write_playback=True)
    client, app_chat = _animating_client(make_client, writer, sandbox)
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == READY
    assert "code" not in public

    media = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}/media")
    assert media.status_code == 200
    assert "html" in media.headers["content-type"]
    assert b"fractions" in media.content
    # Agent HTML gets an opaque origin and no network, even when opened directly.
    csp = media.headers["content-security-policy"]
    assert csp == PLAYBACK_HEADERS["Content-Security-Policy"]
    assert csp.startswith("sandbox allow-scripts;")
    assert "allow-same-origin" not in csp
    assert "default-src 'none'" in csp
    assert media.headers["x-content-type-options"] == "nosniff"

    reopened = client.get(f"/api/sessions/{session['id']}").json()
    assert reopened["turns"][0]["artifacts"][0]["status"] == READY

    other = client.post("/api/sessions").json()
    hidden = client.get(f"/api/sessions/{other['id']}/jobs/{job['id']}/media")
    assert hidden.status_code == 404


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

    writer = FakeWriter([_FAILING_CODE] * MAX_RUNS)
    sandbox = _fake_sandbox(
        [
            SandboxResult(ok=False, error="one"),
            SandboxResult(ok=False, error="two"),
            SandboxResult(ok=False, error="three"),
        ]
    )
    client, app_chat = _animating_client(make_client, writer, sandbox)
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == FAILED
    assert "code" not in public
    assert len(sandbox.calls) == MAX_RUNS
    assert len(writer.calls) == MAX_RUNS

    again = post_turn(client, session["id"], "Are you there?")
    assert FAILURE_NOTICE in reply_text(again)
    assert app_chat.take_animation_notices(session["id"]) == []


def test_a_writer_failure_fails_the_job(make_client):
    """If no code can be written, the session is told to try later [AN-09]."""

    sandbox = _fake_sandbox([])
    client, app_chat = _animating_client(make_client, BrokenWriter(), sandbox)
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Animate fractions."))
    app_chat.wait_for_animation_jobs(10)

    public = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert public["status"] == FAILED
    assert sandbox.calls == []
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
        structured_output={"code": _OK_CODE},
    )
    fields.update(overrides)
    return ResultMessage(**fields)


def test_the_writer_returns_structured_code(tmp_path: Path):
    seen: list[tuple[str, object]] = []

    async def fake_query(*, prompt, options):
        seen.append((prompt, options))
        yield _result()

    writer = ClaudeAnimationWriter(tmp_path, query_fn=fake_query)
    code = asyncio.run(writer.write(BRIEF, failed_code=None, error=None))

    assert code == _OK_CODE
    prompt, options = seen[0]
    assert BRIEF in prompt
    assert "failed" not in prompt
    assert options.tools == []
    assert options.allowed_tools == []
    assert options.setting_sources == []
    assert options.output_format == {"type": "json_schema", "schema": CODE_SCHEMA}


def test_the_writer_raises_when_no_code_comes_back(tmp_path: Path):
    async def fake_query(*, prompt, options):
        del prompt, options
        yield _result(structured_output=None, subtype="error_max_turns", is_error=True)

    writer = ClaudeAnimationWriter(tmp_path, query_fn=fake_query)
    try:
        asyncio.run(writer.write(BRIEF, failed_code=None, error=None))
    except WriterFailed:
        pass
    else:
        raise AssertionError("A result without code was accepted.")


def test_a_fix_prompt_carries_the_failed_code_and_error(tmp_path: Path):
    prompt = writer_prompt(BRIEF, failed_code="CODE-A", error="NameError: x")
    assert BRIEF in prompt
    assert "CODE-A" in prompt
    assert "NameError: x" in prompt
    system = animation_writer_options(cwd=tmp_path).system_prompt
    assert "animation.html" in system
    assert "no network" in system
