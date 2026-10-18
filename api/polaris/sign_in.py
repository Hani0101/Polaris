"""The local sign-in for the one learner: AU-03 to AU-13 and decision 0008.

There is one username and password pair, chosen the first time the page is
used. The password is stored only as a salted scrypt hash. Signing in gives a
60-minute access token, signed with a key made at first run, and a 7-day
refresh token whose hash alone is stored. Each refresh replaces the refresh
token; reusing a replaced one ends the whole sign-in. Five wrong tries in a
row block sign-in for 10 minutes, and the count is stored.

This is not the Claude login (decision 0001) and not Google OAuth.
"""

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ACCESS_TTL = timedelta(minutes=60)
REFRESH_TTL = timedelta(days=7)
MAX_WRONG_TRIES = 5
BLOCK_FOR = timedelta(minutes=10)
MIN_PASSWORD_LENGTH = 8
REFRESH_COOKIE = "polaris_refresh"
REFRESH_PATH = "/api/sign-in/refresh"
KEY_BYTES = 32

# scrypt cost: about 16 MB and a few tens of milliseconds a try.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class PairRefused(Exception):
    """The chosen pair breaks AU-05. The message says which rule."""


class PairAlreadyStored(Exception):
    def __init__(self) -> None:
        super().__init__("A username and password are already chosen. Sign in with them.")


class NoPairStored(Exception):
    def __init__(self) -> None:
        super().__init__("Choose a username and password first.")


class WrongPair(Exception):
    """AU-06: the message does not say which part was wrong."""

    def __init__(self) -> None:
        super().__init__("That username and password don't match.")


class SignInBlocked(Exception):
    def __init__(self, seconds_left: int) -> None:
        self.seconds_left = seconds_left
        super().__init__("Sign-in is paused after five tries that didn't match.")


class RefreshRefused(Exception):
    """The refresh token is missing, expired, replaced, or revoked."""


@dataclass(frozen=True)
class Tokens:
    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_max_age: int
    username: str


def create_sign_in_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sign_in_pair (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sign_in_tries (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            wrong_in_a_row INTEGER NOT NULL,
            blocked_until TEXT
        )
        """
    )
    # One row per sign-in. Its refresh tokens are one family (AU-09).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sign_ins (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            revoked_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            token_hash TEXT PRIMARY KEY,
            sign_in_id TEXT NOT NULL REFERENCES sign_ins(id),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            replaced_at TEXT
        )
        """
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return "$".join(
        ("scrypt", str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P), _b64(salt), _b64(digest))
    )


