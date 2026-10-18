"""Chat scenarios: CH-01, CH-03, CH-04, CH-05, PR-01, PR-02, PR-03, PR-05, and decision 0001.

An empty profile is asked for on every reply until the session ends.
The teaching agent does not write the profile. The session-end pass does.
"""

import asyncio
import json
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from polaris.agent import ReplyResult
from polaris.app import create_app
from polaris.login import ApiKeyPresent
from polaris.models import FactChange

EMPTY_PROFILE_REPLY = (
    "What should I know before I teach? "
    "How do you want to be taught, what can you already do, and where do you struggle?"
)


class StubPass:
    """Returns fixed fact changes so a test can see the session-end pass run."""

    def __init__(self, changes: tuple[FactChange, ...] = ()) -> None:
        self.changes = changes
        self.calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    async def run(self, *, turns, facts):
        self.calls.append(
            (
                tuple(turn.learner_message for turn in turns),
                tuple(fact.text for fact in facts),
            )
        )
        return self.changes


class GatedPass(StubPass):
    """Holds the session-end pass until released, so a test can act while it runs."""

    def __init__(self, changes: tuple[FactChange, ...] = ()) -> None:
        super().__init__(changes)
        self.release = threading.Event()
        self.finished = threading.Event()

    async def run(self, *, turns, facts):
        await asyncio.to_thread(self.release.wait, 10)
        try:
            return await super().run(turns=turns, facts=facts)
        finally:
            self.finished.set()


class TeachingStub:
    """Echoes profile facts into the reply so a test can see they were read."""

    def __init__(self) -> None:
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
        quizzes=(),
        **_extra,
    ):
        del session_id, prior_turns, sdk_session_id, whiteboards, pointing, simplify, quizzes
        if profile.facts:
            text = f"Noted {profile.facts[0]}. {learner_message}"
        else:
            text = EMPTY_PROFILE_REPLY
        yield text[:1]
        yield text[1:]

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


class GatedAgent:
    """Yields the first part of a reply, then waits, so a test can observe it early."""

    def __init__(self) -> None:
        self.release = threading.Event()

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
        quizzes=(),
        **_extra,
    ):
        del session_id, profile, learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify, quizzes
        yield "partial"
        await asyncio.to_thread(self.release.wait)
        yield " tail"

    async def close_session(self, session_id: str) -> None:
        del session_id


def parse_sse(buffer: str) -> tuple[list[dict], str]:
    events: list[dict] = []
    parts = buffer.split("\n\n")
    rest = parts.pop()
    for part in parts:
        for line in part.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))
    return events, rest


def post_turn(
    client: TestClient, session_id: str, message: str, **extra: object
) -> list[dict]:
    response = client.post(
        f"/api/sessions/{session_id}/turns",
        json={"message": message, **extra},
    )
    assert response.status_code == 200, response.text
    events, rest = parse_sse(response.text)
    assert rest == ""
    errors = [event["error"] for event in events if "error" in event]
    assert errors == []
    assert events[-1]["done"] is True
    return events


def reply_text(events: list[dict]) -> str:
    return "".join(event["text"] for event in events if "text" in event)


def read_profile(client) -> dict:
    """The profile needs a valid access token (AU-12), so sign in first."""

    pair = {"username": "learner", "password": "a long password"}
    if client.get("/api/sign-in").json()["pair_stored"]:
        signed_in = client.post("/api/sign-in", json=pair)
    else:
        signed_in = client.post(
            "/api/sign-in/pair", json={**pair, "password_again": pair["password"]}
        )
    token = signed_in.json()["access_token"]
    return client.get("/api/profile", headers={"Authorization": f"Bearer {token}"}).json()


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    opened: list[TestClient] = []

    def make(agent=None, profile: str | None = None, profile_pass=None, title_writer=None):
        if profile is not None:
            (tmp_path / "profile.json").write_text(profile, encoding="utf-8")
        stub = TeachingStub() if agent is None else agent
        client = TestClient(
            create_app(tmp_path, stub, profile_pass=profile_pass, title_writer=title_writer)
        )
        if hasattr(stub, "chat"):
            stub.chat = client.app.state.chat
        client.__enter__()
        opened.append(client)
        return client, stub

    yield make
    for client in opened:
        client.__exit__(None, None, None)


def test_typed_message_is_stored_as_a_turn(make_client):
    client, _agent = make_client()
    session = client.post("/api/sessions").json()

    events = post_turn(client, session["id"], "What is a fraction?")

    texts = [event["text"] for event in events if "text" in event]
    assert texts[0] == "W"
    assert len(texts) >= 2
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert saved["turns"] == [
        {
            "learner_message": "What is a fraction?",
            "reply": EMPTY_PROFILE_REPLY,
            "artifacts": [],
        }
    ]
    assert reply_text(events) == EMPTY_PROFILE_REPLY


