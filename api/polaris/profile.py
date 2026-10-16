"""Read and write the shared profile.

The teaching agent reads the profile and does not write it. The session-end
pass writes fact changes (PR-05 to PR-08). Facts live in the session database
with a kind, a basis, times, and the turns they rest on. See research note
0001 and decision 0006 (proposed).
"""

import json
import re
import sqlite3
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from polaris.models import Fact, FactChange, Turn

_ACTIONS = frozenset({"ADD", "UPDATE", "DELETE", "IGNORE"})
# Order facts are read in: goal first, then how they want to be taught.
FACT_KINDS = ("goal", "taught", "struggle", "can_do", "milestone", "unsorted")
FACT_BASES = ("stated", "observed", "inferred")
PASS_TRIGGERS = ("end",)
PASS_STATUSES = ("running", "stored", "no_change", "failed")


class ProfileUnreadable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The profile could not be read.")


class ProfilePassFailed(RuntimeError):
    """The pass ran but returned no usable result."""


class ProfilePass(Protocol):
    """A separate model that reads a session and returns fact changes."""

    async def run(
        self, *, turns: Sequence[Turn], facts: Sequence[Fact]
    ) -> Sequence[FactChange]:
        """Return ADD, UPDATE, DELETE, or IGNORE changes for this session."""


@dataclass(frozen=True)
class AppliedChanges:
    """What a pass changed, and what code refused, with the reason."""

    accepted: tuple[dict[str, object], ...]
    refused: tuple[dict[str, object], ...]

    @property
    def stored(self) -> bool:
        return any(item["action"] != "IGNORE" for item in self.accepted)