def password_matches(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        tried = _scrypt(password, _unb64(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(tried, _unb64(digest))


class SignIn:
    """The stored pair, the lockout count, and the tokens, all on this machine."""

    def __init__(
        self,
        data_dir: Path,
        with_db: Callable[[Callable[[sqlite3.Connection], Any]], Any],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._with_db = with_db
        # Tests move the clock to expire tokens and end a block.
        self.clock = clock or (lambda: datetime.now(UTC))
        self._key = _signing_key(data_dir / "sign-in.key")
        # A stand-in hash, so a wrong username costs as long as a wrong password.
        self._decoy = hash_password(secrets.token_urlsafe(16))
        with_db(create_sign_in_tables)

    def status(self) -> dict[str, object]:
        """What the page needs before it draws a form: AU-05 or AU-06, and AU-13."""

        def read(conn: sqlite3.Connection) -> dict[str, object]:
            return {
                "pair_stored": _stored_pair(conn) is not None,
                "blocked_seconds": self._seconds_left(conn),
            }

        return self._with_db(read)

    def choose_pair(self, username: str, password: str, password_again: str) -> Tokens:
        """AU-05: the first use stores the pair, then signs the learner in."""

        username = username.strip()
        if not username:
            raise PairRefused("Enter a username.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise PairRefused(f"Use at least {MIN_PASSWORD_LENGTH} characters for the password.")
        if password != password_again:
            raise PairRefused("The two passwords don't match. Enter the same password twice.")
        password_hash = hash_password(password)

        def write(conn: sqlite3.Connection) -> Tokens:
            if _stored_pair(conn) is not None:
                raise PairAlreadyStored()
            conn.execute(
                """
                INSERT INTO sign_in_pair (id, username, password_hash, created_at)
                VALUES (1, ?, ?, ?)
                """,
                (username, password_hash, self._stamp()),
            )
            return self._start(conn, username)

        return self._with_db(write)

    def sign_in(self, username: str, password: str) -> Tokens:
        """AU-06 and AU-13. A block refuses even the correct pair."""

        def check_block(conn: sqlite3.Connection) -> tuple[str, str] | None:
            seconds_left = self._seconds_left(conn)
            if seconds_left:
                raise SignInBlocked(seconds_left)
            pair = _stored_pair(conn)
            if pair is None:
                raise NoPairStored()
            return pair

        stored_username, stored_hash = self._with_db(check_block)
        # The hash runs outside the database lock, and always runs, so the
        # time taken does not say whether the username was right.
        username_ok = hmac.compare_digest(
            username.strip().encode("utf-8"), stored_username.encode("utf-8")
        )
        password_ok = password_matches(password, stored_hash if username_ok else self._decoy)

        def record(conn: sqlite3.Connection) -> Tokens | None:
            # A block that began while this try was hashing still refuses it.
            seconds_left = self._seconds_left(conn)
            if seconds_left:
                raise SignInBlocked(seconds_left)
            if username_ok and password_ok:
                conn.execute("DELETE FROM sign_in_tries")
                return self._start(conn, stored_username)
            self._count_wrong_try(conn)
            return None

        tokens = self._with_db(record)
        if tokens is None:
            seconds_left = self._with_db(self._seconds_left)
            if seconds_left:
                raise SignInBlocked(seconds_left)
            raise WrongPair()
        return tokens

    def refresh(self, refresh_token: str | None) -> Tokens:
        """AU-09: a live refresh token is replaced. A replaced one ends the sign-in."""

        if not refresh_token:
            raise RefreshRefused()
        token_hash = _token_hash(refresh_token)

        def write(conn: sqlite3.Connection) -> Tokens | None:
            row = conn.execute(
                """
                SELECT t.sign_in_id, t.expires_at, t.replaced_at, s.revoked_at
                FROM refresh_tokens t JOIN sign_ins s ON s.id = t.sign_in_id
                WHERE t.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None or row["revoked_at"] is not None:
                return None
            if row["replaced_at"] is not None:
                # Someone kept an old token: end every token of this sign-in.
                self._revoke(conn, row["sign_in_id"])
                return None
            now = self.clock()
            if datetime.fromisoformat(row["expires_at"]) <= now:
                return None
            conn.execute(
                "UPDATE refresh_tokens SET replaced_at = ? WHERE token_hash = ?",
                (now.isoformat(), token_hash),
            )
            pair = _stored_pair(conn)
            if pair is None:
                return None
            return self._issue(conn, row["sign_in_id"], pair[0])

        # The revoke above must be kept, so refusing happens after the commit.
        tokens = self._with_db(write)
        if tokens is None:
            raise RefreshRefused()
        return tokens

    def sign_out(self, refresh_token: str | None) -> None:
        """AU-11: end the sign-in this refresh token belongs to. The profile stays."""

        if not refresh_token:
            return
        token_hash = _token_hash(refresh_token)

        def write(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT sign_in_id FROM refresh_tokens WHERE token_hash = ?", (token_hash,)
            ).fetchone()
            if row is not None:
                self._revoke(conn, row["sign_in_id"])

        self._with_db(write)

    def signed_in(self, authorization: str | None) -> bool:
        """AU-12: a valid, unexpired access token from a sign-in not ended since."""

        if not authorization:
            return False
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return False
        claims = self._verify(token.strip())
        if claims is None:
            return False
        sign_in_id = claims.get("sid")

        def read(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                "SELECT revoked_at FROM sign_ins WHERE id = ?", (sign_in_id,)
            ).fetchone()
            return row is not None and row["revoked_at"] is None

        return self._with_db(read)

    def _start(self, conn: sqlite3.Connection, username: str) -> Tokens:
        sign_in_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO sign_ins (id, created_at) VALUES (?, ?)",
            (sign_in_id, self._stamp()),
        )
        return self._issue(conn, sign_in_id, username)

    def _issue(self, conn: sqlite3.Connection, sign_in_id: str, username: str) -> Tokens:
        now = self.clock()
        refresh_token = secrets.token_urlsafe(32)
        conn.execute(
            """
            INSERT INTO refresh_tokens (token_hash, sign_in_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                _token_hash(refresh_token),
                sign_in_id,
                now.isoformat(),
                (now + REFRESH_TTL).isoformat(),
            ),
        )
        access_token = self._sign(
            {
                "sub": "learner",
                "sid": sign_in_id,
                "iat": int(now.timestamp()),
                "exp": int((now + ACCESS_TTL).timestamp()),
            }
        )
        return Tokens(
            access_token=access_token,
            access_expires_in=int(ACCESS_TTL.total_seconds()),
            refresh_token=refresh_token,
            refresh_max_age=int(REFRESH_TTL.total_seconds()),
            username=username,
        )

    def _revoke(self, conn: sqlite3.Connection, sign_in_id: str) -> None:
        conn.execute(
            "UPDATE sign_ins SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
            (self._stamp(), sign_in_id),
        )

    def _count_wrong_try(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT wrong_in_a_row FROM sign_in_tries WHERE id = 1").fetchone()
        wrong = (row["wrong_in_a_row"] if row is not None else 0) + 1
        blocked_until = None
        if wrong >= MAX_WRONG_TRIES:
            blocked_until = (self.clock() + BLOCK_FOR).isoformat()
            wrong = 0
        conn.execute(
            """
            INSERT INTO sign_in_tries (id, wrong_in_a_row, blocked_until) VALUES (1, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                wrong_in_a_row = excluded.wrong_in_a_row,
                blocked_until = excluded.blocked_until
            """,
            (wrong, blocked_until),
        )

    def _seconds_left(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT blocked_until FROM sign_in_tries WHERE id = 1").fetchone()
        if row is None or row["blocked_until"] is None:
            return 0
        left = (datetime.fromisoformat(row["blocked_until"]) - self.clock()).total_seconds()
        return max(0, math.ceil(left))

    def _stamp(self) -> str:
        return self.clock().isoformat()

    def _sign(self, claims: dict[str, object]) -> str:
        header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
        signed = f"{header}.{payload}"
        signature = hmac.new(self._key, signed.encode("ascii"), hashlib.sha256).digest()
        return f"{signed}.{_b64(signature)}"

    def _verify(self, token: str) -> dict[str, Any] | None:
        try:
            header, payload, signature = token.split(".")
            expected = hmac.new(
                self._key, f"{header}.{payload}".encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(expected, _unb64(signature)):
                return None
            if json.loads(_unb64(header)) != {"alg": "HS256", "typ": "JWT"}:
                return None
            claims = json.loads(_unb64(payload))
        except (ValueError, UnicodeError):
            return None
        if not isinstance(claims, dict) or not isinstance(claims.get("exp"), int):
            return None
        if claims["exp"] <= self.clock().timestamp():
            return None
        return claims


def _stored_pair(conn: sqlite3.Connection) -> tuple[str, str] | None:
    row = conn.execute("SELECT username, password_hash FROM sign_in_pair WHERE id = 1").fetchone()
    return None if row is None else (row["username"], row["password_hash"])


def _signing_key(path: Path) -> bytes:
    """Made at first run and kept on the machine (decision 0008)."""

    try:
        return _read_signing_key(path)
    except FileNotFoundError:
        pass
    key = secrets.token_bytes(KEY_BYTES)
    # Only this user can read it on POSIX; on Windows it takes the folder's
    # access. O_EXCL keeps a second start from replacing it.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _read_signing_key(path)
    with os.fdopen(fd, "w", encoding="ascii") as file:
        file.write(_b64(key))
    return key


def _read_signing_key(path: Path) -> bytes:
    # An empty or damaged file must not become a short key that anyone can sign with.
    try:
        key = _unb64(path.read_text(encoding="ascii").strip())
    except ValueError:
        key = b""
    if len(key) != KEY_BYTES:
        raise RuntimeError(
            f"{path} is not a sign-in key. Delete it and restart Polaris; "
            "the learner then signs in again."
        )
    return key


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, maxmem=64 * 1024 * 1024, dklen=32
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
