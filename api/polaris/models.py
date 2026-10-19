from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """Facts Polaris already knows about the learner.

    `signed_in` is False in an anonymous session, which reads no profile, so
    `facts` is empty and the reply does not ask for them (PR-01, decision 0008).
    """

    facts: tuple[str, ...]
    signed_in: bool = True


@dataclass(frozen=True)
class Fact:
    """One stored fact on the profile, with its kind and basis.

    `written_by` is "pass" for the session-end pass, "learner" for an edit in
    Settings (PR-11).
    """

    id: str
    kind: str
    text: str
    basis: str
    created_at: str
    updated_at: str
    written_by: str = "pass"


@dataclass(frozen=True)
class FactChange:
    """One ADD, UPDATE, DELETE, or IGNORE from the profile pass.

    UPDATE, DELETE, and IGNORE name a stored fact by `id`. `evidence` holds
    the ids of the turns the change rests on.
    """

    action: str
    text: str = ""
    id: str | None = None
    kind: str | None = None
    basis: str | None = None
    evidence: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class Pointing:
    """Parts of one whiteboard the learner pointed at for a turn.

    This is turn metadata. It is not part of the drawing format.
    """

    whiteboard_id: str
    element_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnimationStep:
    """The animation step the learner asked about for a turn (AN-17).

    This is turn metadata. It is not part of the animation format.
    """

    job_id: str
    step_id: str


@dataclass(frozen=True)
class Turn:
    """One typed learner message and the reply that followed it."""

    learner_message: str
    reply: str
    artifacts: tuple[dict[str, object], ...] = ()
    pointing: Pointing | None = None
    id: str | None = None
    animation_step: AnimationStep | None = None
