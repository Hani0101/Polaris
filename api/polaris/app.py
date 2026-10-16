import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from polaris.agent import ReplyAgent
from polaris.animation import MissingJob, MissingPlayback
from polaris.animation_writer import AnimationWriter, ClaudeAnimationWriter
from polaris.chat import (
    BlankMessage,
    Chat,
    InvalidDrawing,
    InvalidPointing,
    MissingSession,
    ReplyInProgress,
    SessionEnded,
)
from polaris.login import ApiKeyPresent, assert_claude_login
from polaris.profile import ProfilePass, ProfileUnreadable, load_profile
from polaris.profile_pass import ClaudeProfilePass
from polaris.quiz import AlreadyGraded, InvalidSubmission, MissingQuiz
from polaris.whiteboard import MissingWhiteboard, WhiteboardUnreadable
from polaris.teaching import ClaudeTeachingAgent, TeachingFailed, reply_error_message


class PointingBody(BaseModel):
    whiteboard_id: str
    element_ids: list[str]


class TurnBody(BaseModel):
    message: str
    pointing: PointingBody | None = None
    simplifies: str | None = None


class GradeBody(BaseModel):
    choices: dict[str, str]


# Agent-written HTML runs in its own opaque origin, even when opened
# directly, so it cannot call this API. It cannot load anything from the
# network either (AN-04).
PLAYBACK_HEADERS = {
    "Content-Security-Policy": (
        "sandbox allow-scripts; default-src 'none'; "
        "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data: blob:; media-src 'self' data: blob:; font-src data:"
    ),
    "X-Content-Type-Options": "nosniff",
}


def _sse(payload: dict[str, object]) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


