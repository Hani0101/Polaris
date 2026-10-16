"""Chat scenarios: CH-01, CH-03, CH-04, CH-05, PR-01, PR-02, PR-03, and decision 0001.

An empty profile is asked for on every reply and is not written.
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

EMPTY_PROFILE_REPLY = (
    "What should I know before I teach? "
    "How do you want to be taught, what can you already do, and where do you struggle?"
)


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
    ):
        del session_id, prior_turns, sdk_session_id, whiteboards, pointing, simplify
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
    ):
        del session_id, profile, learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
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


def post_turn(client: TestClient, session_id: str, message: str) -> list[dict]:
    response = client.post(
        f"/api/sessions/{session_id}/turns",
        json={"message": message},
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


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    opened: list[TestClient] = []

    def make(agent=None, profile: str | None = None):
        if profile is not None:
            (tmp_path / "profile.json").write_text(profile, encoding="utf-8")
        stub = TeachingStub() if agent is None else agent
        client = TestClient(create_app(tmp_path, stub))
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

    left = client.post(f"/api/sessions/{session['id']}/leave")

    assert left.json()["ended"] is True
    assert client.get(f"/api/sessions/{session['id']}").json()["ended"] is True
    assert agent.closed == [session["id"]]


def test_switching_sessions_ends_the_one_left(make_client):
    client, agent = make_client()
    first = client.post("/api/sessions").json()
    second = client.post("/api/sessions").json()

    assert client.get(f"/api/sessions/{first['id']}").json()["ended"] is True
    assert second["ended"] is False
    assert agent.closed == [first["id"]]

    reopened = client.post(f"/api/sessions/{first['id']}/open")
    assert reopened.status_code == 200
    assert reopened.json()["ended"] is False
    assert client.get(f"/api/sessions/{second['id']}").json()["ended"] is True
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
    assert (tmp_path / "profile.json").read_text(encoding="utf-8") == raw


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
    assert client.get("/api/profile").json() == {"facts": []}


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
    ):
        del session_id, profile, learner_message, prior_turns, sdk_session_id, whiteboards, pointing, simplify
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
