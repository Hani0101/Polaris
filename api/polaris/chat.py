"""Sessions made of turns. The profile is read before each reply and never written."""

import asyncio
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

from polaris.agent import ReplyAgent, ReplyResult
from polaris.models import Turn
from polaris.profile import load_profile


class MissingSession(Exception):
    def __init__(self) -> None:
        super().__init__("No session with that id.")


class BlankMessage(Exception):
    def __init__(self) -> None:
        super().__init__("A turn needs a typed message.")


class SessionEnded(Exception):
    def __init__(self) -> None:
        super().__init__("That session has ended. Open it to continue.")


class ReplyInProgress(Exception):
    def __init__(self) -> None:
        super().__init__("A reply is still being produced.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Chat:
    def __init__(self, data_dir: Path, agent: ReplyAgent) -> None:
        self.data_dir = data_dir
        self.agent = agent
        self.db_path = data_dir / "polaris.db"
        self.profile_path = data_dir / "profile.json"
        self._lock = threading.Lock()
        self._busy: set[str] = set()
        self._conn: sqlite3.Connection | None = None
        self._open_db()
        self._init_db()

    def list_sessions(self) -> list[dict[str, object]]:
        def read(conn: sqlite3.Connection) -> list[dict[str, object]]:
            rows = conn.execute(
                """
                SELECT s.id, s.ended_at,
                    (
                        SELECT t.learner_message
                        FROM turns t
                        WHERE t.session_id = s.id
                        ORDER BY t.created_at ASC, t.id ASC
                        LIMIT 1
                    ) AS preview
                FROM sessions s
                ORDER BY s.created_at DESC
                """
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "ended": row["ended_at"] is not None,
                    "preview": row["preview"] or "",
                }
                for row in rows
            ]

        return self._with_db(read)

    def start(self) -> tuple[dict[str, object], tuple[str, ...]]:
        ended = self._end_open(except_id=None)
        session_id = str(uuid.uuid4())

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO sessions (id, created_at, ended_at, sdk_session_id) VALUES (?, ?, NULL, NULL)",
                (session_id, _now()),
            )

        self._with_db(write)
        return self._payload(session_id), ended

    def open(self, session_id: str) -> tuple[dict[str, object], tuple[str, ...]]:
        self._require(session_id)
        ended = self._end_open(except_id=session_id)

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET ended_at = NULL WHERE id = ?",
                (session_id,),
            )

        self._with_db(write)
        return self._payload(session_id), ended

    def leave(self, session_id: str) -> bool:
        """Mark the session ended. Return whether it was open and needs the agent closed."""

        row = self._require(session_id)
        if row["ended_at"] is not None:
            return False

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (_now(), session_id),
            )

        self._with_db(write)
        return True

    def get(self, session_id: str) -> dict[str, object]:
        self._require(session_id)
        return self._payload(session_id)

    def validate_turn(self, session_id: str, message: str) -> str:
        text = message.strip()
        if not text:
            raise BlankMessage()
        row = self._require(session_id)
        if row["ended_at"] is not None:
            raise SessionEnded()
        return text

    def raise_if_busy(self, session_id: str) -> None:
        """Reject a second reply. Call this on the event loop; _busy is not locked."""

        if session_id in self._busy:
            raise ReplyInProgress()

    async def stream_reply(self, session_id: str, message: str) -> AsyncIterator[str]:
        text = await asyncio.to_thread(self.validate_turn, session_id, message)
        self.raise_if_busy(session_id)
        self._busy.add(session_id)
        parts: list[str] = []
        completed = False
        captured: str | None = None
        try:
            profile = await asyncio.to_thread(load_profile, self.profile_path)
            prior = await asyncio.to_thread(self._turns, session_id)
            sdk_session_id = await asyncio.to_thread(self._sdk_session_id, session_id)
            async for item in self.agent.reply(
                session_id=session_id,
                profile=profile,
                learner_message=text,
                prior_turns=prior,
                sdk_session_id=sdk_session_id,
            ):
                if isinstance(item, ReplyResult):
                    captured = item.sdk_session_id
                    continue
                parts.append(item)
                yield item
            completed = True
        finally:
            self._busy.discard(session_id)
            if completed:
                await asyncio.to_thread(self._save_turn, session_id, text, "".join(parts))
                if captured:
                    await asyncio.to_thread(
                        self._save_sdk_session_id, session_id, captured
                    )

    def _payload(self, session_id: str) -> dict[str, object]:
        row = self._require(session_id)
        turns = self._turns(session_id)
        return {
            "id": session_id,
            "ended": row["ended_at"] is not None,
            "turns": [
                {"learner_message": turn.learner_message, "reply": turn.reply}
                for turn in turns
            ],
        }

    def _turns(self, session_id: str) -> tuple[Turn, ...]:
        def read(conn: sqlite3.Connection) -> tuple[Turn, ...]:
            rows = conn.execute(
                """
                SELECT learner_message, reply
                FROM turns
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            return tuple(
                Turn(learner_message=row["learner_message"], reply=row["reply"])
                for row in rows
            )

        return self._with_db(read)

    def _sdk_session_id(self, session_id: str) -> str | None:
        def read(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                "SELECT sdk_session_id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return row["sdk_session_id"]

        return self._with_db(read)

    def _save_turn(self, session_id: str, learner_message: str, reply: str) -> None:
        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO turns (id, session_id, learner_message, reply, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), session_id, learner_message, reply, _now()),
            )

        self._with_db(write)

    def _save_sdk_session_id(self, session_id: str, sdk_session_id: str) -> None:
        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET sdk_session_id = ? WHERE id = ?",
                (sdk_session_id, session_id),
            )

        self._with_db(write)

    def _end_open(self, except_id: str | None) -> tuple[str, ...]:
        def write(conn: sqlite3.Connection) -> tuple[str, ...]:
            if except_id is None:
                rows = conn.execute(
                    "SELECT id FROM sessions WHERE ended_at IS NULL"
                ).fetchall()
                conn.execute(
                    "UPDATE sessions SET ended_at = ? WHERE ended_at IS NULL",
                    (_now(),),
                )
            else:
                rows = conn.execute(
                    "SELECT id FROM sessions WHERE ended_at IS NULL AND id != ?",
                    (except_id,),
                ).fetchall()
                conn.execute(
                    "UPDATE sessions SET ended_at = ? WHERE ended_at IS NULL AND id != ?",
                    (_now(), except_id),
                )
            return tuple(row["id"] for row in rows)

        return self._with_db(write)

    def _require(self, session_id: str) -> dict[str, str | None]:
        def read(conn: sqlite3.Connection) -> dict[str, str | None] | None:
            row = conn.execute(
                "SELECT id, ended_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            return {"id": row["id"], "ended_at": row["ended_at"]}

        row = self._with_db(read)
        if row is None:
            raise MissingSession()
        return row

    def _init_db(self) -> None:
        def write(conn: sqlite3.Connection) -> None:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    ended_at TEXT,
                    sdk_session_id TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    learner_message TEXT NOT NULL,
                    reply TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Startup create, so a database from before this index still gets it.
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS turns_session_id_created_at
                ON turns(session_id, created_at)
                """
            )

        self._with_db(write)

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _open_db(self) -> None:
        # One connection for every helper. The lock is the only access.
        # check_same_thread is off because async routes run helpers on a worker.
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL").fetchone()
        conn.execute("PRAGMA foreign_keys = ON")
        self._conn = conn

    def _with_db(self, fn):
        with self._lock:
            conn = self._conn
            if conn is None:
                raise RuntimeError("The chat database is closed.")
            try:
                result = fn(conn)
                conn.commit()
                return result
            except BaseException:
                conn.rollback()
                raise
