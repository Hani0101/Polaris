"""Read and write the shared profile.

The teaching agent reads the profile and does not write it. The session-end
pass writes fact changes (PR-05 to PR-08). Decision 0003 is accepted so that
pass can run; the design still needs research.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from polaris.models import FactChange, Profile, Turn

_ACTIONS = frozenset({"ADD", "UPDATE", "DELETE", "IGNORE"})


class ProfileUnreadable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The profile could not be read.")


class ProfilePass(Protocol):
    """A separate model that reads a session and returns fact changes."""

    async def run(
        self, *, turns: Sequence[Turn], profile: Profile
    ) -> Sequence[FactChange]:
        """Return ADD, UPDATE, DELETE, or IGNORE changes for this session."""


def load_profile(path: Path) -> Profile:
    """Return the one shared profile. A missing file is an empty profile."""

    if not path.exists():
        return Profile(())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        facts = data["facts"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ProfileUnreadable() from exc
    if not isinstance(facts, list) or not all(isinstance(fact, str) for fact in facts):
        raise ProfileUnreadable()
    return Profile(tuple(facts))


def save_profile(path: Path, profile: Profile) -> None:
    """Store the shared profile as JSON."""

    path.write_text(
        json.dumps({"facts": list(profile.facts)}, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_changes(profile: Profile, changes: Sequence[FactChange]) -> Profile:
    """Apply ADD, UPDATE, DELETE, and IGNORE. A repeated fact stays once."""

    facts = list(profile.facts)
    for change in changes:
        action = change.action.strip().upper()
        fact = change.fact.strip()
        if action not in _ACTIONS:
            continue
        if action == "IGNORE":
            continue
        if action == "DELETE":
            if fact:
                facts = [item for item in facts if item != fact]
            continue
        if not fact:
            continue
        if action == "UPDATE":
            replaced = (change.replaces or "").strip()
            if replaced and replaced in facts:
                facts = [fact if item == replaced else item for item in facts]
            elif fact not in facts:
                facts.append(fact)
            facts = _unique(facts)
            continue
        if fact not in facts:
            facts.append(fact)
    return Profile(tuple(facts))


def _unique(facts: list[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for fact in facts:
        if fact in seen:
            continue
        seen.add(fact)
        kept.append(fact)
    return kept
