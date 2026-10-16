"""Animation jobs. The job id is stored before the animation is ready.

After a job starts, agent-written code runs in the sandbox (AN-04). On
failure the error goes back to the agent; at most two fixes, three runs
in total (AN-05). After that the job fails and the session is told to
try later (AN-09). A ready job keeps a playback file under the work dir
so the learner can open the animation again (AN-06).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from polaris.sandbox import SandboxResult, run as sandbox_run

RUNNING = "running"
READY = "ready"
FAILED = "failed"

# Original run plus this many fixes (AN-05).
MAX_FIX_ATTEMPTS = 2
MAX_RUNS = 1 + MAX_FIX_ATTEMPTS

WAITING_NOTICE = (
    "This animation may take some time. "
    "You can keep talking in this session or another. "
    "The operating system will notify you when it is ready."
)

FAILURE_NOTICE = (
    "Polaris cannot create the animation right now. Try later."
)

# Sandbox work dir playback names, first match wins (AN-06).
PLAYBACK_FILES: tuple[tuple[str, str], ...] = (
    ("animation.mp4", "video/mp4"),
    ("animation.webm", "video/webm"),
    ("animation.gif", "image/gif"),
    ("animation.html", "text/html; charset=utf-8"),
)

MISSING_PLAYBACK_ERROR = (
    "The run finished, but it did not write a playback file. "
    "Write animation.html, animation.mp4, animation.webm, or "
    "animation.gif in the working directory."
)

SandboxRun = Callable[..., SandboxResult]
CodeWriter = Callable[[str | None], str]


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


@dataclass(frozen=True)
class AnimationAttempt:
    """Outcome of one sandbox submission for a started job.

    ``error`` is for the agent. It never includes the submitted code.
    ``session_notice`` is set when the job stops after the last failure.
    """

    ok: bool
    status: str
    runs: int
    error: str | None = None
    session_notice: str | None = None


@dataclass(frozen=True)
class AnimationProduceResult:
    """Outcome of the full produce loop for one job."""

    status: str
    runs: int
    session_notice: str | None = None


def job_payload(job_id: str, session_id: str, *, status: str) -> dict[str, object]:
    """Learner-visible job. Never includes animation code."""

    return {
        "id": job_id,
        "kind": "animation",
        "session_id": session_id,
        "status": status,
    }


def waiting_notice_chunk(
    reply_so_far: str, artifacts: Sequence[Mapping[str, object]]
) -> str:
    """Text to append when this turn started a job that is still running."""

    started = any(
        artifact.get("kind") == "animation" and artifact.get("status") == RUNNING
        for artifact in artifacts
    )
    if not started or reply_so_far.endswith(WAITING_NOTICE):
        return ""
    if reply_so_far and not reply_so_far.endswith("\n"):
        return "\n\n" + WAITING_NOTICE
    return WAITING_NOTICE


def submit_code(
    code: str,
    *,
    work_dir: Path | str,
    runs_before: int,
    run_sandbox: SandboxRun | None = None,
) -> AnimationAttempt:
    """Run agent-written code once for a started job.

    ``runs_before`` is how many sandbox runs already happened for this job
    (0, 1, or 2). A third failure stops further fixes (AN-05, AN-09).
    The result never includes the submitted code.
    """

    if runs_before < 0:
        raise ValueError("runs_before must be zero or greater.")
    if runs_before >= MAX_RUNS:
        return AnimationAttempt(
            ok=False,
            status=FAILED,
            runs=runs_before,
            error=None,
            session_notice=FAILURE_NOTICE,
        )

    runner = run_sandbox if run_sandbox is not None else sandbox_run
    result = runner(code, work_dir=work_dir)
    runs = runs_before + 1
    if result.ok and find_playback(work_dir) is not None:
        return AnimationAttempt(
            ok=True,
            status=READY,
            runs=runs,
            error=None,
            session_notice=None,
        )
    error = result.error if not result.ok else MISSING_PLAYBACK_ERROR
    if runs >= MAX_RUNS:
        return AnimationAttempt(
            ok=False,
            status=FAILED,
            runs=runs,
            error=error,
            session_notice=FAILURE_NOTICE,
        )
    return AnimationAttempt(
        ok=False,
        status=RUNNING,
        runs=runs,
        error=error,
        session_notice=None,
    )


def produce(
    *,
    work_dir: Path | str,
    write_code: CodeWriter,
    run_sandbox: SandboxRun | None = None,
) -> AnimationProduceResult:
    """Write code, run it, and apply at most two fixes (AN-05, AN-09).

    ``write_code`` receives ``None`` on the first run and the sandbox error
    text on each fix. After three failures the job stops.
    """

    error: str | None = None
    runs = 0
    for _ in range(MAX_RUNS):
        code = write_code(error)
        attempt = submit_code(
            code,
            work_dir=work_dir,
            runs_before=runs,
            run_sandbox=run_sandbox,
        )
        runs = attempt.runs
        if attempt.ok:
            return AnimationProduceResult(status=READY, runs=runs)
        error = attempt.error
        if attempt.status == FAILED:
            return AnimationProduceResult(
                status=FAILED,
                runs=runs,
                session_notice=FAILURE_NOTICE,
            )
    return AnimationProduceResult(
        status=FAILED,
        runs=runs,
        session_notice=FAILURE_NOTICE,
    )