def test_reply_is_visible_while_it_is_still_being_produced(make_client):
    agent = GatedAgent()
    client, _agent = make_client(agent)
    session = client.post("/api/sessions").json()
    body = json.dumps({"message": "Tell me more"}).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": f"/api/sessions/{session['id']}/turns",
        "raw_path": f"/api/sessions/{session['id']}/turns".encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            await asyncio.Event().wait()
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    bodies: list[bytes] = []
    status: dict[str, int] = {}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body" and message.get("body"):
            bodies.append(message["body"])

    async def drive():
        app_task = asyncio.create_task(client.app(scope, receive, send))
        try:
            async with asyncio.timeout(5):
                while b"partial" not in b"".join(bodies):
                    if app_task.done():
                        break
                    await asyncio.sleep(0.01)
            early = b"".join(bodies).decode()
            assert "partial" in early
            assert "tail" not in early
            agent.release.set()
            await app_task
        finally:
            agent.release.set()
            if not app_task.done():
                app_task.cancel()

    asyncio.run(drive())
    streamed = b"".join(bodies).decode()
    assert status["code"] == 200
    assert "partial" in streamed
    assert "tail" in streamed
    events, rest = parse_sse(streamed)
    assert rest == ""
    assert [event.get("text") for event in events if "text" in event] == [
        "partial",
        " tail",
    ]


def test_reopening_a_session_shows_its_turns(make_client):
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Remember this")
    left = client.post(f"/api/sessions/{session['id']}/leave")
    assert left.status_code == 200
    assert left.json()["ended"] is True

    reopened = client.post(f"/api/sessions/{session['id']}/open")
    assert reopened.status_code == 200
    assert reopened.json()["ended"] is False
    assert reopened.json()["turns"] == [
        {
            "learner_message": "Remember this",
            "reply": EMPTY_PROFILE_REPLY,
            "artifacts": [],
        }
    ]


def test_leaving_a_session_ends_it(make_client):
    client, agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Hello")

    left = client.post(f"/api/sessions/{session['id']}/leave")

    assert left.json()["ended"] is True
    assert client.get(f"/api/sessions/{session['id']}").json()["ended"] is True
    client.app.state.chat.wait_for_session_ends()
    assert agent.closed == [session["id"]]


def test_switching_sessions_ends_the_one_left(make_client):
    client, agent = make_client()
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "First question")
    second = client.post("/api/sessions").json()
    post_turn(client, second["id"], "Second question")

    assert client.get(f"/api/sessions/{first['id']}").json()["ended"] is True
    assert second["ended"] is False
    client.app.state.chat.wait_for_session_ends()
    assert agent.closed == [first["id"]]

    reopened = client.post(f"/api/sessions/{first['id']}/open")
    assert reopened.status_code == 200
    assert reopened.json()["ended"] is False
    assert client.get(f"/api/sessions/{second['id']}").json()["ended"] is True
    client.app.state.chat.wait_for_session_ends()
    assert agent.closed == [first["id"], second["id"]]


def test_every_reply_is_written_with_the_shared_profile(make_client, tmp_path):
    raw = '{\n  "facts": ["struggles with fractions"]\n}\n'
    client, _agent = make_client(profile=raw)
    first = client.post("/api/sessions").json()
    first_reply = reply_text(post_turn(client, first["id"], "What is a half?"))
    second = client.post("/api/sessions").json()
    second_reply = reply_text(
        post_turn(client, second["id"], "How do I add fractions?")
    )

    assert first_reply == "Noted struggles with fractions. What is a half?"
    assert second_reply == "Noted struggles with fractions. How do I add fractions?"
    assert not (tmp_path / "profile.json").exists()
    assert (tmp_path / "profile.json.imported").read_text(encoding="utf-8") == raw


def test_leaving_a_session_stores_profile_facts(make_client):
    client, _agent = make_client(
        profile_pass=StubPass((FactChange("ADD", "likes step-by-step walkthroughs"),))
    )
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like step-by-step walkthroughs")

    left = client.post(f"/api/sessions/{session['id']}/leave")

    assert left.status_code == 200
    assert read_profile(client) == {
        "facts": ["likes step-by-step walkthroughs"]
    }


def test_a_later_session_teaches_from_stored_facts(make_client):
    client, _agent = make_client(
        profile_pass=StubPass((FactChange("ADD", "likes step-by-step walkthroughs"),))
    )
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "I like step-by-step walkthroughs")
    client.post(f"/api/sessions/{first['id']}/leave")

    second = client.post("/api/sessions").json()
    reply = reply_text(post_turn(client, second["id"], "What is recursion?"))

    assert reply == "Noted likes step-by-step walkthroughs. What is recursion?"


def test_switching_sessions_stores_facts_from_the_one_left(make_client):
    client, _agent = make_client(
        profile_pass=StubPass((FactChange("ADD", "struggles with fractions"),))
    )
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "I struggle with fractions")

    client.post("/api/sessions")

    assert read_profile(client) == {"facts": ["struggles with fractions"]}


