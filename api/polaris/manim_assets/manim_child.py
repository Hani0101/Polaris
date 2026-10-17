"""Runs one Manim scene in its own process and writes ``report.json``.

Started by ``polaris.manim_render`` as ``python -I manim_child.py
request.json``. It imports nothing from Polaris. The request names the
scene file, the output folder, and the quality.

While the scene plays, every animation is followed by a layout check:
something outside the frame, two pieces of text overlapping, or text too
small for a phone screen. A preview also keeps a picture of the end of
each step, for the writer to look at.

The audit hook below denies sockets, starting programs, and writing
outside the output folder. Audit hooks are not a sandbox (PEP 578): native
code loaded by the scene can get past them. This is an experiment.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

QUALITIES = {
    # name: (pixel width, pixel height, frames per second)
    "preview": (640, 480, 15),
    "final": (1440, 1080, 60),
}
FRAME_HEIGHT = 8.0
FRAME_WIDTH = FRAME_HEIGHT * 4 / 3

# Everything visible stays inside the frame by more than this.
EDGE_TOLERANCE = 0.02
# Overlap of two text boxes, as a share of the smaller box, that counts.
OVERLAP_SHARE = 0.04
MIN_FONT_SIZE = 32
MAX_STEPS = 10
MAX_CAPTION = 140
MAX_SECONDS = 150.0
MAX_ISSUES = 25

TEXT_CLASSES = frozenset(
    {
        "Text",
        "MarkupText",
        "Paragraph",
        "MathTex",
        "Tex",
        "SingleStringMathTex",
        "Typst",
        "MathTypst",
        "DecimalNumber",
        "Integer",
        "Variable",
        "Code",
        "Title",
        "BulletedList",
    }
)
# Classes that are meant to run past the frame edges.
EDGE_EXEMPT = frozenset({"NumberPlane", "ComplexPlane", "FullScreenRectangle", "ScreenRectangle"})
# Mobjects that hold values and are never drawn.
NOT_DRAWN = frozenset({"ValueTracker", "ComplexValueTracker"})


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(request["out_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "ok": False,
        "errors": [],
        "steps": [],
        "frames": [],
        "keyframes": [],
        "timings": {},
    }
    started = time.monotonic()
    try:
        _run(request, out_dir, report)
    except _SceneError as error:
        report["errors"].append(str(error))
    except BaseException as error:  # noqa: BLE001 - every failure goes back to the writer
        report["errors"].append(_describe_exception(error, request["scene_path"]))
    report["timings"]["total_s"] = round(time.monotonic() - started, 2)
    report["ok"] = not report["errors"]
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


class _SceneError(Exception):
    pass


def _no_latex(*args, **kwargs):
    raise _SceneError(
        "LaTeX is not installed, so MathTex, Tex, and get_axis_labels with "
        "MathTex do not work. Use MathTypst(...) for maths and Text(...) for words."
    )


def _run(request: dict, out_dir: Path, report: dict) -> None:
    import logging
    import warnings

    warnings.filterwarnings("ignore")
    import_started = time.monotonic()
    import manimpango
    import numpy as np
    import manim.mobject.text.tex_mobject as tex_mobject
    from manim import (
        Code,
        DecimalNumber,
        MarkupText,
        NumberLine,
        Paragraph,
        Text,
        config,
        logger,
    )
    from PIL import Image

    logger.setLevel(logging.ERROR)
    fonts = HERE / "fonts"
    for font in sorted(fonts.glob("*.ttf")):
        manimpango.register_font(str(font))

    import polaris_manim

    width, height, fps = QUALITIES[request["quality"]]
    preview = request["quality"] == "preview"
    config.pixel_width = width
    config.pixel_height = height
    config.frame_rate = fps
    config.frame_height = FRAME_HEIGHT
    config.frame_width = FRAME_WIDTH
    config.background_color = polaris_manim.BACKGROUND
    config.media_dir = str(out_dir / "media")
    config.save_sections = True
    config.disable_caching = True
    config.progress_bar = "none"
    config.verbosity = "ERROR"
    config.output_file = "animation"
    config.write_to_movie = True
    for text_class in (Text, MarkupText, Paragraph):
        text_class.set_default(font=polaris_manim.BODY_FONT)
    Code.set_default(paragraph_config={"font": polaris_manim.MONO_FONT, "font_size": 32})
    # No LaTeX on the learner's machine: numbers and axis labels use Text,
    # and maths uses MathTypst.
    DecimalNumber.set_default(mob_class=Text)
    NumberLine.set_default(label_constructor=Text)
    tex_mobject.tex_to_svg_file = _no_latex
    report["timings"]["import_s"] = round(time.monotonic() - import_started, 2)

    scene_path = Path(request["scene_path"]).resolve()
    source = scene_path.read_text(encoding="utf-8")
    _install_audit_hook(out_dir)

    namespace: dict = {"__name__": "__polaris_scene__", "__file__": str(scene_path)}
    exec(compile(source, str(scene_path), "exec"), namespace)
    scenes = [
        value
        for value in namespace.values()
        if isinstance(value, type)
        and issubclass(value, polaris_manim.PolarisScene)
        and value is not polaris_manim.PolarisScene
        and getattr(value, "__module__", "") == "__polaris_scene__"
    ]
    if len(scenes) != 1:
        raise _SceneError(
            f"The code must define exactly one subclass of PolarisScene; found {len(scenes)}."
        )

    issues: list[str] = []
    seen_issues: set[str] = set()
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    probe = _Probe(np, scene_path, issues, seen_issues)

    scene_class = scenes[0]

    class Probed(scene_class):  # type: ignore[misc, valid-type]
        def _on_step(self, caption: str) -> None:
            if not isinstance(caption, str) or not caption.strip():
                raise _SceneError("Every step needs a caption: self.step(\"...\").")
            if len(caption) > MAX_CAPTION:
                raise _SceneError(
                    f"Step {len(self.captions) + 1} caption is {len(caption)} characters; "
                    f"keep it under {MAX_CAPTION}."
                )
            if self.captions and preview:
                _save_frame(self, Image, frames_dir, len(self.captions), report)
            self._polaris_step_time = self.time

        def _before_animation(self) -> None:
            if not self.captions:
                raise _SceneError(
                    "An animation ran before the first self.step(...). Start with a step."
                )

        def _after_animation(self) -> None:
            probe.check(self, len(self.captions), self.captions[-1])
            if preview:
                _save_keyframe(self, Image, frames_dir, len(self.captions), report)

    Probed.__name__ = scene_class.__name__
    scene = Probed()
    render_started = time.monotonic()
    scene.render()
    report["timings"]["render_s"] = round(time.monotonic() - render_started, 2)

    captions = scene.captions
    if not captions:
        raise _SceneError("The scene has no steps. Call self.step(caption) before each part.")
    if len(captions) > MAX_STEPS:
        issues.append(f"The scene has {len(captions)} steps; use at most {MAX_STEPS}.")
    if scene.time > MAX_SECONDS:
        issues.append(
            f"The scene runs {scene.time:.0f} seconds; keep it under {MAX_SECONDS:.0f}."
        )
    if preview:
        _save_frame(scene, Image, frames_dir, len(captions), report)

    sections = [
        section
        for section in scene.renderer.file_writer.sections
        if section.video is not None
    ]
    sections_dir = Path(scene.renderer.file_writer.sections_output_dir)
    if len(sections) != len(captions):
        issues.append(
            f"{len(captions)} steps made {len(sections)} clips. "
            "Every step needs at least one self.play(...) or self.wait(...)."
        )
    for index, caption in enumerate(captions):
        entry: dict = {"caption": caption}
        if index < len(sections):
            entry["video"] = str(sections_dir / sections[index].video)
            entry["duration_s"] = round(_section_seconds(sections[index], fps), 3)
            if entry["duration_s"] < 0.5:
                issues.append(f"Step {index + 1} lasts under half a second.")
        report["steps"].append(entry)
    movie = Path(scene.renderer.file_writer.movie_file_path)
    report["video"] = str(movie)
    report["duration_s"] = round(scene.time, 3)
    report["errors"].extend(issues[:MAX_ISSUES])
    if len(issues) > MAX_ISSUES:
        report["errors"].append(f"... and {len(issues) - MAX_ISSUES} more layout problems.")


def _section_seconds(section, fps: int) -> float:
    total = 0.0
    for partial in section.partial_movie_files:
        if partial is None:
            continue
        try:
            import av

            with av.open(partial) as container:
                stream = container.streams.video[0]
                if stream.frames:
                    total += stream.frames / fps
                elif container.duration:
                    total += container.duration / 1_000_000
        except Exception:  # noqa: BLE001
            continue
    return total


def _save_frame(scene, image_module, frames_dir: Path, step_number: int, report: dict) -> None:
    frame = scene.renderer.get_frame()
    path = frames_dir / f"step-{step_number:02d}.png"
    image_module.fromarray(frame).convert("RGB").save(path)
    report["frames"].append({"step": step_number, "path": str(path)})


def _save_keyframe(scene, image_module, frames_dir: Path, step_number: int, report: dict) -> None:
    index = sum(1 for key in report["keyframes"] if key["step"] == step_number) + 1
    path = frames_dir / f"step-{step_number:02d}-key-{index:02d}.png"
    image_module.fromarray(scene.renderer.get_frame()).convert("RGB").save(path)
    report["keyframes"].append({"step": step_number, "path": str(path)})


def _install_audit_hook(out_dir: Path) -> None:
    allowed = tuple(Path(path).resolve() for path in (out_dir, tempfile.gettempdir(), os.devnull))
    denied_events = {
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.spawn",
        "os.posix_spawn",
        "os.startfile",
        "os.fork",
        "os.forkpty",
        "pty.spawn",
        "_winapi.CreateProcess",
        "_posixsubprocess.fork_exec",
    }

    def audit(event: str, args: tuple) -> None:
        if event.startswith("socket.") and event != "socket.gethostname":
            raise PermissionError("Animation code has no network.")
        if event in denied_events:
            raise PermissionError("Animation code cannot start other programs.")
        if event == "open" and len(args) >= 2:
            path, mode = args[0], args[1]
            writing = isinstance(mode, str) and any(flag in mode for flag in "wax+")
            if not writing and isinstance(args[-1], int):
                writing = bool(args[-1] & 0o3)  # os.open flags: O_WRONLY or O_RDWR
            if writing and isinstance(path, str | bytes):
                text = path.decode() if isinstance(path, bytes) else path
                resolved = Path(text).resolve()
                if not any(resolved == root or resolved.is_relative_to(root) for root in allowed):
                    raise PermissionError(f"Animation code can only write its own output, not {text}.")
        if event == "object.__setattr__" and len(args) >= 2 and args[1] == "__code__":
            raise PermissionError("Animation code cannot replace function code.")

    sys.addaudithook(audit)


def _describe_exception(error: BaseException, scene_path: str) -> str:
    frames = traceback.extract_tb(error.__traceback__)
    scene_frames = [frame for frame in frames if frame.filename == str(Path(scene_path).resolve())]
    where = ""
    if scene_frames:
        frame = scene_frames[-1]
        where = f" at line {frame.lineno}: {(frame.line or '').strip()}"
    tail = frames[-1] if frames else None
    inside = ""
    if tail is not None and scene_frames and tail is not scene_frames[-1]:
        inside = f" (raised inside {Path(tail.filename).name}, {tail.name})"
    message = str(error).strip() or type(error).__name__
    if len(message) > 600:
        message = message[:600] + "..."
    return f"{type(error).__name__}{where}{inside}: {message}"


class _Probe:
    """Layout checks after each animation."""

    def __init__(self, np, scene_path: Path, issues: list[str], seen: set[str]) -> None:
        self.np = np
        self.scene_path = str(scene_path)
        self.issues = issues
        self.seen = seen

    def check(self, scene, step_number: int, caption: str) -> None:
        if len(self.issues) > MAX_ISSUES:
            return
        line = self._calling_line()
        where = f"step {step_number} (\"{_short(caption, 50)}\"), after the animation at line {line}"
        half_w = scene.camera.frame_width / 2 if hasattr(scene.camera, "frame_width") else FRAME_WIDTH / 2
        half_h = scene.camera.frame_height / 2 if hasattr(scene.camera, "frame_height") else FRAME_HEIGHT / 2
        center = self._camera_center(scene)
        texts: list[tuple[str, tuple[float, float, float, float]]] = []
        for mobject in scene.mobjects:
            self._walk(mobject, texts, center, half_w, half_h, where)
        for index, (name_a, box_a) in enumerate(texts):
            for name_b, box_b in texts[index + 1 :]:
                share = _overlap_share(box_a, box_b)
                if share > OVERLAP_SHARE:
                    self._add(f"In {where}: text {name_a} overlaps text {name_b}.")

    def _walk(self, mobject, texts, center, half_w, half_h, where) -> None:
        name = type(mobject).__name__
        if name in NOT_DRAWN:
            return
        box = self._visible_box(mobject)
        if box is None:
            return
        if name not in EDGE_EXEMPT and not self._covers_frame(box, center, half_w, half_h):
            sides = []
            if box[0] < center[0] - half_w - EDGE_TOLERANCE:
                sides.append("left")
            if box[2] > center[0] + half_w + EDGE_TOLERANCE:
                sides.append("right")
            if box[1] < center[1] - half_h - EDGE_TOLERANCE:
                sides.append("bottom")
            if box[3] > center[1] + half_h + EDGE_TOLERANCE:
                sides.append("top")
            if sides and not mobject.submobjects:
                self._add(
                    f"In {where}: {self._name(mobject)} goes past the {' and '.join(sides)} "
                    "edge of the frame."
                )
            elif sides and _is_text(mobject):
                self._add(
                    f"In {where}: {self._name(mobject)} goes past the {' and '.join(sides)} "
                    "edge of the frame."
                )
                return
        if name in EDGE_EXEMPT:
            return
        if _is_text(mobject):
            texts.append((self._name(mobject), box))
            size = _font_size(mobject)
            if size is not None and size < MIN_FONT_SIZE - 0.5:
                self._add(
                    f"In {where}: {self._name(mobject)} is font size {size:.0f}; "
                    f"use at least {MIN_FONT_SIZE} so it reads on a phone."
                )
            return
        for child in mobject.submobjects:
            self._walk(child, texts, center, half_w, half_h, where)

    def _visible_box(self, mobject):
        np = self.np
        points = []
        for member in mobject.get_family():
            data = getattr(member, "points", None)
            if data is None or len(data) == 0:
                continue
            if not _member_visible(member, np):
                continue
            points.append(data)
        if not points:
            return None
        stacked = np.concatenate(points)
        low = stacked.min(axis=0)
        high = stacked.max(axis=0)
        return (float(low[0]), float(low[1]), float(high[0]), float(high[1]))

    def _covers_frame(self, box, center, half_w, half_h) -> bool:
        # A background that covers the whole frame is meant to run past it.
        return (
            box[0] <= center[0] - half_w
            and box[2] >= center[0] + half_w
            and box[1] <= center[1] - half_h
            and box[3] >= center[1] + half_h
        )

    def _camera_center(self, scene):
        frame = getattr(scene.camera, "frame", None)
        if frame is not None:
            point = frame.get_center()
            return (float(point[0]), float(point[1]))
        return (0.0, 0.0)

    def _calling_line(self) -> str:
        for frame in reversed(traceback.extract_stack()):
            if frame.filename == self.scene_path:
                return str(frame.lineno)
        return "?"

    def _name(self, mobject) -> str:
        name = type(mobject).__name__
        for attribute in ("original_text", "text", "tex_string", "typst_code", "code_string"):
            value = getattr(mobject, attribute, None)
            if isinstance(value, str) and value.strip():
                return f"{name} '{_short(value, 40)}'"
        number = getattr(mobject, "number", None)
        if number is not None:
            return f"{name} {number}"
        return name

    def _add(self, issue: str) -> None:
        if issue in self.seen:
            return
        self.seen.add(issue)
        self.issues.append(issue)


def _member_visible(member, np) -> bool:
    try:
        fill = member.get_fill_opacities()
        stroke = member.get_stroke_opacities()
    except Exception:  # noqa: BLE001 - not a VMobject
        return True
    fill_max = float(np.max(fill)) if len(fill) else 0.0
    stroke_max = float(np.max(stroke)) if len(stroke) else 0.0
    stroke_width = getattr(member, "stroke_width", 1) or 0
    return fill_max > 0.05 or (stroke_max > 0.05 and stroke_width > 0)


def _is_text(mobject) -> bool:
    return any(cls.__name__ in TEXT_CLASSES for cls in type(mobject).__mro__)


def _font_size(mobject) -> float | None:
    try:
        size = getattr(mobject, "font_size", None)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(size, int | float) and size > 0:
        return float(size)
    return None


def _overlap_share(a, b) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    if smaller <= 0:
        return 0.0
    return (width * height) / smaller


def _short(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


if __name__ == "__main__":
    sys.exit(main())
