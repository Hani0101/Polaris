"""Sessions made of turns. The profile is read before each reply.

The teaching agent does not write the profile. The session-end pass does.
"""

import asyncio
import functools
import json
import pickle
import re
import shutil
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import delete_session

from polaris.agent import ReplyAgent, ReplyResult
from polaris.animation import (
    FAILED as JOB_FAILED,
    FAILURE_NOTICE,
    READY as JOB_READY,
    RUNNING as JOB_RUNNING,
    WRITING as JOB_WRITING,
    AnimationProduceResult,
    AnimationWrite,
    MissingJob,
    MissingPlayback,
    PlaybackFile,
    find_playback,
    job_payload,
    load_animation,
    produce as produce_animation,
    waiting_notice_chunk,
)
from polaris.animation import StoredAnimation as Animation
from polaris.animation_router import AnimationRouter, save_route
from polaris.animation_writer import AnimationWriter, new_cli_loop
from polaris.manim_job import (
    ManimDraftData,
    manifest_animation,
    produce_manim,
)
from polaris.login import ApiKeyPresent
from polaris.board_picture import BoardPicture, picture_errors
from polaris.models import AnimationStep, Fact, Pointing, Profile, Turn
from polaris.profile import (
    ProfilePass,
    active_facts,
    apply_changes,
    create_profile_tables,
    finish_pass,
    import_profile_json,
    start_pass,
)
from polaris.quiz import (
    MissingQuiz,
    check_answer,
    normalize_spec,
    public_payload,
)
from polaris.extend import ExtensionCheck, apply_extension
from polaris.flashcards import (
    MissingDeck,
    SourceResource,
    normalize_deck,
    public_payload as deck_payload,
    rate as rate_card,
)
from polaris.resources import ResourceStore, create_resource_tables
from polaris.session_title import TitleWriter, clean_title
from polaris.sign_in import SignIn
from polaris.whiteboard import (
    MissingWhiteboard,
    Whiteboard,
    WhiteboardUnreadable,
    apply_marks,
    blank_whiteboard,
    check_drawing,
    check_learner_drawing,
    pointed_element_errors,
    simpler_count_errors,
)


MAX_NAME_LENGTH = 80


class MissingSession(Exception):
    def __init__(self) -> None:
        super().__init__("No session with that id.")


class NameTooLong(Exception):
    def __init__(self) -> None:
        super().__init__(f"A session name can be at most {MAX_NAME_LENGTH} characters.")


class BlankMessage(Exception):
    def __init__(self) -> None:
        super().__init__("A turn needs a typed message.")


class SessionEnded(Exception):
    def __init__(self) -> None:
        super().__init__("That session has ended. Open it to continue.")


class ReplyInProgress(Exception):
    def __init__(self) -> None:
        super().__init__("A reply is still being produced.")