def test_switching_sessions_does_not_wait_for_the_profile_pass(make_client):  # CH-05, PR-05
    writer = GatedPass((FactChange("ADD", "struggles with fractions"),))
    client, _agent = make_client(profile_pass=writer)
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "I struggle with fractions")

    second = client.post("/api/sessions")

    assert second.status_code == 200
    assert not writer.finished.is_set()
    writer.release.set()
    assert read_profile(client) == {"facts": ["struggles with fractions"]}


def test_a_reply_waits_for_a_pass_still_running(make_client):  # PR-01, PR-02, PR-05
    writer = GatedPass((FactChange("ADD", "likes step-by-step walkthroughs"),))
    client, _agent = make_client(profile_pass=writer)
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "I like step-by-step walkthroughs")
    second = client.post("/api/sessions").json()

    threading.Timer(0.2, writer.release.set).start()
    reply = reply_text(post_turn(client, second["id"], "What is recursion?"))

    assert reply == "Noted likes step-by-step walkthroughs. What is recursion?"


def test_a_later_ending_runs_the_profile_pass_again(make_client):
    texts = ("likes diagrams", "comfortable with Python")

    class NextFactPass:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, *, turns, facts):
            del turns, facts
            fact = texts[min(self.calls, len(texts) - 1)]
            self.calls += 1
            return (FactChange("ADD", fact),)

    writer = NextFactPass()
    client, _agent = make_client(profile_pass=writer)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like diagrams")
    client.post(f"/api/sessions/{session['id']}/leave")
    client.post(f"/api/sessions/{session['id']}/open")
    post_turn(client, session["id"], "I know Python")
    client.post(f"/api/sessions/{session['id']}/leave")
    client.app.state.chat.wait_for_session_ends()

    assert writer.calls == 2
    assert read_profile(client) == {
        "facts": ["likes diagrams", "comfortable with Python"]
    }


def test_a_later_ending_without_a_new_turn_runs_no_pass(make_client):  # PR-05
    writer = StubPass((FactChange("ADD", "likes diagrams"),))
    client, _agent = make_client(profile_pass=writer)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like diagrams")
    client.post(f"/api/sessions/{session['id']}/leave")
    client.app.state.chat.wait_for_session_ends()
    for _ in range(3):
        client.post(f"/api/sessions/{session['id']}/open")
        client.post(f"/api/sessions/{session['id']}/leave")
    client.app.state.chat.wait_for_session_ends()

    assert len(writer.calls) == 1


def test_a_later_ending_after_a_failed_pass_runs_it_again(make_client):  # PR-05
    class FailOncePass(StubPass):
        async def run(self, *, turns, facts):
            await super().run(turns=turns, facts=facts)
            if len(self.calls) == 1:
                raise RuntimeError("no result")
            return (FactChange("ADD", "likes diagrams"),)

    writer = FailOncePass()
    client, _agent = make_client(profile_pass=writer)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like diagrams")
    client.post(f"/api/sessions/{session['id']}/leave")
    client.post(f"/api/sessions/{session['id']}/open")
    client.post(f"/api/sessions/{session['id']}/leave")
    client.app.state.chat.wait_for_session_ends()

    assert len(writer.calls) == 2
    assert read_profile(client) == {"facts": ["likes diagrams"]}


def test_a_reply_does_not_wait_for_a_pass_when_the_profile_has_facts(make_client):  # PR-01
    writer = GatedPass((FactChange("ADD", "likes step-by-step walkthroughs"),))
    client, _agent = make_client(
        profile='{\n  "facts": ["struggles with fractions"]\n}\n', profile_pass=writer
    )
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "I like step-by-step walkthroughs")
    second = client.post("/api/sessions").json()

    reply = reply_text(post_turn(client, second["id"], "What is recursion?"))

    assert reply == "Noted struggles with fractions. What is recursion?"
    assert not writer.finished.is_set()
    writer.release.set()
    client.app.state.chat.wait_for_session_ends()


def test_an_agent_closes_without_waiting_for_an_earlier_pass(make_client):  # CH-05
    writer = GatedPass()
    # A filled profile, so the second reply does not wait for the first pass.
    client, agent = make_client(
        profile='{\n  "facts": ["likes diagrams"]\n}\n', profile_pass=writer
    )
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "First")
    second = client.post("/api/sessions").json()
    post_turn(client, second["id"], "Second")

    client.post("/api/sessions")
    client.app.state.chat.wait_for_agent_close(second["id"])

    assert second["id"] in agent.closed
    assert not writer.finished.is_set()
    writer.release.set()
    client.app.state.chat.wait_for_session_ends()


def test_a_repeated_fact_is_not_stored_twice(make_client):
    client, _agent = make_client(
        profile='{\n  "facts": ["I suck at math"]\n}\n',
        profile_pass=StubPass((FactChange("ADD", "I suck at math"),)),
    )
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I still suck at math")
    client.post(f"/api/sessions/{session['id']}/leave")

    assert read_profile(client) == {"facts": ["I suck at math"]}


