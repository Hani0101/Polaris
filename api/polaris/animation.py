"""Animation jobs. The job id is stored before the animation is ready.

A new animation is data, not code (decision 0006, AN-04). After a job
starts, the writer returns animation data and ``check_animation`` checks it
(AN-10, AN-11). On a refused check the errors go back to the writer; at
most two fixes, three runs in total (AN-05). After that the job fails and
the session is told to try later (AN-09). A ready job keeps
``animation.json`` under its work dir so the learner can open the
animation again (AN-06). Jobs finished before this format kept an HTML,
video, or GIF file, and those still open.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polaris.animation_format import Animation, check_animation
from polaris.lottie_video import LottieVideo, check_lottie_video, is_lottie_video

# Either format can be stored: Polaris's own animation data or a Lottie video.
StoredAnimation = Animation | LottieVideo

RUNNING = "running"
READY = "ready"
FAILED = "failed"

# Stages of a running job (AN-19). A ready or failed job has none. A choosing
# job waits for the learner to pick Manim or Lottie (AN-21). A queued job
# waits for a free place to run (AN-25).
CHOOSING = "choosing"
QUEUED = "queued"
WRITING = "writing"
CHECKING = "checking"
FIXING = "fixing"

# Original run plus this many fixes (AN-05).
MAX_FIX_ATTEMPTS = 2
MAX_RUNS = 1 + MAX_FIX_ATTEMPTS

# How many check errors one fix prompt carries. The rest are counted.
MAX_ERRORS_TO_WRITER = 20

WAITING_NOTICE = (
    "This animation may take some time. "
    "You can keep talking in this session or another. "
    "The operating system will notify you when it is ready."
)

# AN-02 and AN-21: the job waits on its card until the learner picks an engine.
CHOOSING_NOTICE = (
    "Choose Manim or Lottie on the animation card to start it. " + WAITING_NOTICE
)

FAILURE_NOTICE = (
    "Polaris cannot create the animation right now. Try later."
)

ANIMATION_FILE = "animation.json"
ANIMATION_MEDIA_TYPE = "application/json"

# Work dir playback names, first match wins (AN-06). Only animation.json is
# written now; the rest are from jobs that finished before decision 0006.
PLAYBACK_FILES: tuple[tuple[str, str], ...] = (
    (ANIMATION_FILE, ANIMATION_MEDIA_TYPE),
    ("animation.mp4", "video/mp4"),
    ("animation.webm", "video/webm"),
    ("animation.gif", "image/gif"),
    ("animation.html", "text/html; charset=utf-8"),
)

NOT_AN_OBJECT_ERROR = "The animation data must be one JSON object."

AnimationWrite = Callable[[list[str] | None], dict[str, Any]]
StageCallback = Callable[[str], None]


class MissingJob(Exception):
    def __init__(self) -> None:
        super().__init__("No animation job with that id.")


class MissingPlayback(Exception):
    def __init__(self) -> None:
        super().__init__("No animation playback for that job.")


@dataclass(frozen=True)
class PlaybackFile:
    """A watchable file written by a ready job (AN-06)."""

    path: Path
    media_type: str


def find_playback(work_dir: Path | str) -> PlaybackFile | None:
    """Return the first known playback file in the job work dir, if any."""

    root = Path(work_dir)
    for name, media_type in PLAYBACK_FILES:
        path = root / name
        if path.is_file():
            return PlaybackFile(path=path.resolve(), media_type=media_type)
    return None


def load_animation(work_dir: Path | str) -> StoredAnimation | None:
    """The stored animation of a ready job, or None for an older format."""

    path = Path(work_dir) / ANIMATION_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if is_lottie_video(data):
        try:
            return LottieVideo.model_validate(data)
        except ValueError:
            return None
    return check_animation(data).animation


@dataclass(frozen=True)
class AnimationAttempt:
    """Outcome of one checked run for a started job.

    ``errors`` are for the writer. ``session_notice`` is set when the job
    stops after the last failure.
    """

    ok: bool
    status: str
    runs: int
    errors: tuple[str, ...] = ()
    session_notice: str | None = None


@dataclass(frozen=True)
class AnimationProduceResult:
    """Outcome of the full produce loop for one job."""

    status: str
    runs: int
    session_notice: str | None = None


def job_payload(
    job_id: str, session_id: str, *, status: str, stage: str | None = None
) -> dict[str, object]:
    """Learner-visible job. A running job also says its stage (AN-19)."""

    payload: dict[str, object] = {
        "id": job_id,
        "kind": "animation",
        "session_id": session_id,
        "status": status,
    }
    if status == RUNNING and stage:
        payload["stage"] = stage
    return payload


def waiting_notice_chunk(
    reply_so_far: str, artifacts: Sequence[Mapping[str, object]]
) -> str:
    """Text to append when this turn started a job that is still running."""

    started = [
        artifact
        for artifact in artifacts
        if artifact.get("kind") == "animation" and artifact.get("status") == RUNNING
    ]
    if not started or reply_so_far.endswith(WAITING_NOTICE):
        return ""
    choosing = any(artifact.get("stage") == CHOOSING for artifact in started)
    notice = CHOOSING_NOTICE if choosing else WAITING_NOTICE
    if reply_so_far and not reply_so_far.endswith("\n"):
        return "\n\n" + notice
    return notice


def submit_animation(
    data: object,
    *,
    job_id: str,
    work_dir: Path | str,
    runs_before: int,
) -> AnimationAttempt:
    """Check writer data once for a started job, and store it when it passes.

    ``runs_before`` is how many runs already happened for this job (0, 1,
    or 2). The job id replaces any id the writer sent. A third refusal
    stops further fixes (AN-05, AN-09).
    """

    if runs_before < 0:
        raise ValueError("runs_before must be zero or greater.")
    if runs_before >= MAX_RUNS:
        return AnimationAttempt(
            ok=False, status=FAILED, runs=runs_before, session_notice=FAILURE_NOTICE
        )

    runs = runs_before + 1
    stored: StoredAnimation | None = None
    if is_lottie_video(data):
        checked_video = check_lottie_video({**data, "id": job_id})
        stored, errors = checked_video.video, checked_video.errors
    elif isinstance(data, dict):
        checked = check_animation({**data, "id": job_id})
        stored, errors = checked.animation, checked.errors
    else:
        errors = [NOT_AN_OBJECT_ERROR]
    if stored is not None:
        path = Path(work_dir) / ANIMATION_FILE
        path.write_text(json.dumps(stored.model_dump(mode="json")), encoding="utf-8")
        return AnimationAttempt(ok=True, status=READY, runs=runs)
    if runs >= MAX_RUNS:
        return AnimationAttempt(
            ok=False,
            status=FAILED,
            runs=runs,
            errors=tuple(errors),
            session_notice=FAILURE_NOTICE,
        )
    return AnimationAttempt(ok=False, status=RUNNING, runs=runs, errors=tuple(errors))


def errors_for_writer(errors: Sequence[str]) -> list[str]:
    """The check errors one fix prompt carries."""

    shown = list(errors[:MAX_ERRORS_TO_WRITER])
    hidden = len(errors) - len(shown)
    if hidden > 0:
        shown.append(f"... and {hidden} more errors.")
    return shown


def produce(
    *,
    job_id: str,
    work_dir: Path | str,
    write_animation: AnimationWrite,
    on_stage: StageCallback | None = None,
) -> AnimationProduceResult:
    """Write, check, and apply at most two fixes (AN-05, AN-09, AN-19).

    ``write_animation`` receives ``None`` on the first run and the check
    errors on each fix. After three refusals the job stops.
    """

    def stage(name: str) -> None:
        if on_stage is not None:
            on_stage(name)

    errors: list[str] | None = None
    runs = 0
    for _ in range(MAX_RUNS):
        stage(WRITING if errors is None else FIXING)
        data = write_animation(errors)
        stage(CHECKING)
        attempt = submit_animation(
            data, job_id=job_id, work_dir=work_dir, runs_before=runs
        )
        runs = attempt.runs
        if attempt.ok:
            return AnimationProduceResult(status=READY, runs=runs)
        if attempt.status == FAILED:
            break
        errors = errors_for_writer(attempt.errors)
    return AnimationProduceResult(
        status=FAILED, runs=runs, session_notice=FAILURE_NOTICE
    )
