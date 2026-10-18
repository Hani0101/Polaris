import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from urllib.parse import unquote

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from polaris.agent import ReplyAgent
from polaris.animation import MissingJob, MissingPlayback
from polaris.animation_writer import AnimationWriter, ClaudeAnimationWriter
from polaris.animation_router import AnimationRouter
from polaris.lottie_writer import LottieAnimationWriter
from polaris.manim_writer import ClaudeManimWriter
from polaris.chat import (
    BlankMessage,
    Chat,
    InvalidAnimationStep,
    InvalidDrawing,
    InvalidPicture,
    InvalidPointing,
    MissingSession,
    NameTooLong,
    ReplyInProgress,
    SessionEnded,
)
from polaris.login import ApiKeyPresent, assert_claude_login
from polaris.profile import ProfilePass, ProfileUnreadable
from polaris.profile_pass import ClaudeProfilePass
from polaris.session_title import ClaudeTitleWriter, TitleWriter
from polaris.flashcards import InvalidRating, MissingDeck
from polaris.quiz import AlreadyChecked, InvalidSubmission, MissingQuiz
from polaris.resources import MAX_FILE_BYTES, MissingResource, ResourceRefused, too_big
from polaris.sign_in import (
    REFRESH_COOKIE,
    REFRESH_PATH,
    NoPairStored,
    PairAlreadyStored,
    PairRefused,
    RefreshRefused,
    SignInBlocked,
    Tokens,
    WrongPair,
)
from polaris.whiteboard import MissingWhiteboard, WhiteboardUnreadable
from polaris.teaching import ClaudeTeachingAgent, TeachingFailed, reply_error_message


class PointingBody(BaseModel):
    whiteboard_id: str
    element_ids: list[str]


class PictureBody(BaseModel):
    whiteboard_id: str
    media_type: str
    data: str


class AnimationStepBody(BaseModel):
    job_id: str
    step_id: str


class NameBody(BaseModel):
    name: str


class TurnBody(BaseModel):
    message: str
    pointing: PointingBody | None = None
    simplifies: str | None = None
    picture: PictureBody | None = None
    animation_step: AnimationStepBody | None = None
    # The board pinned above the conversation. The turn is about it (WB-19).
    pinned_whiteboard_id: str | None = None
    # Web mode: the agent may search and read the web for this reply only (CH-23).
    web: bool = False


class NoteBody(BaseModel):
    name: str = ""
    text: str


class WebPageBody(BaseModel):
    url: str


class ResourceEditBody(BaseModel):
    name: str | None = None
    text: str | None = None


class AnswerBody(BaseModel):
    question_id: str
    choice_id: str


class RatingBody(BaseModel):
    card_id: str
    rating: str


class PairBody(BaseModel):
    username: str
    password: str


class ChosenPairBody(PairBody):
    password_again: str


# HTML from a job that finished before decision 0006 runs in its own
# opaque origin, even when opened directly, so it cannot call this API. It
# cannot load anything from the network either. New jobs store JSON data,
# which the browser does not run.
PLAYBACK_HEADERS = {
    "Content-Security-Policy": (
        "sandbox allow-scripts; default-src 'none'; "
        "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data: blob:; media-src 'self' data: blob:; font-src data:; "
        "webrtc 'block'"
    ),
    "X-Content-Type-Options": "nosniff",
}


# v1 is one learner on one machine (decision 0001, AU-14). Most routes are open
# and the first use chooses the pair, so a request from another machine, or
# for a host name that is not this machine (DNS rebinding), is refused.
LOCAL_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def _from_this_machine(request: Request) -> bool:
    # No client address means a local socket, not the network.
    if request.client is not None and request.client.host not in LOCAL_NAMES:
        return False
    host = request.headers.get("host", "")
    if host.startswith("["):
        name = host[1:].partition("]")[0]
    else:
        name = host.rpartition(":")[0] if ":" in host else host
    return name.lower() in LOCAL_NAMES


def _sse(payload: dict[str, object]) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


def _signed_in_response(tokens: Tokens) -> JSONResponse:
    """The access token goes to page memory; the refresh token only to a cookie (AU-08, AU-09)."""

    response = JSONResponse(
        {
            "access_token": tokens.access_token,
            "expires_in": tokens.access_expires_in,
            "username": tokens.username,
        },
        headers={"Cache-Control": "no-store"},
    )
    # Not Secure: v1 is served over plain http on this machine (decision 0001).
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=tokens.refresh_max_age,
        path=REFRESH_PATH,
        httponly=True,
        samesite="strict",
    )
    return response