class InvalidDrawing(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


class InvalidAnimationStep(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidPointing(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


class InvalidPicture(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


class DuplicateWhiteboard(Exception):
    def __init__(self) -> None:
        super().__init__(
            "A whiteboard with that id is already in this session. Use a new id."
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_target_id(action: dict[str, Any]) -> str:
    for key in ("whiteboard_id", "id"):
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _dump_pointing(pointing: Pointing | None) -> str | None:
    if pointing is None:
        return None
    return json.dumps(
        {
            "whiteboard_id": pointing.whiteboard_id,
            "element_ids": list(pointing.element_ids),
        }
    )


def _load_pointing(raw: str | None) -> Pointing | None:
    if not raw:
        return None
    data = json.loads(raw)
    return Pointing(
        whiteboard_id=str(data["whiteboard_id"]),
        element_ids=tuple(str(element_id) for element_id in data["element_ids"]),
    )


def _dump_animation_step(step: AnimationStep | None) -> str | None:
    if step is None:
        return None
    return json.dumps({"job_id": step.job_id, "step_id": step.step_id})


def _load_animation_step(raw: str | None) -> AnimationStep | None:
    if not raw:
        return None
    data = json.loads(raw)
    return AnimationStep(job_id=str(data["job_id"]), step_id=str(data["step_id"]))


def _turn_payload(turn: Turn) -> dict[str, object]:
    payload: dict[str, object] = {
        "learner_message": turn.learner_message,
        "reply": turn.reply,
        "artifacts": list(turn.artifacts),
    }
    if turn.pointing is not None:
        payload["pointing"] = {
            "whiteboard_id": turn.pointing.whiteboard_id,
            "element_ids": list(turn.pointing.element_ids),
        }
    if turn.animation_step is not None:
        payload["animation_step"] = {
            "job_id": turn.animation_step.job_id,
            "step_id": turn.animation_step.step_id,
        }
    return payload


def quizzes_for_reply(turns: tuple[Turn, ...]) -> list[dict[str, object]]:
    """Learner-visible quizzes of earlier turns, so the next reply sees each score."""

    return [
        artifact
        for turn in turns
        for artifact in turn.artifacts
        if artifact.get("kind") == "quiz"
    ]


def decks_for_reply(turns: tuple[Turn, ...]) -> list[dict[str, object]]:
    """Decks of earlier turns with their ratings, so the next reply reads them (FC-15)."""

    return [
        artifact
        for turn in turns
        for artifact in turn.artifacts
        if artifact.get("kind") == "deck"
    ]


def _resource_names(conn: sqlite3.Connection, session_id: str) -> dict[str, str]:
    """A session's resources now, so a deck names a renamed one and marks a removed one (FC-18)."""

    return {
        row["id"]: row["name"]
        for row in conn.execute(
            "SELECT id, name FROM resources WHERE session_id = ?", (session_id,)
        ).fetchall()
    }


@functools.lru_cache(maxsize=128)
def _checked_board(raw: str) -> bytes | None:
    """The drawing check of a stored board's JSON, or None when it fails.

    The check re-plots graphs and re-parses LaTeX, and gives the same answer for
    the same text, so a reply that reads every board pays for it once. The board
    is kept pickled: bytes cannot be changed, and each read gets its own copy.
    """

    checked = check_drawing(json.loads(raw))
    if checked.whiteboard is None:
        return None
    return pickle.dumps(checked.whiteboard, pickle.HIGHEST_PROTOCOL)


def _stored_board(raw: str) -> Whiteboard | None:
    pickled = _checked_board(raw)
    return None if pickled is None else pickle.loads(pickled)


# Files of a Manim job the browser may read. The scene code is not one.
_MANIM_ASSETS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"manim\.json"), "application/json"),
    (re.compile(r"captions\.vtt"), "text/vtt; charset=utf-8"),
    (re.compile(r"steps/step-\d{2}\.mp4"), "video/mp4"),
    (re.compile(r"posters/step-\d{2}\.png"), "image/png"),
)


class Chat:
    def __init__(
        self,
        data_dir: Path,
        agent: ReplyAgent,
        profile_pass: ProfilePass | None = None,
        animation_writer: AnimationWriter | None = None,
        title_writer: TitleWriter | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.agent = agent
        self._profile_pass = profile_pass
        self._animation_writer = animation_writer
        self._title_writer = title_writer
        self._title_tasks: set[asyncio.Task[None]] = set()
        self._discarded: list[str] = []
        self.db_path = data_dir / "polaris.db"
        self.profile_path = data_dir / "profile.json"
        self._lock = threading.Lock()
        self._busy: set[str] = set()
        # Sessions being deleted (CH-14): a reply running in one stops and saves nothing.
        self._deleting: set[str] = set()
        # session id -> the learner's message of the turn now running, so an
        # animation job started in that turn can route on what was asked.
        self._turn_messages: dict[str, str] = {}
        self._pending: dict[str, list[dict[str, object]]] = {}
        self._mark_rollbacks: dict[str, list[tuple[str, str]]] = {}
        # session id -> (whiteboard id, step id) the agent added this turn. A
        # failed turn removes only that step, so learner saves made during the
        # turn are kept.
        self._extension_rollbacks: dict[str, list[tuple[str, str]]] = {}
        # Held while a board is read, changed, and written, so a learner save
        # and an agent step never overwrite each other (WB-21).
        self._board_lock = threading.Lock()
        self._animation_notices: dict[str, list[str]] = {}
        # job id -> worker writing that animation off the turn (AN-01).
        self._animation_threads: dict[str, threading.Thread] = {}
        # Session-end work runs after the request that ended the session: the
        # agent closes, then the profile pass runs, one session at a time
        # (CH-05, PR-05). A reply, a profile read, and a delete wait for it.
        self._ends: dict[str, threading.Event] = {}
        self._last_end: threading.Event | None = None
        self._end_tasks: set[asyncio.Task[None]] = set()
        self._warm_tasks: set[asyncio.Task[None]] = set()
        # Set when a pass after the response sees an API key. The app then stops.
        self.api_key_seen = False
        self._conn: sqlite3.Connection | None = None
        self._open_db()
        self.resources = ResourceStore(data_dir, self._with_db, _now)
        self.sign_in = SignIn(data_dir, self._with_db)
        self._init_db()
        self._fail_interrupted_jobs()
        binder = getattr(agent, "bind_store", None)
        if callable(binder):
            binder(
                self.create_quiz,
                self.create_whiteboard,
                mark_whiteboard=self.mark_whiteboard,
                preview_marks=self.preview_marks,
                extend_whiteboard=self.extend_whiteboard,
                preview_extension=self.preview_extension,
                start_animation_job=self.start_animation_job,
                read_resource=self.read_resource,
                create_deck=self.create_deck,
            )

    def list_sessions(self) -> list[dict[str, object]]:
        def read(conn: sqlite3.Connection) -> list[dict[str, object]]:
            rows = conn.execute(
                """
                SELECT s.id, s.ended_at, s.name, s.generated_title,
                    COALESCE(
                        (
                            SELECT t.learner_message
                            FROM turns t
                            WHERE t.session_id = s.id
                            ORDER BY t.created_at ASC, t.id ASC
                            LIMIT 1
                        ),
                        s.first_message
                    ) AS preview
                FROM sessions s
                WHERE preview IS NOT NULL
                ORDER BY s.created_at DESC
                """
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "ended": row["ended_at"] is not None,
                    "name": row["name"] or "",
                    "title": row["generated_title"] or "",
                    "preview": row["preview"] or "",
                }
                for row in rows
            ]

        return self._with_db(read)

    def start(self) -> tuple[dict[str, object], tuple[str, ...]]:
        self._discard_drafts(except_id=None)
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
        self._discard_drafts(except_id=session_id)
        ended = self._end_open(except_id=session_id)

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET ended_at = NULL WHERE id = ?",
                (session_id,),
            )

        self._with_db(write)
        return self._payload(session_id), ended

    def end_in_background(self, session_ids: Iterable[str]) -> None:
        """Close the agent and run the profile pass for sessions that just ended.

        The work runs on the calling event loop after the response, so starting,
        switching, or leaving a session does not wait for a model call (CH-05,
        PR-05). Passes run one at a time, in the order the sessions ended.
        """

        loop = asyncio.get_running_loop()
        for session_id in session_ids:
            done = threading.Event()
            with self._lock:
                previous = self._last_end
                self._last_end = done
                self._ends[session_id] = done
            task = loop.create_task(self._end(session_id, previous, done))
            self._end_tasks.add(task)
            task.add_done_callback(self._end_tasks.discard)

    async def _end(
        self,
        session_id: str,
        previous: threading.Event | None,
        done: threading.Event,
    ) -> None:
        try:
            if previous is not None:
                await asyncio.to_thread(previous.wait)
            await self.agent.close_session(session_id)
            await self.run_profile_pass(session_id)
        except ApiKeyPresent:
            self.api_key_seen = True
        except Exception:
            # run_profile_pass records a pass that failed. This is a close that
            # failed, or the database closing while Polaris stops.
            pass
        finally:
            with self._lock:
                if self._ends.get(session_id) is done:
                    del self._ends[session_id]
                if self._last_end is done:
                    self._last_end = None
            done.set()

    def wait_for_session_ends(self, session_id: str | None = None) -> bool:
        """Block until session-end work has finished: one session's, or all of it.

        Returns whether there was any to wait for. Never call this on the event
        loop that runs the work.
        """

        with self._lock:
            if session_id is None:
                pending = list(self._ends.values())
            else:
                found = self._ends.get(session_id)
                pending = [] if found is None else [found]
        for done in pending:
            done.wait()
        return bool(pending)

    def warm_in_background(self, session_id: str) -> None:
        """Start the agent's client for an open session the learner is typing in.

        Only a speed-up: the first reply then skips the CLI start. It does
        nothing for an ended session, and it closes a client whose session
        ended while it connected.
        """

        if not callable(getattr(self.agent, "warm", None)):
            return
        task = asyncio.get_running_loop().create_task(self._warm(session_id))
        self._warm_tasks.add(task)
        task.add_done_callback(self._warm_tasks.discard)

    async def _warm(self, session_id: str) -> None:
        def is_open() -> bool:
            try:
                return self._require(session_id)["ended_at"] is None
            except MissingSession:
                return False

        def has_turns(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                "SELECT 1 FROM turns WHERE session_id = ? LIMIT 1", (session_id,)
            ).fetchone()
            return row is not None

        try:
            if not await asyncio.to_thread(is_open):
                return
            # An earlier ending of this session closes its old client first (CH-05).
            await asyncio.to_thread(self.wait_for_session_ends, session_id)
            sdk_session_id = await asyncio.to_thread(self._sdk_session_id, session_id)
            turns = await asyncio.to_thread(self._with_db, has_turns)
            await self.agent.warm(session_id, sdk_session_id, turns)  # type: ignore[attr-defined]
            if not await asyncio.to_thread(is_open):
                await self.agent.close_session(session_id)
        except Exception:
            # The reply connects on its own. This is only a speed-up.
            pass

    async def run_profile_pass(self, session_id: str) -> None:
        """Read the ended session and store fact changes. Does not teach.

        Every run is recorded. A failed run keeps its error, so it is not lost
        silently; the error is a type name, never learner text.
        """

        if self._profile_pass is None:
            return
        turns = await asyncio.to_thread(self._turns, session_id)
        if not turns:
            return
        facts = await asyncio.to_thread(self._with_db, self._read_facts)
        run_id = await asyncio.to_thread(
            self._with_db, lambda conn: start_pass(conn, session_id, "end", _now())
        )
        last_turn_id = turns[-1].id

        def failed(error: str) -> None:
            self._with_db(
                lambda conn: finish_pass(
                    conn,
                    run_id,
                    status="failed",
                    now=_now(),
                    error=error,
                    last_turn_id=last_turn_id,
                )
            )

        try:
            changes = await self._profile_pass.run(turns=turns, facts=facts)
        except ApiKeyPresent:
            await asyncio.to_thread(failed, "ApiKeyPresent")
            raise
        except Exception as exc:
            await asyncio.to_thread(failed, type(exc).__name__)
            return
        turn_ids = {turn.id for turn in turns if turn.id is not None}

        def store(conn: sqlite3.Connection) -> None:
            now = _now()
            applied = apply_changes(
                conn, changes, session_id=session_id, turn_ids=turn_ids, now=now
            )
            finish_pass(
                conn,
                run_id,
                status="stored" if applied.stored else "no_change",
                now=now,
                last_turn_id=last_turn_id,
                applied=applied,
            )

        await asyncio.to_thread(self._with_db, store)

    def read_profile(self) -> Profile:
        """The profile as the teaching agent reads it (PR-01)."""

        return Profile(tuple(fact.text for fact in self._with_db(self._read_facts)))

    def _read_facts(self, conn: sqlite3.Connection) -> tuple[Fact, ...]:
        import_profile_json(conn, self.profile_path, _now())
        return active_facts(conn)

    def leave(self, session_id: str) -> bool:
        """Mark the session ended. Return whether it was open and needs the agent closed."""

        row = self._require(session_id)
        if row["ended_at"] is not None:
            return False
        if self._discard_drafts(only_id=session_id):
            return False

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (_now(), session_id),
            )

        self._with_db(write)
        return True

    def rename(self, session_id: str, name: str) -> dict[str, object]:
        """Set the learner's label for a session. A blank name removes it (CH-07)."""

        self._require(session_id)
        text = name.strip()
        if len(text) > MAX_NAME_LENGTH:
            raise NameTooLong()

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET name = ? WHERE id = ?",
                (text or None, session_id),
            )

        self._with_db(write)
        return {"id": session_id, "name": text}

    async def delete_session(self, session_id: str) -> dict[str, object]:
        """Delete a session and everything made in it (CH-11 to CH-16).

        Stops a reply in progress, ends the session if it is open and waits for
        its profile pass, then removes it. The profile keeps its facts. Returns
        whether the pass kept the facts from this session.
        """

        row = await asyncio.to_thread(self._require, session_id)
        self._deleting.add(session_id)
        try:
            await self.agent.close_session(session_id)
            for _ in range(100):
                if session_id not in self._busy:
                    break
                await asyncio.sleep(0.1)
            # A pass from an earlier ending of this session finishes first.
            ended_earlier = await asyncio.to_thread(self.wait_for_session_ends, session_id)
            facts_saved = True
            if row["ended_at"] is None:
                await asyncio.to_thread(self.leave, session_id)
                await self.run_profile_pass(session_id)
                facts_saved = await asyncio.to_thread(self._last_pass_kept, session_id)
            elif ended_earlier:
                facts_saved = await asyncio.to_thread(self._last_pass_kept, session_id)
            sdk_session_id = await asyncio.to_thread(self._sdk_session_id, session_id)
            job_ids = await asyncio.to_thread(self._delete_rows, session_id)
            for job_id in job_ids:
                shutil.rmtree(self.data_dir / "animation" / job_id, ignore_errors=True)
            self.resources.delete_session_files(session_id)
            if sdk_session_id:
                try:
                    delete_session(sdk_session_id)
                except (FileNotFoundError, ValueError):
                    pass
            return {"id": session_id, "facts_saved": facts_saved}
        finally:
            self._deleting.discard(session_id)

    def _last_pass_kept(self, session_id: str) -> bool:
        def read(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                """
                SELECT status FROM profile_passes
                WHERE session_id = ?
                ORDER BY started_at DESC, rowid DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            return row is None or row["status"] != "failed"

        return self._with_db(read)

    def _delete_rows(self, session_id: str) -> list[str]:
        """Remove the session's rows. A fact stays, without evidence from here (CH-12)."""

        def write(conn: sqlite3.Connection) -> list[str]:
            job_ids = [
                row["id"]
                for row in conn.execute(
                    """
                    SELECT j.id FROM animation_jobs j
                    JOIN artifacts a ON a.id = j.id
                    WHERE a.session_id = ?
                    """,
                    (session_id,),
                ).fetchall()
            ]
            artifacts = "SELECT id FROM artifacts WHERE session_id = ?"
            conn.execute("DELETE FROM fact_evidence WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM profile_passes WHERE session_id = ?", (session_id,))
            for table in ("quizzes", "decks", "whiteboards", "animation_jobs"):
                conn.execute(f"DELETE FROM {table} WHERE id IN ({artifacts})", (session_id,))
            conn.execute("DELETE FROM artifacts WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            self.resources.delete_session(session_id, conn)
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return job_ids

        job_ids = self._with_db(write)
        with self._lock:
            self._pending.pop(session_id, None)
            self._mark_rollbacks.pop(session_id, None)
            self._extension_rollbacks.pop(session_id, None)
            self._animation_notices.pop(session_id, None)
        return job_ids

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

    def resolve_pointing(
        self, session_id: str, whiteboard_id: str, element_ids: list[str]
    ) -> Pointing:
        """Accept element ids only when they are on that session's whiteboard."""

        whiteboard = self._stored_whiteboard(session_id, whiteboard_id.strip())
        cleaned = [element_id.strip() for element_id in element_ids]
        errors = pointed_element_errors(whiteboard, cleaned)
        if errors:
            raise InvalidPointing(errors)
        return Pointing(whiteboard_id=whiteboard.id, element_ids=tuple(cleaned))

    def resolve_picture(
        self, session_id: str, whiteboard_id: str, media_type: str, data: str
    ) -> BoardPicture:
        """Accept a picture only of a whiteboard in this session, as a small PNG."""

        whiteboard = self._stored_whiteboard(session_id, whiteboard_id.strip())
        errors = picture_errors(media_type, data)
        if errors:
            raise InvalidPicture(errors)
        return BoardPicture(whiteboard_id=whiteboard.id, media_type=media_type, data=data)

    def resolve_animation_step(
        self, session_id: str, job_id: str, step_id: str
    ) -> AnimationStep:
        """Accept a step only when it is on a ready animation of that session (AN-17)."""

        animation = self.animation_for_reply(session_id, job_id.strip())
        if animation is None:
            raise InvalidAnimationStep("No ready animation with that id in this session.")
        wanted = step_id.strip()
        if not any(step.id == wanted for step in animation.steps):
            raise InvalidAnimationStep("That animation has no step with that id.")
        return AnimationStep(job_id=animation.id, step_id=wanted)

    def resolve_simplify(self, session_id: str, whiteboard_id: str) -> Whiteboard:
        """Load the whiteboard a simpler redraw must stay smaller than."""

        return self._stored_whiteboard(session_id, whiteboard_id.strip())

    def resolve_pinned(self, session_id: str, whiteboard_id: str) -> Whiteboard:
        """The board pinned above the conversation. The turn is about it (WB-19)."""

        return self._stored_whiteboard(session_id, whiteboard_id.strip())

    async def stream_reply(
        self,
        session_id: str,
        message: str,
        pointing: Pointing | None = None,
        simplify: Whiteboard | None = None,
        picture: BoardPicture | None = None,
        animation_step: AnimationStep | None = None,
        pinned: Whiteboard | None = None,
        web: bool = False,
    ) -> AsyncIterator[str | dict[str, object]]:
        text = await asyncio.to_thread(self.validate_turn, session_id, message)
        self.raise_if_busy(session_id)
        self._busy.add(session_id)
        self._turn_messages[session_id] = text
        parts: list[str] = []
        created: list[dict[str, object]] = []
        completed = False
        captured: str | None = None

        def drain() -> list[dict[str, object]]:
            taken = self._take_pending(session_id)
            created.extend(taken)
            return taken

        try:
            if await asyncio.to_thread(self._claim_first_message, session_id, text):
                self._start_title(session_id, text)
            for notice in self.take_animation_notices(session_id):
                parts.append(notice)
                yield notice
            # A session that just ended may still be in its pass, and its agent
            # may still be closing. Its facts are read for this reply (PR-01).
            await asyncio.to_thread(self.wait_for_session_ends)
            profile = await asyncio.to_thread(self.read_profile)
            prior = await asyncio.to_thread(self._turns, session_id)
            sdk_session_id = await asyncio.to_thread(self._sdk_session_id, session_id)
            whiteboards = await asyncio.to_thread(self.whiteboards_for_reply, session_id)
            # The picture is for this turn only and is not stored.
            extra: dict[str, Any] = {"picture": picture} if picture is not None else {}
            if pinned is not None:
                extra["pinned"] = pinned
            # Only a web-mode reply gets the web tools (CH-23).
            if web:
                extra["web"] = True
            animations =await asyncio.to_thread(self.animations_for_reply, session_id)
            # The agent sees the resource list as it stands now (RS-17).
            resource_lines = await asyncio.to_thread(
                self.resources.prompt_lines, session_id
            )
            if resource_lines:
                extra["resources"] = tuple(resource_lines)
            async for item in self.agent.reply(
                session_id=session_id,
                profile=profile,
                learner_message=text,
                prior_turns=prior,
                sdk_session_id=sdk_session_id,
                whiteboards=whiteboards,
                pointing=pointing,
                simplify=simplify,
                quizzes=quizzes_for_reply(prior),
                decks=decks_for_reply(prior),
                **extra,
                animations=animations,
                animation_step=animation_step,
            ):
                if session_id in self._deleting:
                    return
                if isinstance(item, ReplyResult):
                    captured = item.sdk_session_id
                    continue
                parts.append(item)
                yield item
                for artifact in drain():
                    yield artifact
            for artifact in drain():
                yield artifact
            notice = waiting_notice_chunk("".join(parts), created)
            if notice:
                parts.append(notice)
                yield notice
            completed = True
        finally:
            self._busy.discard(session_id)
            self._turn_messages.pop(session_id, None)
            if completed:
                await asyncio.to_thread(
                    self._save_turn,
                    session_id,
                    text,
                    "".join(parts),
                    [str(artifact["id"]) for artifact in created],
                    pointing,
                    animation_step,
                )
                if captured:
                    await asyncio.to_thread(
                        self._save_sdk_session_id, session_id, captured
                    )
            else:
                await asyncio.to_thread(self._discard_unattached, session_id)

    def _claim_first_message(self, session_id: str, text: str) -> bool:
        """List the session by its first message (CH-20). True only the first time:
        a session with a turn or a stored first message is not titled again."""

        def write(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """
                UPDATE sessions SET first_message = ?
                WHERE id = ? AND first_message IS NULL
                AND NOT EXISTS (SELECT 1 FROM turns WHERE session_id = ?)
                """,
                (text, session_id, session_id),
            )
            return cursor.rowcount > 0

        return self._with_db(write)

    def _start_title(self, session_id: str, text: str) -> None:
        """Write the generated title off the reply (CH-20, CH-21)."""

        if self._title_writer is None:
            return
        task = asyncio.get_running_loop().create_task(self._write_title(session_id, text))
        self._title_tasks.add(task)
        task.add_done_callback(self._title_tasks.discard)

    async def _write_title(self, session_id: str, text: str) -> None:
        try:
            title = clean_title(await self._title_writer.write(text))
        except Exception:
            return  # A title is cosmetic: no retry, no error (CH-21).
        if not title or session_id in self._deleting:
            return

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET generated_title = ? WHERE id = ? AND generated_title IS NULL",
                (title, session_id),
            )

        await asyncio.to_thread(self._with_db, write)

    def _require_open_for_resource(self, session_id: str) -> None:
        """A resource for a session being deleted, or gone, is dropped (RS-18, CH-14)."""

        if session_id in self._deleting:
            raise MissingSession()
        self._require(session_id)

    def list_resources(self, session_id: str) -> list[dict[str, object]]:
        self._require(session_id)
        return self.resources.list_all(session_id)

    def add_resource_file(
        self, session_id: str, filename: str, data: bytes
    ) -> dict[str, object]:
        self._require_open_for_resource(session_id)
        return self._guard_late_resource(
            session_id, lambda: self.resources.add_file(session_id, filename, data)
        )

    def add_resource_note(
        self, session_id: str, name: str, text: str
    ) -> dict[str, object]:
        self._require_open_for_resource(session_id)
        return self._guard_late_resource(
            session_id, lambda: self.resources.add_note(session_id, name, text)
        )

    def add_resource_web(self, session_id: str, url: str) -> dict[str, object]:
        """Fetch a public page by its link (RS-22). The fetch runs before the late-file check."""

        self._require_open_for_resource(session_id)
        return self._guard_late_resource(
            session_id, lambda: self.resources.add_web(session_id, url)
        )

    def _guard_late_resource(
        self, session_id: str, add: Callable[[], dict[str, object]]
    ) -> dict[str, object]:
        try:
            added = add()
        except sqlite3.IntegrityError:
            raise MissingSession() from None
        if session_id in self._deleting:
            self.resources.remove(session_id, str(added["id"]))
            raise MissingSession()
        return added

    def get_resource(self, session_id: str, resource_id: str) -> dict[str, object]:
        self._require(session_id)
        return self.resources.get(session_id, resource_id)

    def resource_file(self, session_id: str, resource_id: str):
        self._require(session_id)
        return self.resources.original(session_id, resource_id)

    def rename_resource(
        self, session_id: str, resource_id: str, name: str
    ) -> dict[str, object]:
        self._require(session_id)
        return self.resources.rename(session_id, resource_id, name)

    def edit_resource_note(
        self, session_id: str, resource_id: str, text: str
    ) -> dict[str, object]:
        self._require(session_id)
        return self.resources.edit_note(session_id, resource_id, text)

    def remove_resource(self, session_id: str, resource_id: str) -> None:
        self._require(session_id)
        self.resources.remove(session_id, resource_id)

    def read_resource(
        self,
        session_id: str,
        resource_id: str,
        first: int | None = None,
        last: int | None = None,
    ) -> dict[str, Any]:
        """What the agent's read_resource tool returns (RS-07)."""

        self._require(session_id)
        return self.resources.read_for_agent(session_id, resource_id, first, last)

    def create_quiz(self, session_id: str, spec: dict[str, Any]) -> dict[str, object]:
        self._require(session_id)
        stored = normalize_spec(spec)
        quiz_id = str(uuid.uuid4())
        payload = public_payload(
            quiz_id, session_id, stored, score=None, submitted={}
        )

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO artifacts (id, session_id, turn_id, kind, created_at)
                VALUES (?, ?, NULL, 'quiz', ?)
                """,
                (quiz_id, session_id, _now()),
            )
            conn.execute(
                """
                INSERT INTO quizzes (
                    id, title, questions_json, score_correct, score_total, submitted_json
                )
                VALUES (?, ?, ?, NULL, NULL, NULL)
                """,
                (quiz_id, stored["title"], json.dumps(stored)),
            )

        self._with_db(write)
        with self._lock:
            self._pending.setdefault(session_id, []).append(payload)
        return payload

    def create_deck(self, session_id: str, spec: dict[str, Any]) -> dict[str, object]:
        """Check every card's source, then store the deck whole or not at all (FC-06, FC-12).

        The sources are this session's earlier turns and its resources as they
        stand now (FC-04). Raises InvalidDeck naming each card that fails.
        """

        self._require(session_id)
        resources = [
            SourceResource(id=id_, kind=kind, name=name, pages=pages)
            for id_, kind, name, pages in self.resources.texts(session_id)
        ]

        def count(conn: sqlite3.Connection) -> int:
            return conn.execute(
                "SELECT COUNT(*) FROM turns WHERE session_id = ?", (session_id,)
            ).fetchone()[0]

        stored = normalize_deck(spec, resources=resources, turn_count=self._with_db(count))
        deck_id = str(uuid.uuid4())
        payload = deck_payload(
            deck_id,
            session_id,
            stored,
            {},
            {resource.id: resource.name for resource in resources},
        )

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO artifacts (id, session_id, turn_id, kind, created_at)
                VALUES (?, ?, NULL, 'deck', ?)
                """,
                (deck_id, session_id, _now()),
            )
            conn.execute(
                "INSERT INTO decks (id, title, cards_json, ratings_json) VALUES (?, ?, ?, '{}')",
                (deck_id, stored["title"], json.dumps(stored)),
            )

        self._with_db(write)
        with self._lock:
            self._pending.setdefault(session_id, []).append(payload)
        return payload

    def start_animation_job(self, session_id: str, brief: str) -> dict[str, object]:
        """Store a running job and return its id before any animation exists (AN-01).

        The animation is written and run by a worker, outside the turn, so
        the learner can keep talking in this session or another.
        """

        self._require(session_id)
        brief = brief.strip()
        if not brief:
            raise ValueError("An animation job needs a brief.")
        job_id = str(uuid.uuid4())
        payload = job_payload(job_id, session_id, status=JOB_RUNNING, stage=JOB_WRITING)

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO artifacts (id, session_id, turn_id, kind, created_at)
                VALUES (?, ?, NULL, 'animation', ?)
                """,
                (job_id, session_id, _now()),
            )
            conn.execute(
                """
                INSERT INTO animation_jobs (id, status, stage)
                VALUES (?, ?, ?)
                """,
                (job_id, JOB_RUNNING, JOB_WRITING),
            )

        self._with_db(write)
        with self._lock:
            self._pending.setdefault(session_id, []).append(payload)
        self._launch_animation(
            session_id, job_id, brief, self._turn_messages.get(session_id)
        )
        return payload

    def _launch_animation(
        self,
        session_id: str,
        job_id: str,
        brief: str,
        learner_message: str | None = None,
    ) -> None:
        writer = self._animation_writer
        if writer is None:
            return
        thread = threading.Thread(
            target=self._run_animation_job,
            args=(writer, session_id, job_id, brief, learner_message),
            name=f"polaris-animation-{job_id[:8]}",
            daemon=True,
        )
        with self._lock:
            self._animation_threads[job_id] = thread
        thread.start()

    def _run_animation_job(
        self,
        writer: AnimationWriter,
        session_id: str,
        job_id: str,
        brief: str,
        learner_message: str | None = None,
    ) -> None:
        """Worker: write, check, and fix one animation (AN-05, AN-09, AN-10).

        Runs on its own loop, one that can spawn the Claude CLI. With a
        router, a small evaluation first picks Manim or Lottie (AN-21).
        """

        loop = new_cli_loop()
        if isinstance(writer, AnimationRouter):
            route = loop.run_until_complete(writer.route(brief, learner_message))
            save_route(self.animation_work_dir(job_id), route)
            writer = writer.writer_for(route)
        if getattr(writer, "engine", None) == "manim":
            self._run_manim_job(writer, loop, session_id, job_id, brief)
            return
        last_data: dict[str, Any] | None = None

        def write_animation(errors: list[str] | None) -> dict[str, Any]:
            nonlocal last_data
            last_data = loop.run_until_complete(
                writer.write(
                    brief,
                    failed_data=last_data if errors is not None else None,
                    errors=errors,
                    job_id=job_id,
                )
            )
            return last_data

        try:
            self.produce_animation_job(session_id, job_id, write_animation)
        except MissingJob:
            # The turn that started the job failed and was discarded.
            pass
        except Exception:
            self._fail_animation_job(session_id, job_id)
        finally:
            loop.close()
            with self._lock:
                self._animation_threads.pop(job_id, None)

    def _run_manim_job(
        self,
        writer: Any,
        loop: asyncio.AbstractEventLoop,
        session_id: str,
        job_id: str,
        brief: str,
    ) -> None:
        """Worker for the Manim experiment: draft, render, fix (AN-05, AN-19)."""

        def write_draft(
            failed_code: str | None, errors: list[str] | None
        ) -> ManimDraftData:
            draft = loop.run_until_complete(
                writer.write(
                    brief,
                    failed_code=failed_code,
                    errors=errors,
                    preview_dir=self.animation_work_dir(job_id) / "previews",
                )
            )
            return ManimDraftData(
                title=draft.title, description=draft.description, code=draft.code
            )

        try:
            self.get_animation_job(session_id, job_id)
            result = produce_manim(
                job_id=job_id,
                work_dir=self.animation_work_dir(job_id),
                write_draft=write_draft,
                on_stage=lambda stage: self._set_animation_stage(job_id, stage),
            )
            self._set_animation_status(job_id, result.status)
            if result.session_notice:
                with self._lock:
                    self._animation_notices.setdefault(session_id, []).append(
                        result.session_notice
                    )
        except MissingJob:
            pass
        except Exception:
            self._fail_animation_job(session_id, job_id)
        finally:
            loop.close()
            with self._lock:
                self._animation_threads.pop(job_id, None)

    def wait_for_animation_jobs(self, timeout: float | None = None) -> None:
        """Block until every animation worker has finished."""

        with self._lock:
            threads = list(self._animation_threads.values())
        for thread in threads:
            thread.join(timeout)

    def _fail_animation_job(self, session_id: str, job_id: str) -> None:
        try:
            self._set_animation_status(job_id, JOB_FAILED)
        except RuntimeError:
            # The chat database closed while the worker ran.
            return
        with self._lock:
            self._animation_notices.setdefault(session_id, []).append(FAILURE_NOTICE)

    def _fail_interrupted_jobs(self) -> None:
        """A job still running at startup lost its worker when Polaris stopped (AN-09)."""

        def write(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """
                SELECT DISTINCT a.session_id
                FROM animation_jobs j
                JOIN artifacts a ON a.id = j.id
                WHERE j.status = ?
                """,
                (JOB_RUNNING,),
            ).fetchall()
            conn.execute(
                "UPDATE animation_jobs SET status = ?, stage = NULL WHERE status = ?",
                (JOB_FAILED, JOB_RUNNING),
            )
            return [row["session_id"] for row in rows]

        for session_id in self._with_db(write):
            self._animation_notices.setdefault(session_id, []).append(FAILURE_NOTICE)

    def get_animation_job(self, session_id: str, job_id: str) -> dict[str, object]:
        self._require(session_id)

        def read(conn: sqlite3.Connection) -> sqlite3.Row | None:
            return conn.execute(
                """
                SELECT a.id, a.session_id, j.status, j.stage
                FROM artifacts a
                JOIN animation_jobs j ON j.id = a.id
                WHERE a.id = ? AND a.session_id = ? AND a.kind = 'animation'
                """,
                (job_id, session_id),
            ).fetchone()

        row = self._with_db(read)
        if row is None:
            raise MissingJob()
        return job_payload(
            row["id"], row["session_id"], status=row["status"], stage=row["stage"]
        )

    def get_animation_media(self, session_id: str, job_id: str) -> PlaybackFile:
        """Playback file for a ready job (AN-06). Never includes agent code."""

        job = self.get_animation_job(session_id, job_id)
        if job["status"] != JOB_READY:
            raise MissingPlayback()
        found = find_playback(self.animation_work_dir(job_id))
        if found is None:
            raise MissingPlayback()
        return found

    def get_animation_asset(self, session_id: str, job_id: str, name: str) -> PlaybackFile:
        """A step clip, poster, captions, or manifest of a ready Manim job."""

        job = self.get_animation_job(session_id, job_id)
        if job["status"] != JOB_READY:
            raise MissingPlayback()
        for pattern, media_type in _MANIM_ASSETS:
            if pattern.fullmatch(name):
                path = self.animation_work_dir(job_id) / name
                if path.is_file():
                    return PlaybackFile(path=path.resolve(), media_type=media_type)
        raise MissingPlayback()

    def animation_for_reply(self, session_id: str, job_id: str) -> Animation | None:
        """The stored animation of a ready job in this session, if it is in the format."""

        try:
            job = self.get_animation_job(session_id, job_id)
        except MissingJob:
            return None
        if job["status"] != JOB_READY:
            return None
        work_dir = self.animation_work_dir(job_id)
        return load_animation(work_dir) or manifest_animation(work_dir)

    def animations_for_reply(self, session_id: str) -> list[Animation]:
        """Ready animations a later turn can see, oldest first (AN-16)."""

        def read(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """
                SELECT a.id
                FROM artifacts a
                JOIN animation_jobs j ON j.id = a.id
                WHERE a.session_id = ? AND a.kind = 'animation' AND j.status = ?
                ORDER BY a.created_at ASC, a.id ASC
                """,
                (session_id, JOB_READY),
            ).fetchall()
            return [row["id"] for row in rows]

        animations: list[Animation] = []
        for job_id in self._with_db(read):
            work_dir = self.data_dir / "animation" / job_id
            found = load_animation(work_dir) or manifest_animation(work_dir)
            if found is not None:
                animations.append(found)
        return animations

    def animation_work_dir(self, job_id: str) -> Path:
        """Directory where this job's stored animation is written."""

        path = self.data_dir / "animation" / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def produce_animation_job(
        self,
        session_id: str,
        job_id: str,
        write_animation: AnimationWrite,
    ) -> AnimationProduceResult:
        """Write, check, and fix a started job (AN-05, AN-09, AN-10, AN-19).

        Only checked data is stored. Each stage is kept on the job so the
        learner can see it while the job runs.
        """

        self.get_animation_job(session_id, job_id)
        result = produce_animation(
            job_id=job_id,
            work_dir=self.animation_work_dir(job_id),
            write_animation=write_animation,
            on_stage=lambda stage: self._set_animation_stage(job_id, stage),
        )
        self._set_animation_status(job_id, result.status)
        if result.session_notice:
            with self._lock:
                self._animation_notices.setdefault(session_id, []).append(
                    result.session_notice
                )
        return result

    def take_animation_notices(self, session_id: str) -> list[str]:
        """Drain failure notices for a session (AN-09)."""

        with self._lock:
            return list(self._animation_notices.pop(session_id, []))

    def _set_animation_status(self, job_id: str, status: str) -> None:
        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                UPDATE animation_jobs SET status = ?, stage = NULL WHERE id = ?
                """,
                (status, job_id),
            )

        self._with_db(write)

    def _set_animation_stage(self, job_id: str, stage: str) -> None:
        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE animation_jobs SET stage = ? WHERE id = ? AND status = ?",
                (stage, job_id, JOB_RUNNING),
            )

        self._with_db(write)

    def create_whiteboard(
        self, session_id: str, drawing: dict[str, Any]
    ) -> dict[str, object]:
        self._require(session_id)
        incoming = dict(drawing)
        incoming["session_id"] = session_id
        checked = check_drawing(incoming)
        if checked.whiteboard is None:
            raise InvalidDrawing(checked.errors)
        if checked.whiteboard.simplifies:
            errors = self._simpler_errors(session_id, checked.whiteboard)
            if errors:
                raise InvalidDrawing(errors)

        canonical = checked.whiteboard.model_dump(mode="json")
        whiteboard_id = str(canonical["id"])
        payload: dict[str, object] = {**canonical, "kind": "whiteboard"}

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO artifacts (id, session_id, turn_id, kind, created_at)
                VALUES (?, ?, NULL, 'whiteboard', ?)
                """,
                (whiteboard_id, session_id, _now()),
            )
            conn.execute(
                """
                INSERT INTO whiteboards (id, drawing_json)
                VALUES (?, ?)
                """,
                (whiteboard_id, json.dumps(canonical)),
            )

        try:
            self._with_db(write)
        except sqlite3.IntegrityError:
            raise DuplicateWhiteboard() from None
        with self._lock:
            self._pending.setdefault(session_id, []).append(payload)
        return payload

    def list_whiteboards(self, session_id: str) -> list[dict[str, object]]:
        self._require(session_id)
        shown: list[dict[str, object]] = []
        for raw in self._session_drawing_jsons(session_id):
            payload = self._whiteboard_payload(raw)
            if payload is not None:
                shown.append(payload)
        return shown

    def _session_drawing_jsons(self, session_id: str) -> list[str]:
        def read(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """
                SELECT w.drawing_json
                FROM artifacts a
                JOIN whiteboards w ON w.id = a.id
                WHERE a.session_id = ? AND a.kind = 'whiteboard'
                ORDER BY a.created_at ASC, a.id ASC
                """,
                (session_id,),
            ).fetchall()
            return [row["drawing_json"] for row in rows]

        return self._with_db(read)

    def get_whiteboard(self, session_id: str, whiteboard_id: str) -> dict[str, object]:
        self._require(session_id)

        def read(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                """
                SELECT w.drawing_json
                FROM artifacts a
                JOIN whiteboards w ON w.id = a.id
                WHERE a.id = ? AND a.session_id = ? AND a.kind = 'whiteboard'
                """,
                (whiteboard_id, session_id),
            ).fetchone()
            if row is None:
                return None
            return row["drawing_json"]

        raw = self._with_db(read)
        if raw is None:
            raise MissingWhiteboard()
        payload = self._whiteboard_payload(raw)
        if payload is None:
            raise WhiteboardUnreadable()
        return payload

    def create_learner_whiteboard(self, session_id: str) -> dict[str, object]:
        """An empty board the learner made (WB-18). No turn owns it, and it is kept."""

        self._require(session_id)
        whiteboard_id = str(uuid.uuid4())
        canonical = blank_whiteboard(whiteboard_id, session_id).model_dump(mode="json")

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO artifacts (id, session_id, turn_id, kind, created_at, learner_made)
                VALUES (?, ?, NULL, 'whiteboard', ?, 1)
                """,
                (whiteboard_id, session_id, _now()),
            )
            conn.execute(
                "INSERT INTO whiteboards (id, drawing_json) VALUES (?, ?)",
                (whiteboard_id, json.dumps(canonical)),
            )

        self._with_db(write)
        return {**canonical, "kind": "whiteboard"}

    def update_whiteboard(
        self, session_id: str, whiteboard_id: str, drawing: object
    ) -> dict[str, object]:
        """Merge a learner's drawing into the stored board after the drawing check (WB-21)."""

        self._require(session_id)
        incoming: object = drawing
        if isinstance(drawing, dict):
            incoming = {**drawing, "session_id": session_id}
        with self._board_lock:
            stored = self._stored_whiteboard(session_id, whiteboard_id)
            checked = check_learner_drawing(stored, incoming)
            if checked.whiteboard is None:
                raise InvalidDrawing(checked.errors)
            if checked.whiteboard.id != whiteboard_id:
                raise InvalidDrawing(["whiteboard id cannot change"])

            canonical = checked.whiteboard.model_dump(mode="json")

            def write(conn: sqlite3.Connection) -> None:
                conn.execute(
                    "UPDATE whiteboards SET drawing_json = ? WHERE id = ?",
                    (json.dumps(canonical), whiteboard_id),
                )

            self._with_db(write)
        payload = dict(canonical)
        payload["kind"] = "whiteboard"
        return payload

    def _marked(self, session_id: str, action: dict[str, Any]) -> tuple[Whiteboard, str]:
        """The stored whiteboard with the marks applied, and its stored JSON."""

        self._require(session_id)
        whiteboard_id = _mark_target_id(action)
        if not whiteboard_id:
            raise InvalidDrawing(["whiteboard id: missing field"])
        raw = self._drawing_json(session_id, whiteboard_id)
        if raw is None:
            raise MissingWhiteboard()
        stored = _stored_board(raw)
        if stored is None:
            raise WhiteboardUnreadable()
        checked = apply_marks(stored, action)
        if checked.whiteboard is None:
            raise InvalidDrawing(checked.errors)
        return checked.whiteboard, raw

    def preview_marks(self, session_id: str, action: dict[str, Any]) -> Whiteboard:
        """What mark_whiteboard would store. Nothing is written."""

        return self._marked(session_id, action)[0]

    def mark_whiteboard(
        self, session_id: str, action: dict[str, Any]
    ) -> dict[str, object]:
        """Append agent marks onto a stored whiteboard and show the update."""

        with self._board_lock:
            marked, raw = self._marked(session_id, action)
            canonical = marked.model_dump(mode="json")
            whiteboard_id = str(canonical["id"])

            def write(conn: sqlite3.Connection) -> None:
                conn.execute(
                    "UPDATE whiteboards SET drawing_json = ? WHERE id = ?",
                    (json.dumps(canonical), whiteboard_id),
                )

            self._with_db(write)
        payload: dict[str, object] = {**canonical, "kind": "whiteboard"}
        with self._lock:
            self._mark_rollbacks.setdefault(session_id, []).append(
                (whiteboard_id, raw)
            )
            self._pending.setdefault(session_id, []).append(payload)
        return payload

    def _extended(self, session_id: str, action: dict[str, Any]) -> ExtensionCheck:
        """The stored board with the agent's step added, or why it was refused."""

        self._require(session_id)
        whiteboard_id = action.get("whiteboard_id")
        if not isinstance(whiteboard_id, str) or not whiteboard_id.strip():
            raise InvalidDrawing(["whiteboard_id: missing field"])
        stored = self._stored_whiteboard(session_id, whiteboard_id.strip())
        checked = apply_extension(stored, {**action, "whiteboard_id": whiteboard_id.strip()})
        if checked.whiteboard is None:
            raise InvalidDrawing(checked.errors)
        return checked

    def preview_extension(self, session_id: str, action: dict[str, Any]) -> ExtensionCheck:
        """What extend_whiteboard would store, with its layout problems. Nothing is written."""

        return self._extended(session_id, action)

    def extend_whiteboard(
        self, session_id: str, action: dict[str, Any]
    ) -> dict[str, object]:
        """Add the agent's own parts to a stored board as a new step (WB-20)."""

        with self._board_lock:
            checked = self._extended(session_id, action)
            assert checked.whiteboard is not None
            canonical = checked.whiteboard.model_dump(mode="json")
            whiteboard_id = str(canonical["id"])
            step_id = str(canonical["steps"][-1]["id"])

            def write(conn: sqlite3.Connection) -> None:
                conn.execute(
                    "UPDATE whiteboards SET drawing_json = ? WHERE id = ?",
                    (json.dumps(canonical), whiteboard_id),
                )

            self._with_db(write)
        payload: dict[str, object] = {**canonical, "kind": "whiteboard"}
        with self._lock:
            self._extension_rollbacks.setdefault(session_id, []).append(
                (whiteboard_id, step_id)
            )
            self._pending.setdefault(session_id, []).append(payload)
        return payload

    def _remove_added_step(self, session_id: str, whiteboard_id: str, step_id: str) -> None:
        """Take back a step the agent added in a turn that failed. Learner parts stay."""

        with self._board_lock:
            raw = self._drawing_json(session_id, whiteboard_id)
            if raw is None:
                return
            drawing = json.loads(raw)
            steps = drawing.get("steps")
            if not isinstance(steps, list):
                return
            drawing["steps"] = [
                step
                for step in steps
                if not (
                    isinstance(step, dict)
                    and step.get("id") == step_id
                    and step.get("extension")
                )
            ]
            if check_drawing(drawing).whiteboard is None:
                return

            def write(conn: sqlite3.Connection) -> None:
                conn.execute(
                    "UPDATE whiteboards SET drawing_json = ? WHERE id = ?",
                    (json.dumps(drawing), whiteboard_id),
                )

            self._with_db(write)

    def whiteboards_for_reply(self, session_id: str) -> list[Whiteboard]:
        self._require(session_id)
        boards = (_stored_board(raw) for raw in self._session_drawing_jsons(session_id))
        return [board for board in boards if board is not None]

    def _drawing_json(self, session_id: str, whiteboard_id: str) -> str | None:
        def read(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                """
                SELECT w.drawing_json
                FROM artifacts a
                JOIN whiteboards w ON w.id = a.id
                WHERE a.id = ? AND a.session_id = ? AND a.kind = 'whiteboard'
                """,
                (whiteboard_id, session_id),
            ).fetchone()
            if row is None:
                return None
            return row["drawing_json"]

        return self._with_db(read)

    def _simpler_errors(self, session_id: str, whiteboard: Whiteboard) -> list[str]:
        original_id = whiteboard.simplifies
        if not original_id:
            return []
        try:
            original = self._stored_whiteboard(session_id, original_id)
        except MissingWhiteboard:
            return ["No whiteboard with that id."]
        except WhiteboardUnreadable:
            return ["That whiteboard could not be opened."]
        return simpler_count_errors(original, whiteboard)

    def _stored_whiteboard(self, session_id: str, whiteboard_id: str) -> Whiteboard:
        raw = self._drawing_json(session_id, whiteboard_id)
        if raw is None:
            raise MissingWhiteboard()
        whiteboard = _stored_board(raw)
        if whiteboard is None:
            raise WhiteboardUnreadable()
        return whiteboard

    def _whiteboard_payload(self, raw: str) -> dict[str, object] | None:
        if _checked_board(raw) is None:
            return None
        drawing = json.loads(raw)
        if not isinstance(drawing, dict):
            return None
        drawing["kind"] = "whiteboard"
        return drawing

    def get_quiz(self, quiz_id: str) -> dict[str, object]:
        def read(conn: sqlite3.Connection) -> sqlite3.Row | None:
            return conn.execute(
                """
                SELECT a.id, a.session_id, q.questions_json,
                       q.score_correct, q.score_total, q.submitted_json
                FROM artifacts a
                JOIN quizzes q ON q.id = a.id
                WHERE a.id = ? AND a.kind = 'quiz'
                """,
                (quiz_id,),
            ).fetchone()

        row = self._with_db(read)
        if row is None:
            raise MissingQuiz()
        return self._public_from_row(row)

    def answer_quiz(
        self, quiz_id: str, question_id: str, choice_id: str
    ) -> dict[str, object]:
        """Check one pick against the stored key and keep it (QZ-14, QZ-15). The
        score is kept when the last question is checked (QZ-08)."""

        def write(conn: sqlite3.Connection) -> dict[str, object] | None:
            row = conn.execute(
                """
                SELECT a.id, a.session_id, q.questions_json, q.submitted_json
                FROM artifacts a
                JOIN quizzes q ON q.id = a.id
                WHERE a.id = ? AND a.kind = 'quiz'
                """,
                (quiz_id,),
            ).fetchone()
            if row is None:
                return None
            stored = json.loads(row["questions_json"])
            raw = row["submitted_json"]
            before = json.loads(raw) if raw else {}
            submitted, score = check_answer(stored, before, question_id, choice_id)
            conn.execute(
                """
                UPDATE quizzes
                SET score_correct = ?, score_total = ?, submitted_json = ?
                WHERE id = ?
                """,
                (
                    score["earned"] if score else None,
                    score["total"] if score else None,
                    json.dumps(submitted),
                    quiz_id,
                ),
            )
            return public_payload(
                quiz_id,
                row["session_id"],
                stored,
                score=score,
                submitted=submitted,
            )

        payload = self._with_db(write)
        if payload is None:
            raise MissingQuiz()
        return payload

    def _deck_row(self, conn: sqlite3.Connection, deck_id: str) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT a.id, a.session_id, d.cards_json, d.ratings_json
            FROM artifacts a
            JOIN decks d ON d.id = a.id
            WHERE a.id = ? AND a.kind = 'deck'
            """,
            (deck_id,),
        ).fetchone()

    def _deck_from_row(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
        return deck_payload(
            row["id"],
            row["session_id"],
            json.loads(row["cards_json"]),
            json.loads(row["ratings_json"]),
            _resource_names(conn, row["session_id"]),
        )

    def get_deck(self, deck_id: str) -> dict[str, object]:
        def read(conn: sqlite3.Connection) -> dict[str, object] | None:
            row = self._deck_row(conn, deck_id)
            return None if row is None else self._deck_from_row(conn, row)

        payload = self._with_db(read)
        if payload is None:
            raise MissingDeck()
        return payload

    def rate_card(self, deck_id: str, card_id: str, rating: str) -> dict[str, object]:
        """Keep a card's latest rating (FC-14). It stays with the deck (FC-16)."""

        def write(conn: sqlite3.Connection) -> dict[str, object] | None:
            row = self._deck_row(conn, deck_id)
            if row is None:
                return None
            ratings = rate_card(
                json.loads(row["cards_json"]),
                json.loads(row["ratings_json"]),
                card_id,
                rating,
            )
            conn.execute(
                "UPDATE decks SET ratings_json = ? WHERE id = ?",
                (json.dumps(ratings), deck_id),
            )
            return self._deck_from_row(conn, self._deck_row(conn, deck_id))

        payload = self._with_db(write)
        if payload is None:
            raise MissingDeck()
        return payload

    def reset_ratings(self, deck_id: str) -> dict[str, object]:
        """Every card of the deck back to unrated (FC-14)."""

        def write(conn: sqlite3.Connection) -> dict[str, object] | None:
            row = self._deck_row(conn, deck_id)
            if row is None:
                return None
            conn.execute("UPDATE decks SET ratings_json = '{}' WHERE id = ?", (deck_id,))
            return self._deck_from_row(conn, self._deck_row(conn, deck_id))

        payload = self._with_db(write)
        if payload is None:
            raise MissingDeck()
        return payload

    def _payload(self, session_id: str) -> dict[str, object]:
        row = self._require(session_id)
        turns = self._turns(session_id)
        return {
            "id": session_id,
            "ended": row["ended_at"] is not None,
            "turns": [_turn_payload(turn) for turn in turns],
        }

    def _turns(self, session_id: str) -> tuple[Turn, ...]:
        def read(conn: sqlite3.Connection) -> tuple[Turn, ...]:
            rows = conn.execute(
                """
                SELECT id, learner_message, reply, pointing_json, animation_step_json
                FROM turns
                WHERE session_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            artifact_rows = conn.execute(
                """
                SELECT a.turn_id, a.id, a.session_id, a.kind,
                       q.questions_json, q.score_correct, q.score_total,
                       q.submitted_json, w.drawing_json, j.status AS job_status,
                       j.stage AS job_stage, d.cards_json, d.ratings_json
                FROM artifacts a
                LEFT JOIN quizzes q ON q.id = a.id AND a.kind = 'quiz'
                LEFT JOIN decks d ON d.id = a.id AND a.kind = 'deck'
                LEFT JOIN whiteboards w ON w.id = a.id AND a.kind = 'whiteboard'
                LEFT JOIN animation_jobs j ON j.id = a.id AND a.kind = 'animation'
                WHERE a.session_id = ?
                ORDER BY a.created_at ASC, a.id ASC
                """,
                (session_id,),
            ).fetchall()
            names = _resource_names(conn, session_id)
            by_turn: dict[str, list[dict[str, object]]] = {}
            for row in artifact_rows:
                turn_id = row["turn_id"]
                if turn_id is None:
                    continue
                if row["kind"] == "whiteboard":
                    payload = self._whiteboard_payload(row["drawing_json"])
                    if payload is not None:
                        by_turn.setdefault(turn_id, []).append(payload)
                    continue
                if row["kind"] == "quiz":
                    by_turn.setdefault(turn_id, []).append(self._public_from_row(row))
                    continue
                if row["kind"] == "deck" and row["cards_json"] is not None:
                    by_turn.setdefault(turn_id, []).append(
                        deck_payload(
                            row["id"],
                            row["session_id"],
                            json.loads(row["cards_json"]),
                            json.loads(row["ratings_json"]),
                            names,
                        )
                    )
                    continue
                if row["kind"] == "animation" and row["job_status"] is not None:
                    by_turn.setdefault(turn_id, []).append(
                        job_payload(
                            row["id"],
                            row["session_id"],
                            status=row["job_status"],
                            stage=row["job_stage"],
                        )
                    )
            return tuple(
                Turn(
                    learner_message=row["learner_message"],
                    reply=row["reply"],
                    artifacts=tuple(by_turn.get(row["id"], [])),
                    pointing=_load_pointing(row["pointing_json"]),
                    id=row["id"],
                    animation_step=_load_animation_step(row["animation_step_json"]),
                )
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

    def _save_turn(
        self,
        session_id: str,
        learner_message: str,
        reply: str,
        artifact_ids: list[str],
        pointing: Pointing | None = None,
        animation_step: AnimationStep | None = None,
    ) -> None:
        turn_id = str(uuid.uuid4())
        pointing_json = _dump_pointing(pointing)
        animation_step_json = _dump_animation_step(animation_step)

        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO turns (
                    id, session_id, learner_message, reply, created_at, pointing_json,
                    animation_step_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    session_id,
                    learner_message,
                    reply,
                    _now(),
                    pointing_json,
                    animation_step_json,
                ),
            )
            for artifact_id in artifact_ids:
                conn.execute(
                    """
                    UPDATE artifacts SET turn_id = ?
                    WHERE id = ? AND session_id = ? AND turn_id IS NULL
                      AND learner_made = 0
                    """,
                    (turn_id, artifact_id, session_id),
                )

        self._with_db(write)
        with self._lock:
            self._mark_rollbacks.pop(session_id, None)
            self._extension_rollbacks.pop(session_id, None)

    def _take_pending(self, session_id: str) -> list[dict[str, object]]:
        with self._lock:
            return list(self._pending.pop(session_id, []))

    def _discard_unattached(self, session_id: str) -> None:
        with self._lock:
            rollbacks = list(self._mark_rollbacks.pop(session_id, []))
            added = list(self._extension_rollbacks.pop(session_id, []))
        for whiteboard_id, step_id in reversed(added):
            self._remove_added_step(session_id, whiteboard_id, step_id)

        def write(conn: sqlite3.Connection) -> None:
            for whiteboard_id, previous in reversed(rollbacks):
                conn.execute(
                    "UPDATE whiteboards SET drawing_json = ? WHERE id = ?",
                    (previous, whiteboard_id),
                )
            conn.execute(
                """
                DELETE FROM quizzes
                WHERE id IN (
                    SELECT id FROM artifacts
                    WHERE session_id = ? AND turn_id IS NULL AND learner_made = 0
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM decks
                WHERE id IN (
                    SELECT id FROM artifacts
                    WHERE session_id = ? AND turn_id IS NULL AND learner_made = 0
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM whiteboards
                WHERE id IN (
                    SELECT id FROM artifacts
                    WHERE session_id = ? AND turn_id IS NULL AND learner_made = 0
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM animation_jobs
                WHERE id IN (
                    SELECT id FROM artifacts
                    WHERE session_id = ? AND turn_id IS NULL AND learner_made = 0
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM artifacts
                WHERE session_id = ? AND turn_id IS NULL AND learner_made = 0
                """,
                (session_id,),
            )
            self._pending.pop(session_id, None)

        self._with_db(write)

    def _public_from_row(self, row: sqlite3.Row) -> dict[str, object]:
        stored = json.loads(row["questions_json"])
        score = None
        if row["score_total"] is not None:
            score = {"earned": row["score_correct"], "total": row["score_total"]}
        raw = row["submitted_json"]
        submitted = json.loads(raw) if raw else {}
        return public_payload(
            row["id"],
            row["session_id"],
            stored,
            score=score,
            submitted=submitted,
        )

    def _save_sdk_session_id(self, session_id: str, sdk_session_id: str) -> None:
        def write(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET sdk_session_id = ? WHERE id = ?",
                (sdk_session_id, session_id),
            )

        self._with_db(write)

    def _discard_drafts(
        self, except_id: str | None = None, only_id: str | None = None
    ) -> bool:
        """Remove open sessions that never got a message (CH-19). A draft never
        ends and no profile pass runs on it. Returns whether any was removed."""

        def find(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """
                SELECT id FROM sessions
                WHERE ended_at IS NULL AND first_message IS NULL
                AND NOT EXISTS (SELECT 1 FROM turns WHERE session_id = sessions.id)
                """
            ).fetchall()
            return [
                row["id"]
                for row in rows
                if row["id"] != except_id and only_id in (None, row["id"])
            ]

        drafts = [id_ for id_ in self._with_db(find) if id_ not in self._busy]
        for draft_id in drafts:
            self._delete_rows(draft_id)
            self.resources.delete_session_files(draft_id)
        self._discarded.extend(drafts)
        return bool(drafts)

    def take_discarded(self) -> tuple[str, ...]:
        """Drafts removed since the last call, so their warmed agents can close."""

        taken, self._discarded = tuple(self._discarded), []
        return taken

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
                    created_at TEXT NOT NULL,
                    pointing_json TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(turns)").fetchall()
            }
            if "pointing_json" not in columns:
                conn.execute("ALTER TABLE turns ADD COLUMN pointing_json TEXT")
            if "animation_step_json" not in columns:
                conn.execute("ALTER TABLE turns ADD COLUMN animation_step_json TEXT")
            session_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "name" not in session_columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN name TEXT")
            if "first_message" not in session_columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN first_message TEXT")
            if "generated_title" not in session_columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN generated_title TEXT")
            # Startup create, so a database from before this index still gets it.
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS turns_session_id_created_at
                ON turns(session_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id),
                    turn_id TEXT REFERENCES turns(id),
                    kind TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    learner_made INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            artifact_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
            }
            if "learner_made" not in artifact_columns:
                conn.execute(
                    "ALTER TABLE artifacts ADD COLUMN learner_made INTEGER NOT NULL DEFAULT 0"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quizzes (
                    id TEXT PRIMARY KEY REFERENCES artifacts(id),
                    title TEXT NOT NULL,
                    questions_json TEXT NOT NULL,
                    score_correct INTEGER,
                    score_total INTEGER,
                    submitted_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decks (
                    id TEXT PRIMARY KEY REFERENCES artifacts(id),
                    title TEXT NOT NULL,
                    cards_json TEXT NOT NULL,
                    ratings_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS whiteboards (
                    id TEXT PRIMARY KEY REFERENCES artifacts(id),
                    drawing_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS animation_jobs (
                    id TEXT PRIMARY KEY REFERENCES artifacts(id),
                    status TEXT NOT NULL,
                    stage TEXT
                )
                """
            )
            job_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(animation_jobs)").fetchall()
            }
            if "stage" not in job_columns:
                conn.execute("ALTER TABLE animation_jobs ADD COLUMN stage TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS artifacts_session_id_turn_id
                ON artifacts(session_id, turn_id)
                """
            )
            create_profile_tables(conn)
            create_resource_tables(conn)

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
        # In WAL mode this cannot corrupt the database, and a commit no longer
        # waits for the disk. A power cut can lose the last few commits.
        conn.execute("PRAGMA synchronous = NORMAL")
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
