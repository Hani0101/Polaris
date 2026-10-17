"""The drawing evals score with the layout checks. These tests never call the model."""

import asyncio
import json
import sqlite3
from pathlib import Path

from evals.drawing_eval import PROMPTS, main, run_cases, score_stored, score_whiteboard
from polaris.auto_layout import expand_layout
from polaris.teaching import submit_whiteboard
from polaris.whiteboard import check_drawing
from test_layout import LAYOUTS, _board, _box, _laid_out


def _whiteboard(data: dict):
    checked = check_drawing(data)
    assert checked.whiteboard is not None, checked.errors
    return checked.whiteboard


def _store(data_dir: Path, drawings: list[dict]) -> None:
    connection = sqlite3.connect(data_dir / "polaris.db")
    connection.execute("CREATE TABLE whiteboards (id TEXT PRIMARY KEY, drawing_json TEXT)")
    for drawing in drawings:
        connection.execute(
            "INSERT INTO whiteboards VALUES (?, ?)", (drawing["id"], json.dumps(drawing))
        )
    connection.commit()
    connection.close()


def test_a_placed_layout_scores_clean():
    placed = expand_layout(_laid_out(LAYOUTS["flow"])).drawing

    score = score_whiteboard(_whiteboard(placed))

    assert score.clean
    assert score.placed
    assert score.messages == []


def test_a_crowded_drawing_scores_its_problems():
    crowded = _board(_box("left", 40, 40), _box("right", 100, 60))

    score = score_whiteboard(_whiteboard(crowded))

    assert not score.clean
    assert not score.placed
    assert score.problems["overlap"] == 1
    assert score.messages


def test_score_reads_a_data_dir_and_gates_on_the_clean_rate(tmp_path: Path, capsys):
    clean = expand_layout(_laid_out(LAYOUTS["tree"])).drawing
    crowded = _board(_box("left", 40, 40), _box("right", 100, 60))
    crowded["id"] = "wb-crowded"
    _store(tmp_path, [clean, crowded])

    report = score_stored(tmp_path)

    assert report.summary()["drawings"] == 2
    assert report.summary()["clean"] == 1
    assert report.summary()["problems"]["overlap"] == 1
    assert main(["score", str(tmp_path), "--min-clean", "0.5"]) == 0
    assert main(["score", str(tmp_path), "--min-clean", "0.9"]) == 1
    printed = json.loads(capsys.readouterr().out.split("\n}\n")[0] + "\n}")
    assert printed["summary"]["clean_rate"] == 0.5


def test_the_eval_cases_are_well_formed():
    spec = json.loads(PROMPTS.read_text(encoding="utf-8"))

    assert spec["profile"]
    ids = [case["id"] for case in spec["cases"]]
    assert len(ids) == len(set(ids))
    assert all(case["message"].strip() for case in spec["cases"])


class LayoutAgent:
    """Draws one placed layout per reply, after one refused crowded drawing."""

    def __init__(self, _work_dir: Path) -> None:
        self.create = None
        self.failures: dict[str, int] = {}

    def bind_store(self, _quiz, create_whiteboard, **_kwargs) -> None:
        self.create = create_whiteboard

    async def reply(self, *, session_id: str, learner_message: str, **_kwargs):
        yield f"Drawing: {learner_message}"
        crowded = _board(_box("left", 40, 40), _box("right", 100, 60))
        refused = submit_whiteboard(session_id, crowded, failures=0, store=self.create)
        placed = _laid_out(LAYOUTS["cycle"])
        placed["id"] = f"wb-{session_id}"
        stored = submit_whiteboard(
            session_id, placed, failures=refused.failures, store=self.create
        )
        self.failures[session_id] = stored.failures

    def drawing_fix_count(self, session_id: str) -> int:
        return self.failures.get(session_id, 0)

    async def close_session(self, session_id: str) -> None:
        self.failures.pop(session_id, None)

    async def close_all(self) -> None:
        return None


def test_run_scores_each_case_and_counts_fixes(tmp_path: Path):
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            {
                "profile": ["likes pictures"],
                "cases": [{"id": "one", "message": "Draw a cycle."}],
            }
        ),
        encoding="utf-8",
    )

    report = asyncio.run(run_cases(cases, make_agent=LayoutAgent))

    summary = report.summary()
    assert summary["drawings"] == 1
    assert summary["clean"] == 1
    assert summary["placed_by_layout"] == 1
    assert summary["mean_fixes"] == 1
    assert report.drawings[0].case == "one"
