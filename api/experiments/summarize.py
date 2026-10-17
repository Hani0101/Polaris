"""Print a markdown table of an experiment run folder.

    uv run python -m experiments.summarize ../experiments-out/manim
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1])
    rows = []
    for result in sorted(root.glob("*/result.json")):
        record = json.loads(result.read_text(encoding="utf-8"))
        runs = record["runs"]
        previews = [p for run in runs for p in run.get("previews", [])]
        cost = sum(run.get("cost_usd") or 0 for run in runs)
        last = runs[-1] if runs else {}
        rows.append(
            (
                record["id"],
                "yes" if record["ready"] else "no",
                len(runs),
                len(previews),
                sum(1 for p in previews if not p["ok"]),
                f"{cost:.2f}",
                f"{record['total_s']:.0f}",
                f"{last.get('final_render_s', 0):.0f}",
                f"{last.get('duration_s', 0):.0f}",
                len(last.get("captions", [])),
            )
        )
    head = (
        "brief", "ready", "runs", "previews", "failed previews", "cost $",
        "total s", "final render s", "video s", "steps",
    )
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for row in rows:
        print("| " + " | ".join(str(cell) for cell in row) + " |")
    ready = sum(1 for row in rows if row[1] == "yes")
    total_cost = sum(float(row[5]) for row in rows)
    print(f"\n{ready}/{len(rows)} ready, ${total_cost:.2f} in total.")


if __name__ == "__main__":
    main()