def test_profile_pass_api_key_stops_the_app(make_client):
    class KeyPass:
        async def run(self, *, turns, facts):
            del turns, facts
            raise ApiKeyPresent(
                "Polaris stopped because an API key is present. "
                "v1 uses the Claude login on this machine."
            )

    client, _agent = make_client(profile_pass=KeyPass())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "hello")

    left = client.post(f"/api/sessions/{session['id']}/leave")

    # The session ends at once. The pass runs after, and its API key stops the app.
    assert left.status_code == 200
    client.app.state.chat.wait_for_session_ends()
    assert client.get("/health").status_code == 503


def test_a_failed_profile_pass_does_not_block_leaving(make_client):
    class ExplodingPass:
        async def run(self, *, turns, facts):
            del turns, facts
            raise RuntimeError("pass failed")

    client, _agent = make_client(profile_pass=ExplodingPass())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "hello")

    left = client.post(f"/api/sessions/{session['id']}/leave")

    assert left.status_code == 200
    assert left.json()["ended"] is True
    assert read_profile(client) == {"facts": []}


def _passes(client) -> list[dict[str, object]]:
    client.app.state.chat.wait_for_session_ends()

    def read(conn):
        rows = conn.execute(
            """
            SELECT session_id, trigger, status, error, last_turn_id, changes_json
            FROM profile_passes ORDER BY started_at ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    return client.app.state.chat._with_db(read)


def test_a_failed_profile_pass_is_recorded(make_client):
    class ExplodingPass:
        async def run(self, *, turns, facts):
            del turns, facts
            raise RuntimeError("pass failed")

    client, _agent = make_client(profile_pass=ExplodingPass())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "hello")

    client.post(f"/api/sessions/{session['id']}/leave")

    (run,) = _passes(client)
    assert run["session_id"] == session["id"]
    assert (run["trigger"], run["status"], run["error"]) == ("end", "failed", "RuntimeError")
    assert run["last_turn_id"] is not None


def test_a_stored_pass_records_its_changes_and_evidence(make_client):
    class EvidencePass:
        async def run(self, *, turns, facts):
            del facts
            return (
                FactChange(
                    "ADD",
                    "Likes diagrams",
                    kind="taught",
                    basis="stated",
                    evidence=(turns[0].id,),
                ),
                FactChange("UPDATE", "Struggles with fractions", id="F9"),
            )

    client, _agent = make_client(profile_pass=EvidencePass())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like diagrams")

    client.post(f"/api/sessions/{session['id']}/leave")

    assert read_profile(client) == {"facts": ["Likes diagrams"]}
    (run,) = _passes(client)
    assert run["status"] == "stored"
    changes = json.loads(run["changes_json"])
    assert [item["action"] for item in changes["accepted"]] == ["ADD"]
    assert changes["refused"][0]["why"] == "names no stored fact"

    def evidence(conn):
        return conn.execute(
            "SELECT session_id, turn_id FROM fact_evidence"
        ).fetchall()

    (row,) = client.app.state.chat._with_db(evidence)
    assert row["session_id"] == session["id"]
    assert row["turn_id"] == run["last_turn_id"]


def test_empty_profile_asks_and_does_not_teach(make_client, tmp_path):
    client, _agent = make_client()
    session = client.post("/api/sessions").json()

    first = reply_text(post_turn(client, session["id"], "What is a fraction?"))
    second = reply_text(post_turn(client, session["id"], "Just teach me fractions."))

    assert first == EMPTY_PROFILE_REPLY
    assert second == EMPTY_PROFILE_REPLY
    assert "part of a whole" not in first
    assert "part of a whole" not in second
    assert not (tmp_path / "profile.json").exists()
    assert read_profile(client) == {"facts": []}


def test_profile_has_no_write_route(make_client):
    client, _agent = make_client()
    response = client.post("/api/profile", json={"facts": ["stored by the agent"]})
    assert response.status_code == 405


def test_blank_message_is_not_a_turn(make_client):
    client, _agent = make_client()
    session = client.post("/api/sessions").json()

    response = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": "   "},
    )

    assert response.status_code == 422
    assert client.get(f"/api/sessions/{session['id']}").json()["turns"] == []


def test_api_key_stops_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    with pytest.raises(ApiKeyPresent):
        create_app(tmp_path, TeachingStub())


def test_blank_api_key_does_not_stop_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    app = create_app(tmp_path, TeachingStub())
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


class SdkIdStub(TeachingStub):
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
        quizzes=(),
        **_extra,
    ):
        async for chunk in super().reply(
            session_id=session_id,
            profile=profile,
            learner_message=learner_message,
            prior_turns=prior_turns,
            sdk_session_id=sdk_session_id,
            whiteboards=whiteboards,
            pointing=pointing,
            simplify=simplify,
            quizzes=quizzes,
        ):
            yield chunk
        yield ReplyResult(sdk_session_id="sdk-from-result")


def test_finished_reply_stores_sdk_session_from_the_result(make_client, tmp_path):
    client, _agent = make_client(SdkIdStub())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Hello")

    db = sqlite3.connect(tmp_path / "polaris.db")
    try:
        row = db.execute(
            "SELECT sdk_session_id FROM sessions WHERE id = ?",
            (session["id"],),
        ).fetchone()
    finally:
        db.close()
    assert row[0] == "sdk-from-result"


def _assert_index_and_wal(db_path) -> None:
    db = sqlite3.connect(db_path)
    try:
        index = db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'index' AND name = 'turns_session_id_created_at'
            """
        ).fetchone()
        mode = db.execute("PRAGMA journal_mode").fetchone()
    finally:
        db.close()
    assert index is not None
    assert mode[0] == "wal"


