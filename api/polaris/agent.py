from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from polaris.animation_format import Animation
from polaris.board_picture import BoardPicture
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
        quizzes: Sequence[dict[str, object]] = (),
        picture: BoardPicture | None = None,
        animations: Sequence[Animation] = (),
        animation_step: AnimationStep | None = None,
        pinned: Whiteboard | None = None,
        resources: Sequence[str] = (),
        decks: Sequence[dict[str, object]] = (),
        web: bool = False,
    ) -> AsyncIterator[str | ReplyResult]:
        """Stream reply text, then one ReplyResult when the stream reaches a result.

        quizzes are the learner-visible payloads of this session's quizzes.
        Chat passes picture only when the learner's turn carries one, and
        pinned only while a board is pinned above the conversation (WB-19).
        resources is one line per resource the learner gave the session, and is
        empty when there are none (RS-07). decks are the learner-visible payloads
        of this session's flashcard decks, with their ratings (FC-15). web is
        True only when the learner sent this message in web mode, and only then
        may the reply search or read the web (CH-23).
        """

    async def close_session(self, session_id: str) -> None:
        """Drop the agent connection for a session the learner left."""
