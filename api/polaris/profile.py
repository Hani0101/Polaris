"""Read and write the shared profile.

The teaching agent reads the profile and does not write it. The session-end
pass writes fact changes (PR-05 to PR-08). The learner can add, change, and
remove facts from Settings (PR-11), and the pass does not bring back what the
learner took out (PR-12). Facts live in the session database with a kind, a
basis, times, and the turns they rest on. See research note 0001, decision
0006 (proposed), and decision 0014.
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
MAX_FACT_LENGTH = 300


class ProfileUnreadable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("The profile could not be read.")


class ProfilePassFailed(RuntimeError):
    """The pass ran but returned no usable result."""


class MissingFact(Exception):
    def __init__(self) -> None:
        super().__init__("That is no longer on your profile.")


class BlankFact(Exception):
    def __init__(self) -> None:
        super().__init__("Type something to keep on your profile.")


class FactTooLong(Exception):
    def __init__(self) -> None:
        super().__init__(f"Keep it to {MAX_FACT_LENGTH} characters.")


class FactRepeats(Exception):
    def __init__(self) -> None:
        super().__init__("Your profile already says this.")


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
            replaced_by TEXT REFERENCES facts(id),
            retired_by TEXT CHECK (retired_by IN ('pass', 'learner'))
        )
        """
    )
    # A database from before learner edits has no retired_by column.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(facts)").fetchall()}
    if "retired_by" not in columns:
        conn.execute(
            "ALTER TABLE facts ADD COLUMN retired_by TEXT "
            "CHECK (retired_by IN ('pass', 'learner'))"
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
        SELECT id, kind, text, basis, created_at, updated_at, written_by
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
            written_by=row["written_by"],
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
    place (PR-07). A change whose text the learner removed or reworded is
    refused unless a turn after that edit backs it (PR-12).
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
                """
                UPDATE facts SET retired_at = ?, retired_by = 'pass', updated_at = ?
                WHERE id = ?
                """,
                (now, now, change.id),
            )
            del active[change.id]
            accepted.append(_record(change, None, action="DELETE"))
            continue
        if not text:
            refuse(change, "no text")
            continue
        if _learner_took_out(conn, text, evidence):
            refuse(change, "the learner took this fact out")
            continue
        if action == "UPDATE":
            old = active.get(change.id) if change.id is not None else None
            if old is None:
                refuse(change, "names no stored fact")
                continue
            new = _replace_fact(
                conn,
                old,
                kind=change.kind or old.kind,
                text=text,
                basis=change.basis or old.basis,
                writer="pass",
                now=now,
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


def add_learner_fact(conn: sqlite3.Connection, text: str, now: str) -> Fact:
    """PR-11: the learner adds a fact in Settings. It is stated, and unsorted."""

    text = _learner_text(text)
    if _repeats(text, active_facts(conn)):
        raise FactRepeats()
    return _insert_fact(
        conn, kind="unsorted", text=text, basis="stated", now=now, writer="learner"
    )


def edit_learner_fact(
    conn: sqlite3.Connection, fact_id: str, text: str, now: str
) -> Fact:
    """PR-11: the learner rewords a fact. The old wording is kept, retired.

    The kind and evidence carry over. The new wording is stated by the learner.
    """

    text = _learner_text(text)
    active = active_facts(conn)
    old = next((fact for fact in active if fact.id == fact_id), None)
    if old is None:
        raise MissingFact()
    if text == old.text:
        return old
    if _repeats(text, [fact for fact in active if fact.id != fact_id]):
        raise FactRepeats()
    return _replace_fact(
        conn, old, kind=old.kind, text=text, basis="stated", writer="learner", now=now
    )


def remove_learner_fact(conn: sqlite3.Connection, fact_id: str, now: str) -> None:
    """PR-11: the learner takes a fact off the profile. The row is kept, retired."""

    cursor = conn.execute(
        """
        UPDATE facts SET retired_at = ?, retired_by = 'learner', updated_at = ?
        WHERE id = ? AND retired_at IS NULL
        """,
        (now, now, fact_id),
    )
    if cursor.rowcount == 0:
        raise MissingFact()


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
    writer: str = "pass",
) -> Fact:
    fact = Fact(
        id=str(uuid.uuid4()),
        kind=kind,
        text=text,
        basis=basis,
        created_at=created_at or now,
        updated_at=now,
        written_by=writer,
    )
    conn.execute(
        """
        INSERT INTO facts (id, kind, text, basis, written_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact.id,
            fact.kind,
            fact.text,
            fact.basis,
            fact.written_by,
            fact.created_at,
            fact.updated_at,
        ),
    )
    return fact


def _replace_fact(
    conn: sqlite3.Connection,
    old: Fact,
    *,
    kind: str,
    text: str,
    basis: str,
    writer: str,
    now: str,
) -> Fact:
    """Store a new wording, retire the old one, and carry its evidence over."""

    new = _insert_fact(
        conn,
        kind=kind,
        text=text,
        basis=basis,
        now=now,
        created_at=old.created_at,
        writer=writer,
    )
    conn.execute(
        """
        UPDATE facts SET retired_at = ?, retired_by = ?, replaced_by = ?, updated_at = ?
        WHERE id = ?
        """,
        (now, writer, new.id, now, old.id),
    )
    conn.execute(
        """
        INSERT INTO fact_evidence (fact_id, session_id, turn_id, artifact_id)
        SELECT ?, session_id, turn_id, artifact_id
        FROM fact_evidence WHERE fact_id = ?
        """,
        (new.id, old.id),
    )
    return new


def _learner_text(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise BlankFact()
    if len(text) > MAX_FACT_LENGTH:
        raise FactTooLong()
    return text


def _learner_took_out(
    conn: sqlite3.Connection, text: str, evidence: Sequence[str]
) -> bool:
    """PR-12: the learner removed or reworded this text after every turn behind it.

    A pass reads the whole session again each time it ends, so without this
    an old turn would put back what the learner took out. A turn sent after
    that edit can still store it. The match is on wording, as for repeats.
    """

    key = _normalized(text)
    taken_out = [
        row["retired_at"]
        for row in conn.execute(
            "SELECT text, retired_at FROM facts WHERE retired_by = 'learner'"
        ).fetchall()
        if _normalized(row["text"]) == key
    ]
    if not taken_out:
        return False
    if not evidence:
        return True
    marks = ", ".join("?" for _ in evidence)
    newest = conn.execute(
        f"SELECT MAX(created_at) FROM turns WHERE id IN ({marks})", tuple(evidence)
    ).fetchone()[0]
    return newest is None or newest <= max(taken_out)


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
