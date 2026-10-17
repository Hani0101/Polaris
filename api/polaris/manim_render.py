"""Render a Manim scene written by the animation writer (experiment).

This is the ``feat/manim-experiment`` path. The writer returns Manim code;
this module checks it, runs it in a child process
(``manim_assets/manim_child.py``), and collects the result. It goes against
AN-04 and decision 0006 on purpose, to find out what Manim can do.

Two qualities: ``preview`` (640x480, 15 fps) for the writer's own checks
and the fix loop, and ``final`` (1440x1080, 60 fps) for what the learner
watches. The frame is 4:3, like the Polaris animation canvas.

The child runs with ``python -I``, a stripped environment, a time limit,
and an audit hook. That is not a sandbox; see the child's docstring.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "manim_assets"
CHILD = ASSETS / "manim_child.py"

PREVIEW = "preview"
FINAL = "final"
TIME_LIMITS = {PREVIEW: 120.0, FINAL: 600.0}
MAX_CODE_CHARS = 30_000

ALLOWED_IMPORTS = frozenset(
    {"manim", "polaris_manim", "math", "numpy", "random", "itertools", "functools"}
)
DENIED_NAMES = frozenset(
    {
        "exec",
        "eval",
        "compile",
        "open",
        "__import__",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "breakpoint",
        "input",
    }
)


@dataclass(frozen=True)
class RenderedStep:
    caption: str
    video: Path | None
    duration_s: float


@dataclass(frozen=True)
class RenderResult:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    steps: tuple[RenderedStep, ...] = ()
    video: Path | None = None
    frames: tuple[Path, ...] = ()
    # Pictures after each animation of a step, by step number (preview only).
    keyframes: dict[int, tuple[Path, ...]] = field(default_factory=dict)
    duration_s: float = 0.0
    timings: dict[str, float] = field(default_factory=dict)


def check_code(code: str) -> list[str]:
    """Static checks before anything runs. Not a security boundary."""

    if not code.strip():
        return ["The code is empty."]
    if len(code) > MAX_CODE_CHARS:
        return [f"The code is {len(code)} characters; keep it under {MAX_CODE_CHARS}."]
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return [f"SyntaxError at line {error.lineno}: {error.msg}"]
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    errors.append(f"Line {node.lineno}: import {alias.name} is not allowed.")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in ALLOWED_IMPORTS:
                errors.append(f"Line {node.lineno}: from {node.module} import is not allowed.")
        elif isinstance(node, ast.Name) and node.id in DENIED_NAMES:
            errors.append(f"Line {node.lineno}: {node.id} is not allowed.")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            errors.append(f"Line {node.lineno}: dunder attribute {node.attr} is not allowed.")
    allowed = ", ".join(sorted(ALLOWED_IMPORTS))
    if any("is not allowed" in error and "import" in error for error in errors):
        errors.append(f"Only these modules can be imported: {allowed}.")
    return errors


def render(code: str, out_dir: Path, *, quality: str = PREVIEW) -> RenderResult:
    """Check and render ``code`` into ``out_dir``. Never raises for bad code."""

    errors = check_code(code)
    if errors:
        return RenderResult(ok=False, errors=tuple(errors))
    out_dir = out_dir.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    scene_path = out_dir / "scene.py"
    scene_path.write_text(code, encoding="utf-8")
    request_path = out_dir / "request.json"
    request_path.write_text(
        json.dumps(
            {"scene_path": str(scene_path), "out_dir": str(out_dir), "quality": quality}
        ),
        encoding="utf-8",
    )
    started = time.monotonic()
    limit = TIME_LIMITS[quality]
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(CHILD), str(request_path)],
            cwd=out_dir,
            env=_child_env(out_dir),
            capture_output=True,
            text=True,
            timeout=limit,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RenderResult(
            ok=False,
            errors=(
                f"Rendering took longer than {limit:.0f} seconds. "
                "Use fewer objects, shorter run_time, or fewer always_redraw updaters.",
            ),
        )
    report_path = out_dir / "report.json"
    if not report_path.is_file():
        tail = (completed.stderr or "").strip().splitlines()[-5:]
        return RenderResult(
            ok=False,
            errors=("The renderer stopped without a report. " + " | ".join(tail),),
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    timings = dict(report.get("timings", {}))
    timings["wall_s"] = round(time.monotonic() - started, 2)
    steps = tuple(
        RenderedStep(
            caption=step["caption"],
            video=Path(step["video"]) if step.get("video") else None,
            duration_s=float(step.get("duration_s", 0.0)),
        )
        for step in report.get("steps", [])
    )
    keyframes: dict[int, list[Path]] = {}
    for key in report.get("keyframes", []):
        keyframes.setdefault(int(key["step"]), []).append(Path(key["path"]))
    return RenderResult(
        ok=bool(report.get("ok")),
        keyframes={step: tuple(paths) for step, paths in keyframes.items()},
        errors=tuple(report.get("errors", [])),
        warnings=tuple(report.get("warnings", [])),
        steps=steps,
        video=Path(report["video"]) if report.get("video") else None,
        frames=tuple(Path(frame["path"]) for frame in report.get("frames", [])),
        duration_s=float(report.get("duration_s", 0.0)),
        timings=timings,
    )


def _child_env(out_dir: Path) -> dict[str, str]:
    keep = ("PATH", "SYSTEMROOT", "WINDIR", "LANG", "LC_ALL", "FONTCONFIG_PATH", "FONTCONFIG_FILE")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    temp = out_dir / "tmp"
    temp.mkdir(exist_ok=True)
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = str(temp)
    env["HOME"] = env["USERPROFILE"] = str(out_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def scratch_dir(prefix: str = "polaris-manim-") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))