def test_turn_index_and_wal_apply_to_new_and_existing_databases(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    app = create_app(fresh, TeachingStub())
    with TestClient(app) as client:
        chat = client.app.state.chat
        same = chat._conn
        assert client.get("/api/sessions").json() == {"sessions": []}
        assert chat._conn is same
    assert chat._conn is None
    _assert_index_and_wal(fresh / "polaris.db")

    existing = tmp_path / "existing"
    existing.mkdir()
    db_path = existing / "polaris.db"
    raw = sqlite3.connect(db_path)
    raw.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            ended_at TEXT,
            sdk_session_id TEXT
        );
        CREATE TABLE turns (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            learner_message TEXT NOT NULL,
            reply TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    raw.commit()
    raw.close()
    app = create_app(existing, TeachingStub())
    with TestClient(app) as client:
        assert client.get("/api/sessions").json() == {"sessions": []}
    _assert_index_and_wal(db_path)


class BoomAgent:
    """Fails before any text, the way a missing CLI or a crashed connect() does."""

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
        quizzes=(),
        **_extra,
    ):
        del session_id, profile, learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify, quizzes
        raise RuntimeError("Failed to start Claude Code")
        yield  # pragma: no cover

    async def close_session(self, session_id: str) -> None:
        del session_id


def test_unexpected_teaching_failure_yields_an_sse_error(make_client):
    client, _agent = make_client(BoomAgent())
    session = client.post("/api/sessions").json()

    response = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={"message": "hi"},
    )
    events, rest = parse_sse(response.text)

    assert response.status_code == 200, response.text
    assert rest == ""
    errors = [event["error"] for event in events if "error" in event]
    assert errors, events
    assert "ended early" not in errors[0].lower()
    assert "Failed to start Claude Code" in errors[0]
    assert not any(event.get("done") for event in events)
    assert client.get(f"/api/sessions/{session['id']}").json()["turns"] == []


def test_a_session_can_be_named(make_client):  # CH-06
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "What is a fraction?")

    renamed = client.patch(f"/api/sessions/{session['id']}", json={"name": "  Fractions "})

    assert renamed.status_code == 200
    assert renamed.json() == {"id": session["id"], "name": "Fractions"}
    listed = client.get("/api/sessions").json()["sessions"][0]
    assert listed["name"] == "Fractions"
    assert listed["preview"] == "What is a fraction?"


def test_an_unnamed_session_has_no_name(make_client):  # CH-06
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Hello")

    assert client.get("/api/sessions").json()["sessions"][0]["name"] == ""


def test_a_blank_name_removes_the_name(make_client):  # CH-07
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Hello")
    client.patch(f"/api/sessions/{session['id']}", json={"name": "Fractions"})

    cleared = client.patch(f"/api/sessions/{session['id']}", json={"name": "   "})

    assert cleared.status_code == 200
    assert client.get("/api/sessions").json()["sessions"][0]["name"] == ""


def test_a_name_over_the_limit_is_refused(make_client):  # CH-07
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Hello")

    assert client.patch(f"/api/sessions/{session['id']}", json={"name": "a" * 80}).status_code == 200
    refused = client.patch(f"/api/sessions/{session['id']}", json={"name": "a" * 81})

    assert refused.status_code == 422
    assert client.get("/api/sessions").json()["sessions"][0]["name"] == "a" * 80


def test_naming_an_unknown_session_is_not_found(make_client):
    client, _agent = make_client()

    assert client.patch("/api/sessions/nope", json={"name": "x"}).status_code == 404


def test_naming_leaves_an_ended_session_as_it_was(make_client):  # CH-08
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Remember this")
    client.post(f"/api/sessions/{session['id']}/leave")
    before = client.get(f"/api/sessions/{session['id']}").json()

    client.patch(f"/api/sessions/{session['id']}", json={"name": "Kept"})

    assert client.get(f"/api/sessions/{session['id']}").json() == before
    assert before["ended"] is True


def _rows(client, sql: str, *args: object) -> list[tuple]:
    chat = client.app.state.chat
    return chat._with_db(lambda conn: [tuple(row) for row in conn.execute(sql, args)])


