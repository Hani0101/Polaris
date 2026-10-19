"""Animation evals: run every fixed brief through the real writer and the check.

Records, for each brief, whether the job became ready, how many runs it
used (AN-05 allows three), how long it took, and the last check errors.
These call Claude through the local Claude login, so they run by hand:

    uv run python evals/run_animation_evals.py [--only pendulum,attention]

A report is written to evals/results/<timestamp>.json, and ready
animations are kept beside it so they can be opened and scored by eye.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris.animation import ANIMATION_FILE, READY, produce  # noqa: E402
from polaris.animation_writer import ClaudeAnimationWriter, new_cli_loop  # noqa: E402
from polaris.login import assert_claude_login  # noqa: E402

EVALS_DIR = Path(__file__).resolve().parent
BRIEFS_PATH = EVALS_DIR / "animation_briefs.json"


def run_brief(brief_id: str, brief: str, out_dir: Path) -> dict[str, Any]:
    work_dir = out_dir / brief_id
    work_dir.mkdir(parents=True, exist_ok=True)
    writer = ClaudeAnimationWriter(out_dir / "claude-work")
    loop = new_cli_loop()
    last_data: dict[str, Any] | None = None
    last_errors: list[str] | None = None

    def write_animation(errors: list[str] | None) -> dict[str, Any]:
        nonlocal last_data, last_errors
        last_errors = errors
        last_data = loop.run_until_complete(
            writer.write(
                brief,
                failed_data=last_data if errors is not None else None,
                errors=errors,
            )
        )
        return last_data

    started = time.monotonic()
    try:
        result = produce(job_id=brief_id, work_dir=work_dir, write_animation=write_animation)
        status, runs, crash = result.status, result.runs, None
    except Exception as exc:  # The writer can fail; the eval records it.
        status, runs, crash = "failed", None, f"{type(exc).__name__}: {exc}"
    finally:
        loop.close()
    seconds = round(time.monotonic() - started, 1)
    if status != READY and last_data is not None:
        (work_dir / "last_refused.json").write_text(json.dumps(last_data, indent=2))
    return {
        "id": brief_id,
        "status": status,
        "runs": runs,
        "seconds": seconds,
        "errors_before_last_run": last_errors,
        "crash": crash,
        "animation": str(work_dir / ANIMATION_FILE) if status == READY else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated brief ids")
    args = parser.parse_args()

    assert_claude_login()
    briefs = json.loads(BRIEFS_PATH.read_text(encoding="utf-8"))
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        briefs = [item for item in briefs if item["id"] in wanted]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = EVALS_DIR / "results" / stamp
    out_dir.mkdir(parents=True)
    rows = []
    for item in briefs:
        row = run_brief(item["id"], item["brief"], out_dir)
        rows.append(row)
        print(f"{row['id']:<20} {row['status']:<7} runs={row['runs']} {row['seconds']}s")
    shutil.rmtree(out_dir / "claude-work", ignore_errors=True)

    ready = sum(1 for row in rows if row["status"] == READY)
    first_try = sum(1 for row in rows if row["status"] == READY and row["runs"] == 1)
    report = {
        "when": stamp,
        "briefs": len(rows),
        "ready": ready,
        "ready_on_first_run": first_try,
        "results": rows,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{ready}/{len(rows)} ready, {first_try} on the first run. Report: {out_dir / 'report.json'}")
    return 0 if ready == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
