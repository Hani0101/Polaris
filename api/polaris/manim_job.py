"""Animation jobs made with Manim (experiment, ``feat/manim-experiment``).

The same job rules as ``polaris.animation``: the writer drafts, Polaris
checks, at most two fixes (AN-05, AN-09), and the stage is kept on the job
(AN-19). The check here is the final render itself: it runs the layout
checks after every animation, so a draft that renders is a draft that
passed.

A ready job keeps, in its work dir:

- ``animation.mp4``: the whole video, which the media route serves.
- ``steps/step-NN.mp4`` and ``posters/step-NN.png``: one clip and its last
  frame per step, for the step player and reduced motion (AN-12, AN-13).
- ``captions.vtt``: one cue per step with its caption (AN-15).
- ``manim.json``: the title, the description, and each step's caption and
  time range. A later turn reads it (AN-16, AN-17).
- ``source/scene.py``: the code, kept for the experiment. Never served.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from polaris.animation import (
    CHECKING,
    FAILED,
    FAILURE_NOTICE,
    FIXING,
    MAX_RUNS,
    READY,
    WRITING,
    AnimationProduceResult,
    StageCallback,
    errors_for_writer,
)
from polaris.animation_format import Animation, Step
from polaris.manim_render import FINAL, RenderResult, render

MANIFEST_FILE = "manim.json"
CAPTIONS_FILE = "captions.vtt"
VIDEO_FILE = "animation.mp4"


@dataclass(frozen=True)
class ManimDraftData:
    title: str
    description: str
    code: str


# Receives (failed code, errors) on a fix and (None, None) on the first run.
DraftWrite = Callable[[str | None, list[str] | None], ManimDraftData]
Renderer = Callable[..., RenderResult]


def produce_manim(
    *,
    job_id: str,
    work_dir: Path | str,
    write_draft: DraftWrite,
    on_stage: StageCallback | None = None,
    renderer: Renderer = render,
    output: tuple[int, int, int] | None = None,
) -> AnimationProduceResult:
    """Write, render, and apply at most two fixes.

    ``output`` is the final render's pixel width, height, and frames per
    second, from the learner's settings (AN-26). None keeps the default.
    """

    root = Path(work_dir)

    def stage(name: str) -> None:
        if on_stage is not None:
            on_stage(name)

    failed_code: str | None = None
    errors: list[str] | None = None
    runs = 0
    for _ in range(MAX_RUNS):
        stage(WRITING if errors is None else FIXING)
        runs += 1
        try:
            draft = write_draft(failed_code, errors)
        except Exception as error:  # noqa: BLE001 - a writer failure is a failed run
            errors = [f"The writer failed: {error}"]
            continue
        stage(CHECKING)
        result = renderer(draft.code, root / "render", quality=FINAL, output=output)
        if result.ok and result.video is not None:
            store_render(root, job_id, draft, result)
            return AnimationProduceResult(status=READY, runs=runs)
        failed_code = draft.code
        errors = errors_for_writer(list(result.errors) or ["The render made no video."])
    return AnimationProduceResult(status=FAILED, runs=runs, session_notice=FAILURE_NOTICE)


def store_render(root: Path, job_id: str, draft: ManimDraftData, result: RenderResult) -> None:
    """Keep the video, the step clips, posters, captions, and the manifest."""

    assert result.video is not None
    shutil.copy(result.video, root / VIDEO_FILE)
    steps_dir = root / "steps"
    posters_dir = root / "posters"
    for folder in (steps_dir, posters_dir):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
    steps = []
    start = 0.0
    for index, step in enumerate(result.steps, start=1):
        name = f"step-{index:02d}"
        if step.video is not None and step.video.is_file():
            shutil.copy(step.video, steps_dir / f"{name}.mp4")
            _last_frame(step.video, posters_dir / f"{name}.png")
        steps.append(
            {
                "id": f"step-{index}",
                "caption": step.caption,
                "start_s": round(start, 3),
                "duration_s": step.duration_s,
            }
        )
        start += step.duration_s
    manifest = {
        "engine": "manim",
        "id": job_id,
        "title": draft.title,
        "description": draft.description,
        "duration_s": round(start, 3),
        "steps": steps,
    }
    (root / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / CAPTIONS_FILE).write_text(captions_vtt(steps), encoding="utf-8")
    source = root / "source"
    source.mkdir(exist_ok=True)
    (source / "scene.py").write_text(draft.code, encoding="utf-8")
    shutil.rmtree(root / "render", ignore_errors=True)


def captions_vtt(steps: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for index, step in enumerate(steps, start=1):
        begin = step["start_s"]
        end = begin + step["duration_s"]
        lines += [
            f"step-{index}",
            f"{_vtt_time(begin)} --> {_vtt_time(end)}",
            step["caption"],
            "",
        ]
    return "\n".join(lines)


def _vtt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _last_frame(video: Path, out: Path) -> None:
    import av

    last = None
    with av.open(str(video)) as container:
        for frame in container.decode(video=0):
            last = frame
    if last is not None:
        last.to_image().save(out)


def load_manifest(work_dir: Path | str) -> dict | None:
    path = Path(work_dir) / MANIFEST_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def manifest_animation(work_dir: Path | str) -> Animation | None:
    """A Manim job as an Animation with captioned steps and no elements.

    Built without validation so the teaching prompt can describe it and the
    learner can ask about a step (AN-16, AN-17). The player never reads it.
    """

    manifest = load_manifest(work_dir)
    if manifest is None:
        return None
    steps = [
        Step.model_construct(
            id=str(step["id"]),
            caption=str(step["caption"]),
            duration_ms=int(float(step.get("duration_s", 0)) * 1000),
            actions=[],
        )
        for step in manifest.get("steps", [])
    ]
    return Animation.model_construct(
        version=1,
        id=str(manifest["id"]),
        title=str(manifest.get("title", "Animation")),
        description=str(manifest.get("description", "")),
        elements=[],
        steps=steps,
    )