def create_app(
    data_dir: Path,
    agent: ReplyAgent | None = None,
    profile_pass: ProfilePass | None = None,
) -> FastAPI:
    """Build the API. Refuses to start when an API key would replace the Claude login."""

    assert_claude_login()
    data_dir.mkdir(parents=True, exist_ok=True)
    animation_writer: AnimationWriter | None = None
    if agent is None:
        agent = ClaudeTeachingAgent(data_dir / "claude-work")
        if profile_pass is None:
            profile_pass = ClaudeProfilePass(data_dir / "claude-work")
        animation_writer = ClaudeAnimationWriter(data_dir / "claude-work")
    chat = Chat(
        data_dir,
        agent,
        profile_pass=profile_pass,
        animation_writer=animation_writer,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            closer = getattr(app.state.chat.agent, "close_all", None)
            try:
                if closer is not None:
                    await closer()
            finally:
                app.state.chat.close()

    app = FastAPI(lifespan=lifespan)
    app.state.chat = chat
    app.state.api_key_stop = False

    @app.middleware("http")
    async def stop_when_api_key_seen(request, call_next):
        if app.state.api_key_stop:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Polaris stopped because an API key is present. "
                        "v1 uses the Claude login on this machine."
                    )
                },
            )
        return await call_next(request)

    @app.exception_handler(MissingSession)
    async def missing_session(_request, exc: MissingSession) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(BlankMessage)
    async def blank_message(_request, exc: BlankMessage) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(SessionEnded)
    async def session_ended(_request, exc: SessionEnded) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ReplyInProgress)
    async def reply_in_progress(_request, exc: ReplyInProgress) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(MissingQuiz)
    async def missing_quiz(_request, exc: MissingQuiz) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MissingJob)
    async def missing_job(_request, exc: MissingJob) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MissingPlayback)
    async def missing_playback(_request, exc: MissingPlayback) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MissingWhiteboard)
    async def missing_whiteboard(_request, exc: MissingWhiteboard) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(WhiteboardUnreadable)
    async def whiteboard_unreadable(
        _request, exc: WhiteboardUnreadable
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidDrawing)
    async def invalid_drawing(_request, exc: InvalidDrawing) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidPointing)
    async def invalid_pointing(_request, exc: InvalidPointing) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(AlreadyGraded)
    async def already_graded(_request, exc: AlreadyGraded) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidSubmission)
    async def invalid_submission(_request, exc: InvalidSubmission) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ApiKeyPresent)
    async def api_key_present(_request, exc: ApiKeyPresent) -> JSONResponse:
        app.state.api_key_stop = True
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/profile")
    def read_profile() -> dict[str, list[str]]:
        profile = load_profile(chat.profile_path)
        return {"facts": list(profile.facts)}

    @app.get("/api/sessions")
    def list_sessions() -> dict[str, list[dict[str, object]]]:
        return {"sessions": chat.list_sessions()}

    async def close_ended(session_ids: tuple[str, ...]) -> None:
        for session_id in session_ids:
            await chat.agent.close_session(session_id)
            await chat.run_profile_pass(session_id)

    @app.post("/api/sessions")
    async def start_session() -> dict[str, object]:
        session, ended_ids = await asyncio.to_thread(chat.start)
        await close_ended(ended_ids)
        return session

    @app.get("/api/sessions/{session_id}")
    def read_session(session_id: str) -> dict[str, object]:
        return chat.get(session_id)

    @app.post("/api/sessions/{session_id}/open")
    async def open_session(session_id: str) -> dict[str, object]:
        session, ended_ids = await asyncio.to_thread(chat.open, session_id)
        await close_ended(ended_ids)
        return session

    @app.post("/api/sessions/{session_id}/leave")
    async def leave_session(session_id: str) -> dict[str, object]:
        should_close = await asyncio.to_thread(chat.leave, session_id)
        if should_close:
            await chat.agent.close_session(session_id)
            await chat.run_profile_pass(session_id)
        return await asyncio.to_thread(chat.get, session_id)

    @app.post("/api/sessions/{session_id}/turns")
    async def send_turn(session_id: str, body: TurnBody) -> StreamingResponse:
        text = await asyncio.to_thread(chat.validate_turn, session_id, body.message)
        pointing = None
        if body.pointing is not None:
            pointing = await asyncio.to_thread(
                chat.resolve_pointing,
                session_id,
                body.pointing.whiteboard_id,
                body.pointing.element_ids,
            )
        simplify = None
        if body.simplifies is not None and body.simplifies.strip():
            simplify = await asyncio.to_thread(
                chat.resolve_simplify,
                session_id,
                body.simplifies,
            )
        chat.raise_if_busy(session_id)

        async def events() -> AsyncIterator[str]:
            try:
                async for chunk in chat.stream_reply(session_id, text, pointing, simplify):
                    if isinstance(chunk, str):
                        yield _sse({"text": chunk})
                    else:
                        yield _sse({"artifact": chunk})
                yield _sse({"done": True})
            except ApiKeyPresent as exc:
                app.state.api_key_stop = True
                yield _sse({"error": str(exc)})
            except (TeachingFailed, ProfileUnreadable) as exc:
                yield _sse({"error": str(exc)})
            except Exception as exc:
                yield _sse({"error": reply_error_message(exc)})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/sessions/{session_id}/whiteboards")
    def list_whiteboards(session_id: str) -> dict[str, list[dict[str, object]]]:
        return {"whiteboards": chat.list_whiteboards(session_id)}

    @app.get("/api/sessions/{session_id}/whiteboards/{whiteboard_id}")
    def read_whiteboard(session_id: str, whiteboard_id: str) -> dict[str, object]:
        return chat.get_whiteboard(session_id, whiteboard_id)

    @app.put("/api/sessions/{session_id}/whiteboards/{whiteboard_id}")
    def update_whiteboard(
        session_id: str,
        whiteboard_id: str,
        drawing: dict[str, Any] = Body(),
    ) -> dict[str, object]:
        return chat.update_whiteboard(session_id, whiteboard_id, drawing)

    @app.get("/api/sessions/{session_id}/jobs/{job_id}")
    def read_job(session_id: str, job_id: str) -> dict[str, object]:
        return chat.get_animation_job(session_id, job_id)

    @app.get("/api/sessions/{session_id}/jobs/{job_id}/media")
    def read_job_media(session_id: str, job_id: str) -> FileResponse:
        playback = chat.get_animation_media(session_id, job_id)
        return FileResponse(
            playback.path,
            media_type=playback.media_type,
            headers=PLAYBACK_HEADERS,
        )

    @app.get("/api/quizzes/{quiz_id}")
    def read_quiz(quiz_id: str) -> dict[str, object]:
        return chat.get_quiz(quiz_id)

    @app.post("/api/quizzes/{quiz_id}/grade")
    def grade_quiz(quiz_id: str, body: GradeBody) -> dict[str, object]:
        return chat.grade_quiz(quiz_id, body.choices)

    return app
