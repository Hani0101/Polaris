"""The two animation engines, and the learner's choice between them (AN-21).

Manim suits scientific animations: maths, equations, plots, geometry, and
physics. Lottie suits every other topic: how something works, processes,
systems, stories, and timelines. A job waits in the ``choosing`` stage until
the learner picks one on the animation card, and only then does the chosen
writer start.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MANIM = "manim"
LOTTIE = "lottie"
ENGINES = (MANIM, LOTTIE)


class UnknownEngine(ValueError):
    def __init__(self) -> None:
        super().__init__("Choose manim or lottie.")


class EngineChoiceClosed(Exception):
    def __init__(self) -> None:
        super().__init__("This animation is not waiting for an engine choice.")


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
