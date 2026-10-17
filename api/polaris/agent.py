from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from polaris.animation_format import Animation
from polaris.models import AnimationStep, Pointing, Profile, Turn
from polaris.whiteboard import Whiteboard


@dataclass(frozen=True)
class ReplyResult:
    """End of a reply whose stream reached a result. Carries the Claude session id."""

    sdk_session_id: str | None


class ReplyAgent(Protocol):
    """The teaching agent. It can read a profile and stream a reply. It cannot write the profile."""

    def reply(
        self,
        *,
        session_id: str,
        profile: Profile,
        learner_message: str,
        prior_turns: Sequence[Turn],
        sdk_session_id: str | None,
        whiteboards: Sequence[Whiteboard] = (),
        pointing: Pointing | None = None,
        simplify: Whiteboard | None = None,
        animations: Sequence[Animation] = (),
        animation_step: AnimationStep | None = None,
    ) -> AsyncIterator[str | ReplyResult]:
        """Stream reply text, then one ReplyResult when the stream reaches a result."""

    async def close_session(self, session_id: str) -> None:
        """Drop the agent connection for a session the learner left."""
