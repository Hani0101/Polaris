"""Run the Manim writer on animation briefs and render the final videos.

    uv run python -m experiments.run_manim --out ../experiments-out/manim [--brief pendulum ...]

Calls Claude through the local login, so it runs by hand. Each brief gets
a folder with the writer's previews, the final render, and result.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from pathlib import Path

from polaris.animation_writer import new_cli_loop
from polaris.manim_render import FINAL, render
from polaris.manim_writer import ClaudeManimWriter, ManimWriterFailed

BRIEFS = Path(__file__).resolve().parent.parent / "evals" / "animation_briefs.json"


def run_brief(
    brief_id: str, brief: str, out: Path, model: str | None, previews: int
) -> dict:
    folder = out / brief_id
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    writer = ClaudeManimWriter(folder / "work", model=model, max_previews=previews)
    record: dict = {"id": brief_id, "brief": brief, "runs": []}
    errors: list[str] | None = None
    code: str | None = None
    started = time.monotonic()
    loop = new_cli_loop()
    try:
        for attempt in range(1, 4):
            run_started = time.monotonic()
            try:
                draft = loop.run_until_complete(
                    writer.write(
                        brief,
                        failed_code=code,
                        errors=errors,
                        preview_dir=folder / f"run-{attempt}" / "previews",
                    )
                )
            except ManimWriterFailed as error:
                record["runs"].append({"attempt": attempt, "writer_error": str(error)})
                errors = [str(error)]
                continue
            code = draft.code
            (folder / f"run-{attempt}").mkdir(parents=True, exist_ok=True)
            (folder / f"run-{attempt}" / "scene.py").write_text(code, encoding="utf-8")
            write_s = round(time.monotonic() - run_started, 1)
            final_started = time.monotonic()
            final = render(code, folder / f"run-{attempt}" / "final", quality=FINAL)
            run = {
                "attempt": attempt,
                "title": draft.title,
                "description": draft.description,
                "write_s": write_s,
                "previews": draft.run.previews,
                "cost_usd": draft.run.cost_usd,
                "turns": draft.run.num_turns,
                "final_ok": final.ok,
                "final_errors": list(final.errors),
                "final_render_s": round(time.monotonic() - final_started, 1),
                "duration_s": final.duration_s,
                "captions": [step.caption for step in final.steps],
            }
            record["runs"].append(run)
            if final.ok and final.video is not None:
                shutil.copy(final.video, folder / "animation.mp4")
                record["ready"] = True
                break
            errors = list(final.errors)
    finally:
        loop.close()
    record.setdefault("ready", False)
    record["total_s"] = round(time.monotonic() - started, 1)
    (folder / "result.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--brief", action="append", default=[])
    parser.add_argument("--model", default=None)
    parser.add_argument("--previews", type=int, default=5, help="0 turns the preview tool off")
    args = parser.parse_args()
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))
    chosen = [b for b in briefs if not args.brief or b["id"] in args.brief]
    args.out.mkdir(parents=True, exist_ok=True)
    for item in chosen:
        record = run_brief(item["id"], item["brief"], args.out, args.model, args.previews)
        last = record["runs"][-1] if record["runs"] else {}
        print(
            f"{item['id']}: ready={record['ready']} runs={len(record['runs'])} "
            f"total={record['total_s']}s previews={len(last.get('previews', []))} "
            f"cost={last.get('cost_usd')}",
            flush=True,
        )


if __name__ == "__main__":
    main()