def create_profile_tables(conn: sqlite3.Connection) -> None:
    kinds = ", ".join(f"'{kind}'" for kind in FACT_KINDS)
    bases = ", ".join(f"'{basis}'" for basis in FACT_BASES)
    triggers = ", ".join(f"'{trigger}'" for trigger in PASS_TRIGGERS)
    statuses = ", ".join(f"'{status}'" for status in PASS_STATUSES)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS facts (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ({kinds})),
            text TEXT NOT NULL,
            basis TEXT NOT NULL CHECK (basis IN ({bases})),
            written_by TEXT NOT NULL CHECK (written_by IN ('pass', 'learner')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            retired_at TEXT,
            replaced_by TEXT REFERENCES facts(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_evidence (
            id INTEGER PRIMARY KEY,
            fact_id TEXT NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            turn_id TEXT REFERENCES turns(id),
            artifact_id TEXT REFERENCES artifacts(id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS fact_evidence_fact_id
        ON fact_evidence(fact_id)
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS profile_passes (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            trigger TEXT NOT NULL CHECK (trigger IN ({triggers})),
            status TEXT NOT NULL CHECK (status IN ({statuses})),
            error TEXT,
            last_turn_id TEXT REFERENCES turns(id),
            changes_json TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT
        )
        """
    )


def import_profile_json(conn: sqlite3.Connection, path: Path, now: str) -> None:
    """Move facts from the old profile.json into the database, once.

    Each string becomes an unsorted, inferred fact with no evidence. The file
    is renamed, not deleted, so the old profile can be recovered by hand.
    """

    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        facts = data["facts"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ProfileUnreadable() from exc
    if not isinstance(facts, list) or not all(isinstance(fact, str) for fact in facts):
        raise ProfileUnreadable()
    active = active_facts(conn)
    for text in facts:
        text = text.strip()
        if not text or _repeats(text, active):
            continue
        fact = _insert_fact(conn, kind="unsorted", text=text, basis="inferred", now=now)
        active = (*active, fact)
    path.replace(path.with_name(path.name + ".imported"))


def active_facts(conn: sqlite3.Connection) -> tuple[Fact, ...]:
    order = " ".join(f"WHEN '{kind}' THEN {rank}" for rank, kind in enumerate(FACT_KINDS))
    rows = conn.execute(
        f"""
        SELECT id, kind, text, basis, created_at, updated_at
        FROM facts
        WHERE retired_at IS NULL
        ORDER BY CASE kind {order} END, created_at ASC, rowid ASC
        """
    ).fetchall()
    return tuple(
        Fact(
            id=row["id"],
            kind=row["kind"],
            text=row["text"],
            basis=row["basis"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    )


def apply_changes(
    conn: sqlite3.Connection,
    changes: Sequence[FactChange],
    *,
    session_id: str,
    turn_ids: Collection[str],
    now: str,
) -> AppliedChanges:
    """Apply ADD, UPDATE, DELETE, and IGNORE. A repeated fact stays once.

    A change that names no stored fact is refused. Nothing is added in its
    place (PR-07).
    """

    accepted: list[dict[str, object]] = []
    refused: list[dict[str, object]] = []
    active = {fact.id: fact for fact in active_facts(conn)}

    def refuse(change: FactChange, why: str) -> None:
        refused.append(_record(change, why))

    for change in changes:
        action = change.action.strip().upper()
        text = change.text.strip()
        if action not in _ACTIONS:
            refuse(change, "unknown action")
            continue
        if change.kind is not None and change.kind not in FACT_KINDS:
            refuse(change, "unknown kind")
            continue
        if change.basis is not None and change.basis not in FACT_BASES:
            refuse(change, "unknown basis")
            continue
        evidence = [turn_id for turn_id in change.evidence if turn_id in turn_ids]
        if action == "IGNORE":
            if change.id is not None and change.id not in active:
                refuse(change, "names no stored fact")
                continue
            accepted.append(_record(change, None, action="IGNORE"))
            continue
        if action == "DELETE":
            if change.id is None or change.id not in active:
                refuse(change, "names no stored fact")
                continue
            conn.execute(
                "UPDATE facts SET retired_at = ?, updated_at = ? WHERE id = ?",
                (now, now, change.id),
            )
            del active[change.id]
            accepted.append(_record(change, None, action="DELETE"))
            continue
        if not text:
            refuse(change, "no text")
            continue
        if action == "UPDATE":
            old = active.get(change.id) if change.id is not None else None
            if old is None:
                refuse(change, "names no stored fact")
                continue
            new = _insert_fact(
                conn,
                kind=change.kind or old.kind,
                text=text,
                basis=change.basis or old.basis,
                now=now,
                created_at=old.created_at,
            )
            conn.execute(
                """
                UPDATE facts SET retired_at = ?, replaced_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, new.id, now, old.id),
            )
            conn.execute(
                """
                INSERT INTO fact_evidence (fact_id, session_id, turn_id, artifact_id)
                SELECT ?, session_id, turn_id, artifact_id
                FROM fact_evidence WHERE fact_id = ?
                """,
                (new.id, old.id),
            )
            _add_evidence(conn, new.id, session_id, evidence)
            del active[old.id]
            active[new.id] = new
            accepted.append(_record(change, None, action="UPDATE", stored_id=new.id))
            continue
        if _repeats(text, active.values()):
            accepted.append(_record(change, "repeat of a stored fact", action="IGNORE"))
            continue
        new = _insert_fact(
            conn,
            kind=change.kind or "unsorted",
            text=text,
            basis=change.basis or "inferred",
            now=now,
        )
        _add_evidence(conn, new.id, session_id, evidence)
        active[new.id] = new
        accepted.append(_record(change, None, action="ADD", stored_id=new.id))
    return AppliedChanges(tuple(accepted), tuple(refused))


def start_pass(
    conn: sqlite3.Connection, session_id: str, trigger: str, now: str
) -> str:
    run_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO profile_passes (id, session_id, trigger, status, started_at)
        VALUES (?, ?, ?, 'running', ?)
        """,
        (run_id, session_id, trigger, now),
    )
    return run_id


def finish_pass(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    now: str,
    error: str | None = None,
    last_turn_id: str | None = None,
    applied: AppliedChanges | None = None,
) -> None:
    changes_json = None
    if applied is not None:
        changes_json = json.dumps(
            {"accepted": list(applied.accepted), "refused": list(applied.refused)}
        )
    conn.execute(
        """
        UPDATE profile_passes
        SET status = ?, error = ?, last_turn_id = ?, changes_json = ?, finished_at = ?
        WHERE id = ?
        """,
        (status, error, last_turn_id, changes_json, now, run_id),
    )


def _insert_fact(
    conn: sqlite3.Connection,
    *,
    kind: str,
    text: str,
    basis: str,
    now: str,
    created_at: str | None = None,
) -> Fact:
    fact = Fact(
        id=str(uuid.uuid4()),
        kind=kind,
        text=text,
        basis=basis,
        created_at=created_at or now,
        updated_at=now,
    )
    conn.execute(
        """
        INSERT INTO facts (id, kind, text, basis, written_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'pass', ?, ?)
        """,
        (fact.id, fact.kind, fact.text, fact.basis, fact.created_at, fact.updated_at),
    )
    return fact


def _add_evidence(
    conn: sqlite3.Connection, fact_id: str, session_id: str, turn_ids: list[str]
) -> None:
    for turn_id in turn_ids or [None]:
        conn.execute(
            "INSERT INTO fact_evidence (fact_id, session_id, turn_id) VALUES (?, ?, ?)",
            (fact_id, session_id, turn_id),
        )


def _normalized(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def _repeats(text: str, facts: Collection[Fact]) -> bool:
    key = _normalized(text)
    return any(_normalized(fact.text) == key for fact in facts)


def _record(
    change: FactChange,
    why: str | None,
    *,
    action: str | None = None,
    stored_id: str | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "action": action or change.action,
        "id": change.id,
        "kind": change.kind,
        "text": change.text,
        "reason": change.reason,
    }
    if stored_id is not None:
        item["stored_id"] = stored_id
    if why is not None:
        item["why"] = why
    return item