def test_deleting_a_session_removes_it_and_what_was_made_in_it(make_client):  # CH-11, CH-12
    client, _agent = make_client()
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "What is a fraction?")
    board = client.post(f"/api/sessions/{session['id']}/whiteboards")
    assert board.status_code == 201
    other = client.post("/api/sessions").json()
    post_turn(client, other["id"], "Another question")

    deleted = client.delete(f"/api/sessions/{session['id']}")

    assert deleted.status_code == 200
    ids = [listed["id"] for listed in client.get("/api/sessions").json()["sessions"]]
    assert ids == [other["id"]]
    assert client.get(f"/api/sessions/{session['id']}").status_code == 404
    assert _rows(client, "SELECT id FROM turns WHERE session_id = ?", session["id"]) == []
    assert _rows(client, "SELECT id FROM artifacts WHERE session_id = ?", session["id"]) == []
    assert _rows(client, "SELECT id FROM whiteboards") == []


def test_deleting_keeps_the_profile(make_client):  # CH-12
    client, _agent = make_client(
        profile_pass=StubPass((FactChange("ADD", "likes step-by-step walkthroughs"),))
    )
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like step-by-step walkthroughs")

    deleted = client.delete(f"/api/sessions/{session['id']}")

    assert deleted.json() == {"id": session["id"], "facts_saved": True}
    assert read_profile(client) == {"facts": ["likes step-by-step walkthroughs"]}
    assert _rows(client, "SELECT id FROM fact_evidence") == []
    assert _rows(client, "SELECT id FROM profile_passes") == []


def test_deleting_the_open_session_ends_it_first(make_client):  # CH-13
    writer = StubPass()
    client, agent = make_client(profile_pass=writer)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "I like pictures")

    client.delete(f"/api/sessions/{session['id']}")

    assert writer.calls == [(("I like pictures",), ())]
    assert agent.closed == [session["id"]]


def test_deleting_stops_a_reply_in_progress(make_client):  # CH-14
    agent = GatedAgent()
    client, _agent = make_client(agent)
    chat = client.app.state.chat
    session = client.post("/api/sessions").json()

    async def scenario() -> None:
        seen: list[object] = []

        async def consume() -> None:
            async for item in chat.stream_reply(session["id"], "Tell me more"):
                seen.append(item)

        reply = asyncio.create_task(consume())
        while not seen:
            await asyncio.sleep(0.01)
        deleting = asyncio.create_task(chat.delete_session(session["id"]))
        await asyncio.sleep(0.05)
        agent.release.set()
        await deleting
        await reply

    asyncio.run(scenario())

    assert client.get("/api/sessions").json() == {"sessions": []}
    assert _rows(client, "SELECT id FROM turns") == []


def test_deleting_an_unknown_session_is_not_found(make_client):  # CH-17
    client, _agent = make_client()

    assert client.delete("/api/sessions/nope").status_code == 404


def test_a_failed_profile_pass_does_not_block_deleting(make_client):  # CH-16
    class ExplodingPass:
        async def run(self, *, turns, facts):
            del turns, facts
            raise RuntimeError("pass failed")

    client, _agent = make_client(profile_pass=ExplodingPass())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "hello")

    deleted = client.delete(f"/api/sessions/{session['id']}")

    assert deleted.status_code == 200
    assert deleted.json() == {"id": session["id"], "facts_saved": False}
    assert client.get("/api/sessions").json() == {"sessions": []}


def test_deleting_an_ended_session_waits_for_its_pass(make_client):  # CH-16
    class GatedFailingPass(GatedPass):
        async def run(self, *, turns, facts):
            del turns, facts
            await asyncio.to_thread(self.release.wait, 10)
            raise RuntimeError("pass failed")

    writer = GatedFailingPass()
    client, _agent = make_client(profile_pass=writer)
    first = client.post("/api/sessions").json()
    post_turn(client, first["id"], "hello")
    client.post("/api/sessions")

    threading.Timer(0.2, writer.release.set).start()
    deleted = client.delete(f"/api/sessions/{first['id']}")

    assert deleted.json() == {"id": first["id"], "facts_saved": False}


class WarmClient:
    """A stand-in SDK client whose connect can be held, like a cold CLI start."""

    def __init__(self, options, gate: threading.Event | None = None) -> None:
        from test_teaching import delta, result

        self.options = options
        self.messages = [delta("Hi"), result()]
        self.gate = gate
        self.connects = 0
        self.prompts: list[str] = []
        self.disconnected = False

    async def connect(self) -> None:
        self.connects += 1
        if self.gate is not None:
            await asyncio.to_thread(self.gate.wait, 10)

    async def query(self, prompt, session_id: str = "default") -> None:
        del session_id
        self.prompts.append(prompt)

    async def receive_response(self):
        for message in self.messages:
            yield message

    async def disconnect(self) -> None:
        self.disconnected = True


def _warm_agent(tmp_path, gate: threading.Event | None = None):
    from polaris.teaching import ClaudeTeachingAgent
    from test_teaching import FakeKeyCheck

    created: list[WarmClient] = []

    def factory(options):
        client = WarmClient(options, gate)
        created.append(client)
        return client

    agent = ClaudeTeachingAgent(
        tmp_path / "claude-work", client_factory=factory, key_check=FakeKeyCheck()
    )
    return agent, created


