from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """Facts Polaris already knows about the learner."""

    facts: tuple[str, ...]


@dataclass(frozen=True)
class FactChange:
    """One ADD, UPDATE, DELETE, or IGNORE from the profile pass."""

    action: str
    fact: str
    replaces: str | None = None


@dataclass(frozen=True)
class Pointing:
    """Parts of one whiteboard the learner pointed at for a turn.

    This is turn metadata. It is not part of the drawing format.
    """

    whiteboard_id: str
    element_ids: tuple[str, ...]


@dataclass(frozen=True)
class Turn:
    """One typed learner message and the reply that followed it."""

    learner_message: str
    reply: str
    artifacts: tuple[dict[str, object], ...] = ()
    pointing: Pointing | None = None
