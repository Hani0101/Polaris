from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """Facts Polaris already knows about the learner. Read only."""

    facts: tuple[str, ...]


@dataclass(frozen=True)
class Turn:
    """One typed learner message and the reply that followed it."""

    learner_message: str
    reply: str