def wait_for_warm_ups(client: TestClient) -> None:
    chat = client.app.state.chat
    for _ in range(200):
        if not chat._warm_tasks:
            return
        threading.Event().wait(0.01)
    raise AssertionError("A warm-up did not finish.")


def test_typing_warms_the_client_the_first_reply_uses(make_client, tmp_path):
    agent, created = _warm_agent(tmp_path)
    client, _agent = make_client(agent=agent)
    session = client.post("/api/sessions").json()

    warmed = client.post(f"/api/sessions/{session['id']}/warm")
    wait_for_warm_ups(client)
    assert warmed.status_code == 202
    assert len(created) == 1
    assert created[0].connects == 1
    assert created[0].prompts == []

    assert reply_text(post_turn(client, session["id"], "What is a half?")) == "Hi"
    client.post(f"/api/sessions/{session['id']}/warm")
    wait_for_warm_ups(client)

    assert len(created) == 1
    assert created[0].connects == 1
    assert len(created[0].prompts) == 1


def test_a_reply_waits_for_a_warm_up_still_connecting(make_client, tmp_path):
    gate = threading.Event()
    agent, created = _warm_agent(tmp_path, gate)
    client, _agent = make_client(agent=agent)
    session = client.post("/api/sessions").json()

    client.post(f"/api/sessions/{session['id']}/warm")
    threading.Timer(0.2, gate.set).start()
    assert reply_text(post_turn(client, session["id"], "What is a half?")) == "Hi"

    assert len(created) == 1
    assert created[0].connects == 1


def test_warming_an_ended_session_does_nothing(make_client, tmp_path):
    agent, created = _warm_agent(tmp_path)
    client, _agent = make_client(agent=agent)
    first = client.post("/api/sessions").json()
    client.post("/api/sessions")
    client.app.state.chat.wait_for_session_ends()

    assert client.post(f"/api/sessions/{first['id']}/warm").status_code == 202
    assert client.post("/api/sessions/nope/warm").status_code == 202
    wait_for_warm_ups(client)

    assert created == []
    assert agent._clients == {}


def test_ending_a_session_while_it_warms_leaves_no_client(make_client, tmp_path):  # CH-05
    gate = threading.Event()
    agent, created = _warm_agent(tmp_path, gate)
    client, _agent = make_client(agent=agent)
    first = client.post("/api/sessions").json()
    client.post(f"/api/sessions/{first['id']}/warm")
    for _ in range(200):
        if created:
            break
        threading.Event().wait(0.01)

    client.post("/api/sessions")
    gate.set()
    client.app.state.chat.wait_for_session_ends()
    wait_for_warm_ups(client)

    assert len(created) == 1
    assert created[0].disconnected is True
    assert agent._clients == {}


class StubTitles:
    """Returns a fixed title and records what it was shown (CH-20)."""

    def __init__(self, title: str = "Adding fractions") -> None:
        self.title = title
        self.messages: list[str] = []

    async def write(self, message: str) -> str:
        self.messages.append(message)
        return self.title


class GatedTitles(StubTitles):
    def __init__(self, title: str = "Adding fractions") -> None:
        super().__init__(title)
        self.release = threading.Event()

    async def write(self, message: str) -> str:
        await asyncio.to_thread(self.release.wait, 10)
        return await super().write(message)


class FailingTitles(StubTitles):
    async def write(self, message: str) -> str:
        self.messages.append(message)
        raise RuntimeError("no title")


def listed_sessions(client) -> list[dict]:
    return client.get("/api/sessions").json()["sessions"]


def wait_for_title(client, expected: str, seconds: float = 5.0) -> dict:
    """The title is written after the reply, so poll the list for it."""

    import time

    deadline = time.monotonic() + seconds
    while True:
        rows = listed_sessions(client)
        if rows and rows[0]["title"] == expected:
            return rows[0]
        assert time.monotonic() < deadline, rows
        time.sleep(0.02)


def test_a_session_without_a_message_is_not_listed(make_client):  # CH-18
    client, _agent = make_client()
    client.post("/api/sessions")

    assert listed_sessions(client) == []


def test_the_first_send_lists_the_session_with_its_message(make_client):  # CH-20
    agent = GatedAgent()
    client, _agent = make_client(agent)
    session = client.post("/api/sessions").json()
    scope_events: list[dict] = []

    def send() -> None:
        scope_events.extend(post_turn(client, session["id"], "What is a fraction?"))

    thread = threading.Thread(target=send)
    thread.start()
    try:
        import time

        deadline = time.monotonic() + 5
        while not listed_sessions(client):
            assert time.monotonic() < deadline
            time.sleep(0.02)
        row = listed_sessions(client)[0]
        assert row["id"] == session["id"]
        assert row["preview"] == "What is a fraction?"
    finally:
        agent.release.set()
        thread.join(10)


