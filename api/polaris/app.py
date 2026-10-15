import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from polaris.agent import ReplyAgent
from polaris.chat import (
    BlankMessage,
    Chat,
    MissingSession,
    ReplyInProgress,
    SessionEnded,
)
from polaris.login import ApiKeyPresent, assert_claude_login
from polaris.profile import ProfileUnreadable, load_profile
from polaris.teaching import ClaudeTeachingAgent, TeachingFailed


class TurnBody(BaseModel):
    message: str


def _sse(payload: dict[str, object]) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


def create_app(data_dir: Path, agent: ReplyAgent | None = None) -> FastAPI:
    """Build the API. Refuses to start when an API key would replace the Claude login."""

    assert_claude_login()
    data_dir.mkdir(parents=True, exist_ok=True)
    if agent is None:
        agent = ClaudeTeachingAgent(data_dir / "claude-work")
    chat = Chat(data_dir, agent)

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

    @app.post("/api/sessions")
    async def start_session() -> dict[str, object]:
        session, ended_ids = await asyncio.to_thread(chat.start)
        for session_id in ended_ids:
            await chat.agent.close_session(session_id)
        return session

    @app.get("/api/sessions/{session_id}")
    def read_session(session_id: str) -> dict[str, object]:
        return chat.get(session_id)

    @app.post("/api/sessions/{session_id}/open")
    async def open_session(session_id: str) -> dict[str, object]:
        session, ended_ids = await asyncio.to_thread(chat.open, session_id)
        for left_id in ended_ids:
            await chat.agent.close_session(left_id)
        return session

    @app.post("/api/sessions/{session_id}/leave")
    async def leave_session(session_id: str) -> dict[str, object]:
        should_close = await asyncio.to_thread(chat.leave, session_id)
        if should_close:
            await chat.agent.close_session(session_id)
        return await asyncio.to_thread(chat.get, session_id)

    @app.post("/api/sessions/{session_id}/turns")
    async def send_turn(session_id: str, body: TurnBody) -> StreamingResponse:
        text = await asyncio.to_thread(chat.validate_turn, session_id, body.message)
        chat.raise_if_busy(session_id)

        async def events() -> AsyncIterator[str]:
            try:
                async for chunk in chat.stream_reply(session_id, text):
                    yield _sse({"text": chunk})
                yield _sse({"done": True})
            except ApiKeyPresent as exc:
                app.state.api_key_stop = True
                yield _sse({"error": str(exc)})
            except (TeachingFailed, ProfileUnreadable) as exc:
                yield _sse({"error": str(exc)})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app
