"""Read the shared profile.

The teaching agent reads the profile and does not write it. Decision 0003
blocks profile writing (PR-05 to PR-08). It does not block PR-02. An empty
profile is asked for before teaching, and nothing stores the answer.
"""

import json
from pathlib import Path

from polaris.models import Profile


class ProfileUnreadable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The profile could not be read.")


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
