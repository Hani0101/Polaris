"""Run the Lottie writer on one eval brief and store the video (experiment).

Usage: python evals/run_lottie_one.py <brief-id> [out-dir]
Writes <out-dir>/<brief-id>/animation.json and prints the check result.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from polaris.animation import produce  # noqa: E402
from polaris.animation_writer import new_cli_loop  # noqa: E402
from polaris.lottie_writer import LottieAnimationWriter  # noqa: E402


def main() -> int:
    brief_id = sys.argv[1]
    out_root = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent / "results" / "lottie")
    briefs = json.loads((Path(__file__).parent / "animation_briefs.json").read_text(encoding="utf-8"))
    brief = next(item["brief"] for item in briefs if item["id"] == brief_id)
    work = out_root / brief_id
    work.mkdir(parents=True, exist_ok=True)
    writer = LottieAnimationWriter(out_root / "lottie-work")
    loop = new_cli_loop()
    started = time.monotonic()

    def write(errors: list[str] | None) -> dict:
        return loop.run_until_complete(
            writer.write(brief, failed_data=None, errors=errors, job_id=brief_id)
        )

    try:
        result = produce(job_id=brief_id, work_dir=work, write_animation=write, on_stage=print)
    finally:
        loop.close()
    print(json.dumps({"status": result.status, "runs": result.runs, "seconds": round(time.monotonic() - started)}))
    return 0 if result.status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
