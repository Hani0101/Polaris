"""What a Polaris Manim scene imports besides Manim itself.

A scene is ``from manim import *`` and ``from polaris_manim import *``,
then one subclass of ``PolarisScene``. Each ``self.step(caption)`` starts
one step of the animation; the caption is shown under the video and read
by a screen reader, so the scene does not draw it.

The colours are the Polaris design system's dark mode (tokens.json). They
are the default, not a limit: a scene may use other colours and set its own
background with ``self.camera.background_color``. The fonts are the design
system's, registered by the runner.
"""

from __future__ import annotations

from manim import Scene, config

# Dark-mode design tokens.
BACKGROUND = "#0c0701"  # color.bg.page
SURFACE = "#211910"  # color.surface.raised
BORDER = "#3a3026"  # color.border.default
INK = "#faf8f4"  # color.text.primary
MUTED = "#c9bfb2"  # color.text.secondary
FAINT = "#7a6f62"  # color.border.strong
ACCENT = "#f08a4b"  # color.accent
POSITIVE = "#8fd19e"  # color.state.success
NEGATIVE = "#f19a8e"  # color.state.error
HIGHLIGHT = "#f0c674"  # color.state.warning
INFO = "#9cc3ff"  # color.state.info

BODY_FONT = "Atkinson Hyperlegible Next"
MONO_FONT = "Atkinson Hyperlegible Mono"

# Text sizes that stay readable on a 320px phone screen, where the frame is
# about 254px wide: size 40 is about 14px there, the Polaris minimum.
TITLE_SIZE = 56
BODY_SIZE = 48
LABEL_SIZE = 40
MIN_TEXT_SIZE = 40

# Keep everything this far inside the frame edges.
SAFE_MARGIN = 0.4

__all__ = [
    "ACCENT",
    "BACKGROUND",
    "BODY_FONT",
    "BODY_SIZE",
    "BORDER",
    "FAINT",
    "HIGHLIGHT",
    "INFO",
    "INK",
    "LABEL_SIZE",
    "MIN_TEXT_SIZE",
    "MONO_FONT",
    "MUTED",
    "NEGATIVE",
    "POSITIVE",
    "PolarisScene",
    "SAFE_MARGIN",
    "SURFACE",
    "TITLE_SIZE",
    "safe_bottom",
    "safe_left",
    "safe_right",
    "safe_top",
]


def safe_top() -> float:
    return config.frame_height / 2 - SAFE_MARGIN


def safe_bottom() -> float:
    return -config.frame_height / 2 + SAFE_MARGIN


def safe_left() -> float:
    return -config.frame_width / 2 + SAFE_MARGIN


def safe_right() -> float:
    return config.frame_width / 2 - SAFE_MARGIN


class PolarisScene(Scene):
    """A scene split into captioned steps.

    The runner replaces ``_on_step`` and ``_after_animation`` to record
    steps, check the layout, and keep a picture of each step's end.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.captions: list[str] = []

    def step(self, caption: str) -> None:
        """Start the next step. Every animation belongs to a step."""

        self._on_step(caption)
        self.captions.append(caption)
        self.next_section(f"step-{len(self.captions)}")

    def play(self, *args, **kwargs) -> None:
        self._before_animation()
        super().play(*args, **kwargs)
        self._after_animation()

    def wait(self, *args, **kwargs) -> None:
        self._before_animation()
        super().wait(*args, **kwargs)
        self._after_animation()

    def _on_step(self, caption: str) -> None:
        pass

    def _before_animation(self) -> None:
        pass

    def _after_animation(self) -> None:
        pass

