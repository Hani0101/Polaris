"""The two animation engines, their settings, and the learner's choice (AN-21, AN-26).

Manim suits scientific animations: maths, equations, plots, geometry, and
physics. Lottie suits every other topic: how something works, processes,
systems, stories, and timelines. A job waits in the ``choosing`` stage until
the learner picks one, and only then does the chosen writer start.

Each engine has its own legal quality and frame rate values, listed in
``ENGINE_OPTIONS``. ``check_settings`` refuses anything else, so a request
that bypasses the UI still cannot set an illegal value. The web app offers
the same values (``web/src/animation/settings.ts``).

- Manim renders video, so quality is the pixel size of the final render.
- Lottie is vector data that lottie-web draws in the browser, so quality is
  lottie-web's drawing quality (``lottie.setQuality``), and the frame rate is
  the scenes' ``fr``, which the player keeps to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MANIM = "manim"
LOTTIE = "lottie"
ENGINES = (MANIM, LOTTIE)


@dataclass(frozen=True)
class EngineOptions:
    qualities: tuple[str, ...]
    frame_rates: tuple[int, ...]
    default_quality: str
    default_fps: int


ENGINE_OPTIONS: dict[str, EngineOptions] = {
    MANIM: EngineOptions(
        qualities=("480p", "720p", "1080p"),
        frame_rates=(15, 24, 30, 60),
        default_quality="1080p",
        default_fps=60,
    ),
    LOTTIE: EngineOptions(
        qualities=("low", "medium", "high"),
        frame_rates=(24, 30, 60),
        default_quality="high",
        default_fps=30,
    ),
}

# Manim quality -> final render size in pixels. 4:3, like the Polaris canvas.
MANIM_SIZES: dict[str, tuple[int, int]] = {
    "480p": (640, 480),
    "720p": (960, 720),
    "1080p": (1440, 1080),
}


class UnknownEngine(ValueError):
    def __init__(self) -> None:
        super().__init__("Choose manim or lottie.")


class IllegalSettings(ValueError):
    """A quality or frame rate the chosen engine does not offer."""


class EngineChoiceClosed(Exception):
    def __init__(self) -> None:
        super().__init__("This animation is not waiting for an engine choice.")


@dataclass(frozen=True)
class AnimationSettings:
    """The engine, quality, and frame rate of one job."""

    engine: str
    quality: str
    fps: int

    def as_payload(self) -> dict[str, object]:
        return {"engine": self.engine, "quality": self.quality, "fps": self.fps}

    def manim_output(self) -> tuple[int, int, int]:
        """Pixel width, height, and frames per second of the final Manim render."""

        width, height = MANIM_SIZES[self.quality]
        return width, height, self.fps


def check_settings(engine: object, quality: object, fps: object) -> AnimationSettings:
    """Settings the engine offers, or UnknownEngine / IllegalSettings."""

    if engine not in ENGINES:
        raise UnknownEngine()
    options = ENGINE_OPTIONS[str(engine)]
    name = "Manim" if engine == MANIM else "Lottie"
    if quality not in options.qualities:
        raise IllegalSettings(
            f"{name} quality must be one of {', '.join(options.qualities)}."
        )
    # bool is an int in Python; True is not a frame rate.
    if isinstance(fps, bool) or fps not in options.frame_rates:
        rates = ", ".join(str(rate) for rate in options.frame_rates)
        raise IllegalSettings(f"{name} frame rate must be one of {rates}.")
    return AnimationSettings(engine=str(engine), quality=str(quality), fps=int(fps))


def default_settings(engine: str) -> AnimationSettings:
    options = ENGINE_OPTIONS[engine]
    return AnimationSettings(engine, options.default_quality, options.default_fps)


def load_settings(engine: str | None, quality: str | None, fps: int | None) -> AnimationSettings | None:
    """Settings stored on a job, or None when the job has none or they no longer pass."""

    if engine is None:
        return None
    try:
        return check_settings(engine, quality, fps)
    except ValueError:
        return None


@dataclass(frozen=True)
class AnimationEngines:
    """Both animation writers. The learner picks one per job."""

    manim: Any
    lottie: Any

    def writer_for(self, engine: str) -> Any:
        if engine == MANIM:
            return self.manim
        if engine == LOTTIE:
            return self.lottie
        raise UnknownEngine()