def _signed_out_response(status_code: int, detail: str | None = None) -> JSONResponse:
    content = {"detail": detail} if detail is not None else {}
    response = JSONResponse(status_code=status_code, content=content)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, httponly=True, samesite="strict")
    return response


async def _close_quietly(agent: ReplyAgent, session_id: str) -> None:
    try:
        await agent.close_session(session_id)
    except Exception:
        pass


def create_app(
    data_dir: Path,
    agent: ReplyAgent | None = None,
    profile_pass: ProfilePass | None = None,
    title_writer: TitleWriter | None = None,
) -> FastAPI:
    """Build the API. Refuses to start when an API key would replace the Claude login."""

    assert_claude_login()
    data_dir.mkdir(parents=True, exist_ok=True)
    animation_writer: AnimationWriter | None = None
    if agent is None:
        agent = ClaudeTeachingAgent(data_dir / "claude-work")
        if profile_pass is None:
            profile_pass = ClaudeProfilePass(data_dir / "claude-work")
        if title_writer is None:
            title_writer = ClaudeTitleWriter(data_dir / "claude-work")
        # A router sends maths and heavy graphs to Manim and the rest to
        # Lottie (AN-21). POLARIS_ANIMATION_ENGINE=manim, lottie, or data
        # forces one writer for every job.
        engine = os.environ.get("POLARIS_ANIMATION_ENGINE", "auto")
        if engine == "data":
            animation_writer = ClaudeAnimationWriter(data_dir / "claude-work")
        elif engine == "manim":
            animation_writer = ClaudeManimWriter(data_dir / "claude-work")
        elif engine == "lottie":
            animation_writer = LottieAnimationWriter(data_dir / "lottie-work")
        else:
            animation_writer = AnimationRouter(
                manim=ClaudeManimWriter(data_dir / "claude-work"),
                lottie=LottieAnimationWriter(data_dir / "lottie-work"),
                work_dir=data_dir / "claude-work",
            )
    chat = Chat(
        data_dir,
        agent,
        profile_pass=profile_pass,
        animation_writer=animation_writer,
        title_writer=title_writer,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            # A session that ended just before Polaris stops still gets its pass.
            await asyncio.to_thread(app.state.chat.wait_for_session_ends)
            closer = getattr(app.state.chat.agent, "close_all", None)
            try:
                if closer is not None:
                    await closer()
            finally:
                app.state.chat.close()

    app = FastAPI(lifespan=lifespan)
    app.state.chat = chat
    app.state.api_key_stop = False
    app.state.background = set()

    @app.middleware("http")
    async def stop_when_api_key_seen(request, call_next):
        if app.state.api_key_stop or chat.api_key_seen:
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

    # Added last, so it runs first.
    @app.middleware("http")
    async def answer_this_machine_only(request, call_next):
        if not _from_this_machine(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Polaris answers only on this machine."},
            )
        return await call_next(request)

    @app.exception_handler(MissingSession)
    async def missing_session(_request, exc: MissingSession) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(NameTooLong)
    async def name_too_long(_request, exc: NameTooLong) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

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

    @app.exception_handler(InvalidPicture)
    async def invalid_picture(_request, exc: InvalidPicture) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(InvalidAnimationStep)
    async def invalid_animation_step(
        _request, exc: InvalidAnimationStep
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(MissingResource)
    async def missing_resource(_request, exc: MissingResource) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ResourceRefused)
    async def resource_refused(_request, exc: ResourceRefused) -> JSONResponse:
        status = {"too_big": 413, "fetch_failed": 502}.get(exc.code, 422)
        return JSONResponse(
            status_code=status, content={"detail": str(exc), "code": exc.code}
        )

    @app.exception_handler(MissingDeck)
    async def missing_deck(_request, exc: MissingDeck) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidRating)
    async def invalid_rating(_request, exc: InvalidRating) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(AlreadyChecked)
    async def already_checked(_request, exc: AlreadyChecked) -> JSONResponse:
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

    @app.exception_handler(PairRefused)
    async def pair_refused(_request, exc: PairRefused) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PairAlreadyStored)
    async def pair_already_stored(_request, exc: PairAlreadyStored) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(NoPairStored)
    async def no_pair_stored(_request, exc: NoPairStored) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(WrongPair)
    async def wrong_pair(_request, exc: WrongPair) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(SignInBlocked)
    async def sign_in_blocked(_request, exc: SignInBlocked) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": str(exc), "blocked_seconds": exc.seconds_left},
            headers={"Retry-After": str(exc.seconds_left)},
        )

    def require_sign_in(request: Request) -> None:
        """AU-12: only the profile and its evidence need a valid access token."""

        if not chat.sign_in.signed_in(request.headers.get("authorization")):
            raise HTTPException(
                status_code=401,
                detail="Sign in to see your profile.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @app.get("/api/sign-in")
    def sign_in_status() -> dict[str, object]:
        return chat.sign_in.status()

    @app.post("/api/sign-in/pair")
    async def choose_pair(body: ChosenPairBody) -> JSONResponse:
        tokens = await asyncio.to_thread(
            chat.sign_in.choose_pair, body.username, body.password, body.password_again
        )
        return _signed_in_response(tokens)

    @app.post("/api/sign-in")
    async def sign_in(body: PairBody) -> JSONResponse:
        tokens = await asyncio.to_thread(chat.sign_in.sign_in, body.username, body.password)
        return _signed_in_response(tokens)

    @app.post(REFRESH_PATH)
    def refresh_sign_in(request: Request) -> JSONResponse:
        try:
            tokens = chat.sign_in.refresh(request.cookies.get(REFRESH_COOKIE))
        except RefreshRefused:
            return _signed_out_response(401, "Sign in again.")
        return _signed_in_response(tokens)

    # Sign-out lives on the refresh path, the only path the cookie is sent to (AU-11).
    @app.delete(REFRESH_PATH)
    def sign_out(request: Request) -> JSONResponse:
        chat.sign_in.sign_out(request.cookies.get(REFRESH_COOKIE))
        return _signed_out_response(200)

    @app.get("/api/profile", dependencies=[Depends(require_sign_in)])
    def read_profile() -> dict[str, list[str]]:
        # The profile includes facts from a pass still running (PR-05).
        chat.wait_for_session_ends()
        return {"facts": list(chat.read_profile().facts)}

    def close_discarded() -> None:
        """A draft left unsent is gone; close the agent it may have warmed (CH-19)."""

        for session_id in chat.take_discarded():
            task = asyncio.get_running_loop().create_task(
                _close_quietly(chat.agent, session_id)
            )
            app.state.background.add(task)
            task.add_done_callback(app.state.background.discard)

    @app.get("/api/sessions")
    def list_sessions() -> dict[str, list[dict[str, object]]]:
        return {"sessions": chat.list_sessions()}

    @app.post("/api/sessions")
    async def start_session() -> dict[str, object]:
        session, ended_ids = await asyncio.to_thread(chat.start)
        chat.end_in_background(ended_ids)
        close_discarded()
        return session

    @app.get("/api/sessions/{session_id}")
    def read_session(session_id: str) -> dict[str, object]:
        return chat.get(session_id)

    @app.patch("/api/sessions/{session_id}")
    def rename_session(session_id: str, body: NameBody) -> dict[str, object]:
        return chat.rename(session_id, body.name)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, object]:
        return await chat.delete_session(session_id)

    @app.post("/api/sessions/{session_id}/open")
    async def open_session(session_id: str) -> dict[str, object]:
        session, ended_ids = await asyncio.to_thread(chat.open, session_id)
        chat.end_in_background(ended_ids)
        close_discarded()
        return session

    @app.post("/api/sessions/{session_id}/warm", status_code=202)
    async def warm_session(session_id: str) -> dict[str, str]:
        """The learner started typing: connect the agent before the reply needs it."""

        chat.warm_in_background(session_id)
        return {"id": session_id}

    @app.post("/api/sessions/{session_id}/leave")
    async def leave_session(session_id: str) -> dict[str, object]:
        if await asyncio.to_thread(chat.leave, session_id):
            chat.end_in_background((session_id,))
        close_discarded()
        try:
            return await asyncio.to_thread(chat.get, session_id)
        except MissingSession:
            # A draft is discarded, not ended (CH-19).
            return {"id": session_id, "ended": False, "turns": []}

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
        picture = None
        if body.picture is not None:
            picture = await asyncio.to_thread(
                chat.resolve_picture,
                session_id,
                body.picture.whiteboard_id,
                body.picture.media_type,
                body.picture.data,
            )
        animation_step = None
        if body.animation_step is not None:
            animation_step = await asyncio.to_thread(
                chat.resolve_animation_step,
                session_id,
                body.animation_step.job_id,
                body.animation_step.step_id,
            )
        pinned = None
        if body.pinned_whiteboard_id is not None and body.pinned_whiteboard_id.strip():
            pinned = await asyncio.to_thread(
                chat.resolve_pinned,
                session_id,
                body.pinned_whiteboard_id,
            )
        chat.raise_if_busy(session_id)

        async def events() -> AsyncIterator[str]:
            try:
                async for chunk in chat.stream_reply(
                    session_id,
                    text,
                    pointing,
                    simplify,
                    picture=picture,
                    animation_step=animation_step,
                    pinned=pinned,
                    web=body.web,
                ):
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

    @app.post("/api/sessions/{session_id}/whiteboards", status_code=201)
    def create_whiteboard(session_id: str) -> dict[str, object]:
        return chat.create_learner_whiteboard(session_id)

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

    @app.get("/api/sessions/{session_id}/resources")
    def list_resources(session_id: str) -> dict[str, list[dict[str, object]]]:
        return {"resources": chat.list_resources(session_id)}

    @app.post("/api/sessions/{session_id}/resources", status_code=201)
    async def add_resource(session_id: str, request: Request) -> dict[str, object]:
        """Add a file. The body is the file and X-Filename is its name (RS-04)."""

        await asyncio.to_thread(chat.list_resources, session_id)
        declared = request.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > MAX_FILE_BYTES:
            raise too_big()
        data = bytearray()
        async for piece in request.stream():
            data.extend(piece)
            if len(data) > MAX_FILE_BYTES:
                raise too_big()
        filename = unquote(request.headers.get("x-filename", ""))
        return await asyncio.to_thread(
            chat.add_resource_file, session_id, filename, bytes(data)
        )

    @app.post("/api/sessions/{session_id}/resources/notes", status_code=201)
    def add_resource_note(session_id: str, body: NoteBody) -> dict[str, object]:
        return chat.add_resource_note(session_id, body.name, body.text)

    @app.post("/api/sessions/{session_id}/resources/web", status_code=201)
    async def add_resource_web(session_id: str, body: WebPageBody) -> dict[str, object]:
        """Fetch a public page by its link (RS-22). The fetch blocks, so it runs off the loop."""

        return await asyncio.to_thread(chat.add_resource_web, session_id, body.url)

    @app.get("/api/sessions/{session_id}/resources/{resource_id}")
    def read_resource(session_id: str, resource_id: str) -> dict[str, object]:
        return chat.get_resource(session_id, resource_id)

    @app.get("/api/sessions/{session_id}/resources/{resource_id}/file")
    def read_resource_file(session_id: str, resource_id: str) -> FileResponse:
        path, media_type = chat.resource_file(session_id, resource_id)
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "Content-Security-Policy": "sandbox; default-src 'none'",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "inline",
            },
        )

    @app.patch("/api/sessions/{session_id}/resources/{resource_id}")
    def edit_resource(
        session_id: str, resource_id: str, body: ResourceEditBody
    ) -> dict[str, object]:
        result: dict[str, object] = chat.get_resource(session_id, resource_id)
        if body.name is not None:
            result = chat.rename_resource(session_id, resource_id, body.name)
        if body.text is not None:
            result = chat.edit_resource_note(session_id, resource_id, body.text)
        return {key: value for key, value in result.items() if key != "text_pages"}

    @app.delete("/api/sessions/{session_id}/resources/{resource_id}")
    def remove_resource(session_id: str, resource_id: str) -> dict[str, str]:
        chat.remove_resource(session_id, resource_id)
        return {"id": resource_id}

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

    @app.get("/api/sessions/{session_id}/jobs/{job_id}/manim/{name:path}")
    def read_job_manim_asset(session_id: str, job_id: str, name: str) -> FileResponse:
        asset = chat.get_animation_asset(session_id, job_id, name)
        return FileResponse(asset.path, media_type=asset.media_type, headers=PLAYBACK_HEADERS)

    @app.get("/api/quizzes/{quiz_id}")
    def read_quiz(quiz_id: str) -> dict[str, object]:
        return chat.get_quiz(quiz_id)

    @app.post("/api/quizzes/{quiz_id}/answer")
    def answer_quiz(quiz_id: str, body: AnswerBody) -> dict[str, object]:
        return chat.answer_quiz(quiz_id, body.question_id, body.choice_id)

    @app.get("/api/decks/{deck_id}")
    def read_deck(deck_id: str) -> dict[str, object]:
        return chat.get_deck(deck_id)

    @app.post("/api/decks/{deck_id}/ratings")
    def rate_card(deck_id: str, body: RatingBody) -> dict[str, object]:
        return chat.rate_card(deck_id, body.card_id, body.rating)

    @app.delete("/api/decks/{deck_id}/ratings")
    def reset_ratings(deck_id: str) -> dict[str, object]:
        return chat.reset_ratings(deck_id)

    return app
