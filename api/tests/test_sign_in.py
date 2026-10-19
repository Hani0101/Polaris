"""Sign-in scenarios: AU-01, AU-04 to AU-09, AU-11 to AU-13, and decision 0008."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from polaris.app import create_app
from polaris.sign_in import REFRESH_COOKIE, REFRESH_PATH, password_matches

USERNAME = "ada"
PASSWORD = "correct horse"
START = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


class QuietAgent:
    async def reply(self, **_kwargs):
        yield "A fraction is part of a whole."

    async def close_session(self, session_id: str) -> None:
        del session_id


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def move(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    opened: list[TestClient] = []

    def make() -> tuple[TestClient, Clock]:
        client = TestClient(create_app(tmp_path, QuietAgent()))
        clock = Clock()
        client.app.state.chat.sign_in.clock = clock
        client.__enter__()
        opened.append(client)
        return client, clock

    yield make
    for client in opened:
        client.__exit__(None, None, None)


def choose(client: TestClient, username=USERNAME, password=PASSWORD, again=None):
    return client.post(
        "/api/sign-in/pair",
        json={
            "username": username,
            "password": password,
            "password_again": password if again is None else again,
        },
    )


def sign_in(client: TestClient, username=USERNAME, password=PASSWORD):
    return client.post("/api/sign-in", json={"username": username, "password": password})


def bearer(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def refresh_cookie(response) -> str:
    return response.cookies[REFRESH_COOKIE]


def hold_cookie(client: TestClient, token: str) -> None:
    """The browser holds this one refresh token, and nothing else."""

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token, path=REFRESH_PATH)


def refresh_with(client: TestClient, token: str):
    hold_cookie(client, token)
    return client.post(REFRESH_PATH)


def db_rows(tmp_path, query: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(tmp_path / "polaris.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def test_the_app_opens_with_no_sign_in(make_client):  # AU-01
    client, _clock = make_client()

    session = client.post("/api/sessions")
    turn = client.post(f"/api/sessions/{session.json()['id']}/turns", json={"message": "Hi"})

    assert session.status_code == 200
    assert turn.status_code == 200
    assert '"done": true' in turn.text


def test_the_first_visit_chooses_the_pair(make_client, tmp_path):  # AU-04, AU-05
    client, _clock = make_client()
    assert client.get("/api/sign-in").json() == {"pair_stored": False, "blocked_seconds": 0}

    chosen = choose(client)

    assert chosen.status_code == 200
    assert chosen.json()["username"] == USERNAME
    assert client.get("/api/sign-in").json()["pair_stored"] is True
    (row,) = db_rows(tmp_path, "SELECT username, password_hash FROM sign_in_pair")
    assert row["username"] == USERNAME
    assert PASSWORD not in row["password_hash"]
    assert row["password_hash"].startswith("scrypt$")
    assert password_matches(PASSWORD, row["password_hash"])


@pytest.mark.parametrize(
    ("username", "password", "again"),
    [
        ("   ", PASSWORD, PASSWORD),
        (USERNAME, "short", "short"),
        (USERNAME, PASSWORD, PASSWORD + "x"),
    ],
)
def test_a_pair_that_breaks_the_rules_is_refused(make_client, username, password, again):  # AU-05
    client, _clock = make_client()

    refused = choose(client, username, password, again)

    assert refused.status_code == 422
    assert client.get("/api/sign-in").json()["pair_stored"] is False


def test_there_is_no_second_pair(make_client):  # AU-04, AU-07
    client, _clock = make_client()
    choose(client)

    second = choose(client, "someone", "another password")

    assert second.status_code == 409
    assert sign_in(client, "someone", "another password").status_code == 401
    assert sign_in(client).status_code == 200


def test_a_matching_pair_signs_the_learner_in(make_client):  # AU-06, AU-08, AU-09
    client, _clock = make_client()
    choose(client)

    signed_in = sign_in(client)

    assert signed_in.status_code == 200
    body = signed_in.json()
    assert body["expires_in"] == 60 * 60
    assert set(body) == {"access_token", "expires_in", "username"}
    cookie = signed_in.headers["set-cookie"]
    assert f"{REFRESH_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert f"Path={REFRESH_PATH}" in cookie
    assert f"Max-Age={7 * 24 * 60 * 60}" in cookie


def test_a_mismatch_does_not_say_which_part_was_wrong(make_client):  # AU-06
    client, _clock = make_client()
    choose(client)

    wrong_name = sign_in(client, "grace", PASSWORD)
    wrong_password = sign_in(client, USERNAME, "not the password")

    assert wrong_name.status_code == wrong_password.status_code == 401
    assert wrong_name.json() == wrong_password.json()
    assert REFRESH_COOKIE not in wrong_name.cookies


def test_the_server_stores_only_a_hash_of_the_refresh_token(make_client, tmp_path):  # AU-09
    client, _clock = make_client()
    token = refresh_cookie(choose(client))

    hashes = [row["token_hash"] for row in db_rows(tmp_path, "SELECT token_hash FROM refresh_tokens")]

    assert token not in hashes
    assert len(hashes) == 1


def test_refreshing_replaces_the_refresh_token(make_client):  # AU-09
    client, _clock = make_client()
    old = refresh_cookie(choose(client))

    refreshed = refresh_with(client, old)

    assert refreshed.status_code == 200
    new = refresh_cookie(refreshed)
    assert new != old
    assert client.get("/api/profile", headers=bearer(refreshed)).status_code == 200
    assert refresh_with(client, old).status_code == 401


def test_reusing_an_ended_refresh_token_revokes_the_sign_in(make_client):  # AU-09
    client, _clock = make_client()
    first = choose(client)
    old = refresh_cookie(first)
    refreshed = refresh_with(client, old)
    newest = refresh_cookie(refreshed)

    reused = refresh_with(client, old)

    assert reused.status_code == 401
    assert refresh_with(client, newest).status_code == 401
    assert client.get("/api/profile", headers=bearer(refreshed)).status_code == 401
    assert client.get("/api/profile", headers=bearer(first)).status_code == 401


def test_an_expired_refresh_token_is_refused(make_client):  # AU-09, AU-10
    client, clock = make_client()
    token = refresh_cookie(choose(client))

    clock.move(days=7, seconds=1)

    refused = refresh_with(client, token)
    assert refused.status_code == 401
    assert f'{REFRESH_COOKIE}=""' in refused.headers["set-cookie"]


def test_an_access_token_lasts_sixty_minutes(make_client):  # AU-08
    client, clock = make_client()
    signed_in = choose(client)

    clock.move(minutes=59)
    assert client.get("/api/profile", headers=bearer(signed_in)).status_code == 200
    clock.move(minutes=1)
    assert client.get("/api/profile", headers=bearer(signed_in)).status_code == 401


def test_signing_out_ends_the_sign_in_and_keeps_the_profile(make_client, tmp_path):  # AU-11
    client, _clock = make_client()
    signed_in = choose(client)
    token = refresh_cookie(signed_in)
    conn = sqlite3.connect(tmp_path / "polaris.db")
    conn.execute(
        """
        INSERT INTO facts (id, kind, text, basis, written_by, created_at, updated_at)
        VALUES ('f1', 'struggle', 'struggles with fractions', 'stated', 'pass', 'x', 'x')
        """
    )
    conn.commit()
    conn.close()

    hold_cookie(client, token)
    out = client.delete(REFRESH_PATH)

    assert out.status_code == 200
    assert f'{REFRESH_COOKIE}=""' in out.headers["set-cookie"]
    assert refresh_with(client, token).status_code == 401
    assert client.get("/api/profile", headers=bearer(signed_in)).status_code == 401
    again = sign_in(client)
    assert client.get("/api/profile", headers=bearer(again)).json() == {
        "facts": ["struggles with fractions"]
    }


def test_the_profile_is_unreachable_without_a_token(make_client):  # AU-12
    client, _clock = make_client()
    choose(client)

    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get("/api/profile", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/sessions").status_code == 200


def test_a_token_signed_with_another_key_is_refused(make_client, tmp_path):  # AU-12
    client, _clock = make_client()
    signed_in = choose(client)
    header, payload, _signature = signed_in.json()["access_token"].split(".")

    forged = f"{header}.{payload}.AAAA"

    assert client.get("/api/profile", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_five_wrong_tries_lock_sign_in_for_ten_minutes(make_client):  # AU-13
    client, clock = make_client()
    choose(client)

    for _ in range(4):
        assert sign_in(client, password="not the password").status_code == 401
    fifth = sign_in(client, password="not the password")

    assert fifth.status_code == 429
    assert fifth.json()["blocked_seconds"] == 600
    blocked = sign_in(client)
    assert blocked.status_code == 429
    clock.move(minutes=4)
    assert client.get("/api/sign-in").json()["blocked_seconds"] == 360
    assert sign_in(client).status_code == 429
    clock.move(minutes=6)
    assert sign_in(client).status_code == 200


def test_a_successful_sign_in_resets_the_count(make_client):  # AU-13
    client, _clock = make_client()
    choose(client)
    for _ in range(4):
        sign_in(client, password="not the password")

    assert sign_in(client).status_code == 200
    for _ in range(4):
        assert sign_in(client, password="not the password").status_code == 401


def test_a_restart_does_not_clear_the_lockout(make_client):  # AU-13
    client, clock = make_client()
    choose(client)
    for _ in range(5):
        sign_in(client, password="not the password")
    client.__exit__(None, None, None)

    restarted, restarted_clock = make_client()
    restarted_clock.now = clock.now + timedelta(minutes=1)

    assert sign_in(restarted).status_code == 429
    assert restarted.get("/api/sign-in").json()["blocked_seconds"] == 540


def test_the_signing_key_is_kept_on_the_machine(make_client, tmp_path):  # decision 0008
    client, _clock = make_client()
    signed_in = choose(client)
    client.__exit__(None, None, None)

    restarted, _restarted_clock = make_client()

    assert (tmp_path / "sign-in.key").exists()
    assert restarted.get("/api/profile", headers=bearer(signed_in)).status_code == 200


@pytest.mark.parametrize("text", ["", "not a key", "c2hvcnQ"])
def test_a_damaged_signing_key_is_not_used(tmp_path, monkeypatch, text):  # decision 0008
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "sign-in.key").write_text(text, encoding="ascii")

    with pytest.raises(RuntimeError, match="not a sign-in key"):
        create_app(tmp_path, QuietAgent())


@pytest.mark.parametrize(
    ("base_url", "address", "answered"),
    [
        ("http://localhost:5173", "127.0.0.1", True),
        ("http://127.0.0.1:8000", "127.0.0.1", True),
        ("http://[::1]:8000", "::1", True),
        ("http://rebound.example:8000", "127.0.0.1", False),
        ("http://localhost:8000", "192.168.1.20", False),
    ],
)
def test_only_this_machine_is_answered(tmp_path, monkeypatch, base_url, address, answered):  # AU-14
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = create_app(tmp_path, QuietAgent())

    with TestClient(app, base_url=base_url, client=(address, 50000)) as client:
        assert client.get("/api/sessions").status_code == (200 if answered else 403)
        assert choose(client).status_code == (200 if answered else 403)
