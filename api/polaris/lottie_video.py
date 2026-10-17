"""Lottie videos: an animation made of Lottie scenes played one after another.

Experiment (branch feat/lottie-experiment). Each scene is one Lottie
document and one step of the animation, with a caption. Polaris's player
plays the scenes in order with lottie-web, and the learner can pause, go
back, go to the next scene, and replay one.

``check_lottie_video`` refuses data that lottie-web cannot play safely:
expressions (lottie-web evaluates them as JavaScript), external images and
fonts, and documents that are missing the keys a player needs. With a
renderer available it also draws frames of every scene in headless Chromium
and refuses scenes that throw or draw nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

FORMAT = "lottie"

WIDTH = 800
HEIGHT = 600
BACKGROUND = "#faf8f4"
MIN_TEXT_SIZE = 30
MAX_SCENES = 12
MIN_SCENE_SECONDS = 1.5
MAX_SCENE_SECONDS = 20.0
MAX_CAPTION_LENGTH = 160
MAX_SCENE_BYTES = 1_500_000
FONT_FAMILIES = ("Atkinson Hyperlegible Next", "Atkinson Hyperlegible Mono")

# Below this share of non-background pixels a frame counts as blank.
MIN_INK = 0.004

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_SCRIPT = REPO_ROOT / "scripts" / "render-lottie.mjs"


class LottieScene(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    caption: str = Field(min_length=1)
    lottie: dict[str, Any]


class LottieVideo(BaseModel):
    format: str = FORMAT
    version: int = 1
    id: str = ""
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    # The writer may pick any background; the player paints it behind every scene.
    background: str = Field(default=BACKGROUND, pattern=r"^#[0-9a-fA-F]{6}$")
    scenes: list[LottieScene] = Field(min_length=1)

    @property
    def steps(self) -> list[LottieScene]:
        """The scenes, under the name the rest of Polaris uses for steps."""

        return self.scenes


@dataclass
class CheckedVideo:
    video: LottieVideo | None
    errors: list[str] = field(default_factory=list)


def is_lottie_video(data: object) -> bool:
    return isinstance(data, dict) and data.get("format") == FORMAT


def scene_seconds(lottie: dict[str, Any]) -> float:
    try:
        return (float(lottie["op"]) - float(lottie["ip"])) / float(lottie["fr"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _walk(node: Any, path: str):
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")


def check_scene(scene_id: str, lottie: object) -> list[str]:
    """Structural checks for one Lottie document. Errors name the scene."""

    where = f"scene '{scene_id}'"
    if not isinstance(lottie, dict):
        return [f"{where}: the Lottie data must be one JSON object."]
    errors: list[str] = []
    size = len(json.dumps(lottie))
    if size > MAX_SCENE_BYTES:
        errors.append(f"{where}: {size} bytes is over the {MAX_SCENE_BYTES} byte limit.")
    for key in ("v", "fr", "ip", "op", "w", "h", "layers"):
        if key not in lottie:
            errors.append(f"{where}: missing top-level key '{key}'.")
    if errors:
        return errors
    if lottie["w"] != WIDTH or lottie["h"] != HEIGHT:
        errors.append(f"{where}: w and h must be {WIDTH} and {HEIGHT}.")
    if not isinstance(lottie["fr"], (int, float)) or not 12 <= lottie["fr"] <= 60:
        errors.append(f"{where}: fr must be between 12 and 60.")
    seconds = scene_seconds(lottie)
    if not MIN_SCENE_SECONDS <= seconds <= MAX_SCENE_SECONDS:
        errors.append(
            f"{where}: lasts {seconds:.2f}s; a scene lasts "
            f"{MIN_SCENE_SECONDS:g} to {MAX_SCENE_SECONDS:g} seconds."
        )
    if not isinstance(lottie["layers"], list) or not lottie["layers"]:
        errors.append(f"{where}: needs at least one layer.")

    for path, node in _walk(lottie, "$"):
        expression = node.get("x")
        if isinstance(expression, str):
            errors.append(f"{where}: expressions are not allowed ({path}.x). Bake keyframes.")
        if node.get("ty") == 2 or (isinstance(node.get("p"), str) and "layers" not in node):
            errors.append(f"{where}: image layers and image assets are not allowed ({path}).")
        if isinstance(node.get("u"), str) and node["u"]:
            errors.append(f"{where}: external files are not allowed ({path}.u).")
    fonts = lottie.get("fonts", {}).get("list", []) if isinstance(lottie.get("fonts"), dict) else []
    for index, font in enumerate(fonts if isinstance(fonts, list) else []):
        if not isinstance(font, dict):
            continue
        if font.get("fFamily") not in FONT_FAMILIES:
            errors.append(
                f"{where}: font {index} must use fFamily "
                + " or ".join(f"'{name}'" for name in FONT_FAMILIES)
                + "."
            )
        if font.get("fPath"):
            errors.append(f"{where}: font {index} must not load a file (fPath).")
    for path, node in _walk(lottie.get("layers", []), "layers"):
        if node.get("ty") == 5:
            for keyframe in node.get("t", {}).get("d", {}).get("k", []) or []:
                document = keyframe.get("s", {}) if isinstance(keyframe, dict) else {}
                text_size = document.get("s")
                if isinstance(text_size, (int, float)) and text_size < MIN_TEXT_SIZE:
                    errors.append(
                        f"{where}: text '{str(document.get('t', ''))[:30]}' is size "
                        f"{text_size:g}; text is at least {MIN_TEXT_SIZE}."
                    )
    return errors


def check_lottie_video(data: object, *, render: bool = True) -> CheckedVideo:
    """Check a whole video. With ``render``, also draw frames when a renderer exists."""

    if not isinstance(data, dict):
        return CheckedVideo(None, ["The animation data must be one JSON object."])
    try:
        video = LottieVideo.model_validate({**data, "format": FORMAT})
    except ValidationError as error:
        return CheckedVideo(
            None,
            [
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors()[:20]
            ],
        )
    errors: list[str] = []
    if len(video.scenes) > MAX_SCENES:
        errors.append(f"At most {MAX_SCENES} scenes; this has {len(video.scenes)}.")
    seen: set[str] = set()
    for scene in video.scenes:
        if scene.id in seen:
            errors.append(f"Two scenes have the id '{scene.id}'.")
        seen.add(scene.id)
        if len(scene.caption) > MAX_CAPTION_LENGTH:
            errors.append(
                f"scene '{scene.id}': the caption is {len(scene.caption)} characters; "
                f"at most {MAX_CAPTION_LENGTH}."
            )
        errors.extend(check_scene(scene.id, scene.lottie))
    if not errors and render and renderer_available():
        errors.extend(render_errors(video))
    if errors:
        return CheckedVideo(None, errors)
    return CheckedVideo(video)


# --- rendering ------------------------------------------------------------


def renderer_available() -> bool:
    if os.environ.get("POLARIS_LOTTIE_RENDER") == "off":
        return False
    return shutil.which("node") is not None and RENDER_SCRIPT.is_file()


@dataclass(frozen=True)
class RenderedScene:
    id: str
    errors: list[str]
    ink: list[tuple[int, float]]
    sheet: Path


def check_frames(lottie: dict[str, Any], count: int = 6) -> list[int]:
    """Evenly spread frames from the first to the last of a scene."""

    start = int(lottie.get("ip", 0))
    end = max(start, int(lottie.get("op", 1)) - 1)
    if count <= 1 or end == start:
        return [end]
    return sorted({round(start + (end - start) * index / (count - 1)) for index in range(count)})


def render_scenes(
    scenes: list[tuple[str, dict[str, Any], list[int]]],
    *,
    out_dir: Path,
    background: str = BACKGROUND,
    cell_width: int = 400,
    timeout: float = 180.0,
) -> list[RenderedScene]:
    """Draw frames of each scene into one contact sheet per scene."""

    payload = {
        "background": background,
        "width": cell_width,
        "out": str(out_dir),
        "scenes": [
            {"id": scene_id, "lottie": lottie, "frames": frames}
            for scene_id, lottie, frames in scenes
        ],
    }
    completed = subprocess.run(
        ["node", str(RENDER_SCRIPT)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        cwd=REPO_ROOT,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", "replace")[-2000:])
    result = json.loads(completed.stdout.decode("utf-8"))
    return [
        RenderedScene(
            id=item["id"],
            errors=list(item.get("errors", [])),
            ink=[(int(frame["frame"]), float(frame["ink"])) for frame in item.get("frames", [])],
            sheet=Path(item["sheet"]),
        )
        for item in result["scenes"]
    ]


def render_errors(video: LottieVideo) -> list[str]:
    """Scenes that throw in lottie-web, or whose settled frame draws nothing."""

    with tempfile.TemporaryDirectory(prefix="polaris-lottie-") as tmp:
        try:
            rendered = render_scenes(
                [
                    (scene.id, scene.lottie, check_frames(scene.lottie, 3))
                    for scene in video.scenes
                ],
                out_dir=Path(tmp),
                background=video.background,
                cell_width=200,
            )
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
            # A missing or broken renderer is not the writer's fault.
            print(f"lottie render check skipped: {error}")
            return []
    errors: list[str] = []
    for scene in rendered:
        for message in scene.errors[:3]:
            errors.append(f"scene '{scene.id}': lottie-web error: {message}")
        if scene.ink and scene.ink[-1][1] < MIN_INK:
            errors.append(f"scene '{scene.id}': the last frame is blank.")
    return errors


# --- descriptions -----------------------------------------------------------


def describe_lottie_step(video: LottieVideo, index: int) -> str:
    scene = video.scenes[index]
    return f"Step {index + 1} ('{scene.id}'): {scene.caption.strip()}"


def describe_lottie_video(video: LottieVideo) -> str:
    """Short text for a later turn: title, description, and each scene's caption."""

    lines = [f"Animation {video.id}: {video.title.strip()}", video.description.strip()]
    lines.extend(describe_lottie_step(video, index) for index in range(len(video.scenes)))
    return "\n".join(lines)
