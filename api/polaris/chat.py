"""Sessions made of turns. The profile is read before each reply.

The teaching agent does not write the profile. The session-end pass does.
"""

import asyncio
import json
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from polaris.animation_format import Animation
from polaris.animation_writer import AnimationWriter, new_cli_loop
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
from polaris.quiz import AlreadyGraded, MissingQuiz, grade, normalize_spec, public_payload
from polaris.whiteboard import (
    MissingWhiteboard,
    Whiteboard,
    WhiteboardUnreadable,
    apply_marks,
    check_drawing,
    check_learner_drawing,
    pointed_element_errors,
    simpler_count_errors,
)


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


class Chat:
    def __init__(
        self,
        data_dir: Path,
        agent: ReplyAgent,
        profile_pass: ProfilePass | None = None,
        animation_writer: AnimationWriter | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.agent = agent
        self._profile_pass = profile_pass
        self._animation_writer = animation_writer
        self.db_path = data_dir / "polaris.db"
        self.profile_path = data_dir / "profile.json"
        self._lock = threading.Lock()
        self._busy: set[str] = set()
        self._pending: dict[str, list[dict[str, object]]] = {}
        self._mark_rollbacks: dict[str, list[tuple[str, str]]] = {}
        self._animation_notices: dict[str, list[str]] = {}
        # job id -> worker writing that animation off the turn (AN-01).
        self._animation_threads: dict[str, threading.Thread] = {}
        self._conn: sqlite3.Connection | None = None
        self._open_db()
        self._init_db()
        self._fail_interrupted_jobs()
        binder = getattr(agent, "bind_store", None)
        if callable(binder):
            binder(
                self.create_quiz,
                self.create_whiteboard,
                mark_whiteboard=self.mark_whiteboard,
                preview_marks=self.preview_marks,
                start_animation_job=self.start_animation_job,
            )

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

    async def stream_reply(
        self,
        session_id: str,
        message: str,
        pointing: Pointing | None = None,
        simplify: Whiteboard | None = None,
        picture: BoardPicture | None = None,
        animation_step: AnimationStep | None = None,
    ) -> AsyncIterator[str | dict[str, object]]:
        text = await asyncio.to_thread(self.validate_turn, session_id, message)
        self.raise_if_busy(session_id)
        self._busy.add(session_id)
        parts: list[str] = []
        created: list[dict[str, object]] = []
        completed = False
        captured: str | None = None

        def drain() -> list[dict[str, object]]:
            taken = self._take_pending(session_id)
            created.extend(taken)
            return taken

        try:
            for notice in self.take_animation_notices(session_id):
                parts.append(notice)
                yield notice
            profile = await asyncio.to_thread(self.read_profile)
            prior = await asyncio.to_thread(self._turns, session_id)
            sdk_session_id = await asyncio.to_thread(self._sdk_session_id, session_id)
            whiteboards = await asyncio.to_thread(self.whiteboards_for_reply, session_id)
            # The picture is for this turn only and is not stored.
            extra: dict[str, Any] = {"picture": picture} if picture is not None else {}
            animations = await asyncio.to_thread(self.animations_for_reply, session_id)
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
                **extra,
                animations=animations,
                animation_step=animation_step,
            ):
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

    def create_quiz(self, session_id: str, spec: dict[str, Any]) -> dict[str, object]:
        self._require(session_id)
        stored = normalize_spec(spec)
        quiz_id = str(uuid.uuid4())
        payload = public_payload(
            quiz_id, session_id, stored, score=None, submitted=None
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
        self._launch_animation(session_id, job_id, brief)
        return payload

    def _launch_animation(self, session_id: str, job_id: str, brief: str) -> None:
        writer = self._animation_writer
        if writer is None:
            return
        thread = threading.Thread(
            target=self._run_animation_job,
            args=(writer, session_id, job_id, brief),
            name=f"polaris-animation-{job_id[:8]}",
            daemon=True,
        )
        with self._lock:
            self._animation_threads[job_id] = thread
        thread.start()

    def _run_animation_job(
        self, writer: AnimationWriter, session_id: str, job_id: str, brief: str
    ) -> None:
        """Worker: write, check, and fix one animation (AN-05, AN-09, AN-10).

        Runs on its own loop, one that can spawn the Claude CLI.
        """

        loop = new_cli_loop()
        last_data: dict[str, Any] | None = None

        def write_animation(errors: list[str] | None) -> dict[str, Any]:
            nonlocal last_data
            last_data = loop.run_until_complete(
                writer.write(
                    brief,
                    failed_data=last_data if errors is not None else None,
                    errors=errors,
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

    def animation_for_reply(self, session_id: str, job_id: str) -> Animation | None:
        """The stored animation of a ready job in this session, if it is in the format."""

        try:
            job = self.get_animation_job(session_id, job_id)
        except MissingJob:
            return None
        if job["status"] != JOB_READY:
            return None
        return load_animation(self.animation_work_dir(job_id))

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
            found = load_animation(self.data_dir / "animation" / job_id)
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

        def read(conn: sqlite3.Connection) -> list[dict[str, object]]:
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
            shown: list[dict[str, object]] = []
            for row in rows:
                payload = self._whiteboard_payload(json.loads(row["drawing_json"]))
                if payload is not None:
                    shown.append(payload)
            return shown

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
        payload = self._whiteboard_payload(json.loads(raw))
        if payload is None:
            raise WhiteboardUnreadable()
        return payload

    def update_whiteboard(
        self, session_id: str, whiteboard_id: str, drawing: object
    ) -> dict[str, object]:
        """Store a learner's drawing after the same check the agent drawing uses."""

        self._require(session_id)
        stored = self._stored_whiteboard(session_id, whiteboard_id)
        incoming: object = drawing
        if isinstance(drawing, dict):
            incoming = {**drawing, "session_id": session_id}
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
        checked_stored = check_drawing(json.loads(raw))
        if checked_stored.whiteboard is None:
            raise WhiteboardUnreadable()
        checked = apply_marks(checked_stored.whiteboard, action)
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

    def whiteboards_for_reply(self, session_id: str) -> list[Whiteboard]:
        boards: list[Whiteboard] = []
        for payload in self.list_whiteboards(session_id):
            drawing = dict(payload)
            drawing.pop("kind", None)
            checked = check_drawing(drawing)
            if checked.whiteboard is not None:
                boards.append(checked.whiteboard)
        return boards

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
        checked = check_drawing(json.loads(raw))
        if checked.whiteboard is None:
            raise WhiteboardUnreadable()
        return checked.whiteboard

    def _whiteboard_payload(self, drawing: object) -> dict[str, object] | None:
        checked = check_drawing(drawing)
        if checked.whiteboard is None or not isinstance(drawing, dict):
            return None
        payload = dict(drawing)
        payload["kind"] = "whiteboard"
        return payload

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

    def grade_quiz(
        self, quiz_id: str, choices: dict[str, str]
    ) -> dict[str, object]:
        def write(conn: sqlite3.Connection) -> dict[str, object] | None:
            row = conn.execute(
                """
                SELECT a.id, a.session_id, q.questions_json, q.score_total
                FROM artifacts a
                JOIN quizzes q ON q.id = a.id
                WHERE a.id = ? AND a.kind = 'quiz'
                """,
                (quiz_id,),
            ).fetchone()
            if row is None:
                return None
            if row["score_total"] is not None:
                raise AlreadyGraded()
            stored = json.loads(row["questions_json"])
            score, submitted = grade(stored, choices)
            updated = conn.execute(
                """
                UPDATE quizzes
                SET score_correct = ?, score_total = ?, submitted_json = ?
                WHERE id = ? AND score_total IS NULL
                """,
                (score["earned"], score["total"], json.dumps(submitted), quiz_id),
            )
            if updated.rowcount == 0:
                raise AlreadyGraded()
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
                       j.stage AS job_stage
                FROM artifacts a
                LEFT JOIN quizzes q ON q.id = a.id AND a.kind = 'quiz'
                LEFT JOIN whiteboards w ON w.id = a.id AND a.kind = 'whiteboard'
                LEFT JOIN animation_jobs j ON j.id = a.id AND a.kind = 'animation'
                WHERE a.session_id = ?
                ORDER BY a.created_at ASC, a.id ASC
                """,
                (session_id,),
            ).fetchall()
            by_turn: dict[str, list[dict[str, object]]] = {}
            for row in artifact_rows:
                turn_id = row["turn_id"]
                if turn_id is None:
                    continue
                if row["kind"] == "whiteboard":
                    payload = self._whiteboard_payload(json.loads(row["drawing_json"]))
                    if payload is not None:
                        by_turn.setdefault(turn_id, []).append(payload)
                    continue
                if row["kind"] == "quiz":
                    by_turn.setdefault(turn_id, []).append(self._public_from_row(row))
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
                    """,
                    (turn_id, artifact_id, session_id),
                )

        self._with_db(write)
        with self._lock:
            self._mark_rollbacks.pop(session_id, None)

    def _take_pending(self, session_id: str) -> list[dict[str, object]]:
        with self._lock:
            return list(self._pending.pop(session_id, []))

    def _discard_unattached(self, session_id: str) -> None:
        with self._lock:
            rollbacks = list(self._mark_rollbacks.pop(session_id, []))

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
                    WHERE session_id = ? AND turn_id IS NULL
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM whiteboards
                WHERE id IN (
                    SELECT id FROM artifacts
                    WHERE session_id = ? AND turn_id IS NULL
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM animation_jobs
                WHERE id IN (
                    SELECT id FROM artifacts
                    WHERE session_id = ? AND turn_id IS NULL
                )
                """,
                (session_id,),
            )
            conn.execute(
                """
                DELETE FROM artifacts
                WHERE session_id = ? AND turn_id IS NULL
                """,
                (session_id,),
            )
            self._pending.pop(session_id, None)

        self._with_db(write)

    def _public_from_row(self, row: sqlite3.Row) -> dict[str, object]:
        stored = json.loads(row["questions_json"])
        score = None
        submitted = None
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
                    created_at TEXT NOT NULL
                )
                """
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