def test_the_title_is_written_from_the_first_message_only(make_client):  # CH-20, CH-21
    titles = StubTitles("Adding fractions")
    client, _agent = make_client(title_writer=titles)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "  How do I add 1/2 and 1/3?  ")

    row = wait_for_title(client, "Adding fractions")

    assert titles.messages == ["How do I add 1/2 and 1/3?"]
    assert row["name"] == ""
    assert row["preview"] == "How do I add 1/2 and 1/3?"


def test_the_title_is_written_once(make_client):  # CH-20
    titles = StubTitles()
    client, _agent = make_client(title_writer=titles)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "First")
    wait_for_title(client, "Adding fractions")

    post_turn(client, session["id"], "Second")
    client.post(f"/api/sessions/{session['id']}/leave")
    client.post(f"/api/sessions/{session['id']}/open")
    post_turn(client, session["id"], "Third")

    assert titles.messages == ["First"]


def test_a_failed_title_keeps_the_first_message_label(make_client):  # CH-21
    titles = FailingTitles()
    client, _agent = make_client(title_writer=titles)
    session = client.post("/api/sessions").json()

    post_turn(client, session["id"], "Why is the sky blue?")
    post_turn(client, session["id"], "And at sunset?")

    row = listed_sessions(client)[0]
    assert row["title"] == ""
    assert row["preview"] == "Why is the sky blue?"
    assert titles.messages == ["Why is the sky blue?"]


def test_a_title_is_cleaned_and_limited(make_client):  # CH-21
    titles = StubTitles('  "**Fractions**"\nextra line ' + "x" * 200)
    client, _agent = make_client(title_writer=titles)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Fractions please")

    row = wait_for_title(client, "Fractions")

    assert len(row["title"]) <= 80


def test_a_name_beats_a_late_title(make_client):  # CH-21
    titles = GatedTitles("Adding fractions")
    client, _agent = make_client(title_writer=titles)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Add fractions")
    client.patch(f"/api/sessions/{session['id']}", json={"name": "Fractions"})

    titles.release.set()
    row = wait_for_title(client, "Adding fractions")

    assert row["name"] == "Fractions"


def test_a_title_for_a_deleted_session_is_dropped(make_client):  # CH-21, CH-14
    titles = GatedTitles()
    client, _agent = make_client(title_writer=titles)
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Add fractions")

    assert client.delete(f"/api/sessions/{session['id']}").status_code == 200
    titles.release.set()
    import time

    time.sleep(0.2)

    assert listed_sessions(client) == []
    assert client.get(f"/api/sessions/{session['id']}").status_code == 404


def test_an_older_session_gets_no_title(make_client, tmp_path):  # CH-22
    client, _agent = make_client(title_writer=StubTitles())
    session = client.post("/api/sessions").json()
    post_turn(client, session["id"], "Hello")
    wait_for_title(client, "Adding fractions")
    # A session saved before generated titles: no title, no first_message.
    db = sqlite3.connect(tmp_path / "polaris.db")
    db.execute("UPDATE sessions SET generated_title = NULL, first_message = NULL")
    db.commit()
    db.close()

    row = listed_sessions(client)[0]

    assert row["title"] == ""
    assert row["preview"] == "Hello"


def test_leaving_a_draft_discards_it(make_client):  # CH-19
    pass_ = StubPass()
    client, agent = make_client(profile_pass=pass_)
    draft = client.post("/api/sessions").json()

    client.post(f"/api/sessions/{draft['id']}/leave")

    assert client.get(f"/api/sessions/{draft['id']}").status_code == 404
    assert listed_sessions(client) == []
    assert pass_.calls == []


def test_starting_another_session_discards_the_draft(make_client):  # CH-19
    pass_ = StubPass()
    client, _agent = make_client(profile_pass=pass_)
    draft = client.post("/api/sessions").json()

    other = client.post("/api/sessions").json()

    assert client.get(f"/api/sessions/{draft['id']}").status_code == 404
    assert client.get(f"/api/sessions/{other['id']}").status_code == 200
    assert pass_.calls == []


def test_opening_a_session_discards_the_draft(make_client):  # CH-19
    pass_ = StubPass()
    client, _agent = make_client(profile_pass=pass_)
    earlier = client.post("/api/sessions").json()
    post_turn(client, earlier["id"], "Earlier question")
    client.post(f"/api/sessions/{earlier['id']}/leave")
    draft = client.post("/api/sessions").json()

    client.post(f"/api/sessions/{earlier['id']}/open")

    assert client.get(f"/api/sessions/{draft['id']}").status_code == 404
    assert [row["id"] for row in listed_sessions(client)] == [earlier["id"]]


def test_a_draft_drops_its_held_resource(make_client, tmp_path):  # CH-19
    client, _agent = make_client()
    draft = client.post("/api/sessions").json()
    client.post(
        f"/api/sessions/{draft['id']}/resources/notes",
        json={"name": "Notes", "text": "Fractions"},
    )

    client.post(f"/api/sessions/{draft['id']}/leave")

    db = sqlite3.connect(tmp_path / "polaris.db")
    try:
        assert db.execute("SELECT id FROM resources").fetchall() == []
    finally:
        db.close()
