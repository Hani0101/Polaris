"""Run the live evals: uv run python -m evals [--runs N] [--cases id,id] [--jobs J]."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from polaris.login import ApiKeyPresent, assert_claude_login

from evals.cases import CASES
from evals.harness import API_DIR, Case, Sample, temp_data_dir

REPORT_DIR = Path(__file__).resolve().parent / "reports"
SAMPLE_TIMEOUT_SECONDS = 600


async def run_sample(case: Case, index: int, gate: asyncio.Semaphore) -> Sample:
    async with gate:
        sample = Sample()
        started = time.monotonic()
        holder = temp_data_dir()
        try:
            await asyncio.wait_for(case.run(Path(holder.name), sample), SAMPLE_TIMEOUT_SECONDS)
        except ApiKeyPresent:
            raise
        except Exception as exc:
            sample.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
        finally:
            holder.cleanup()
            sample.seconds = time.monotonic() - started
        mark = "error" if sample.error else "ok"
        print(f"  {case.id} #{index + 1}: {mark} ({sample.seconds:.0f}s)", flush=True)
        return sample


async def run_all(cases: list[Case], runs: int, jobs: int) -> dict[str, list[Sample]]:
    gate = asyncio.Semaphore(jobs)
    tasks = {
        case.id: [asyncio.create_task(run_sample(case, index, gate)) for index in range(runs)]
        for case in cases
    }
    return {case_id: [await task for task in group] for case_id, group in tasks.items()}


# --- report --------------------------------------------------------------------


def _rate(samples: list[Sample], name: str) -> tuple[int, int, int, bool]:
    passed = failed = na = 0
    judged = False
    for sample in samples:
        for check in sample.checks:
            if check.name != name:
                continue
            judged = judged or check.judged
            if check.ok is None:
                na += 1
            elif check.ok:
                passed += 1
            else:
                failed += 1
    return passed, failed, na, judged


def _check_names(samples: list[Sample]) -> list[str]:
    names: list[str] = []
    for sample in samples:
        for check in sample.checks:
            if check.name not in names:
                names.append(check.name)
    return names


def _git_head() -> str:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=API_DIR, capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "polaris"], cwd=API_DIR, capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return "unknown"
    return f"{head}{' (polaris/ has local changes)' if dirty else ''}"


def _quote(text: str, limit: int = 2500) -> str:
    body = text if len(text) <= limit else text[:limit] + "\n… (cut)"
    return "\n".join("    " + line for line in body.splitlines()) or "    (empty)"


def render(cases: list[Case], results: dict[str, list[Sample]], runs: int, seconds: float) -> str:
    all_samples = [sample for group in results.values() for sample in group]
    cost = sum(sample.cost_usd for sample in all_samples)
    models = sorted({model for sample in all_samples for model in sample.models})
    errors = sum(1 for sample in all_samples if sample.error)
    lines = [
        f"# Polaris live eval, {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- Runs per case: {runs}",
        f"- Commit: {_git_head()}",
        f"- claude-agent-sdk: {version('claude-agent-sdk')}",
        f"- Models seen: {', '.join(models) or 'none'}",
        f"- Cost reported by the SDK: ${cost:.4f}",
        f"- Wall time: {seconds / 60:.1f} min",
        f"- Samples that errored before scoring: {errors}",
        "",
        "Pass rate is passed / (passed + failed). n/a counts samples where the check did not apply "
        "(for example no whiteboard was drawn). Checks marked **[model judge]** are scored by one "
        "Haiku-class yes/no call; every other check is code.",
        "",
        "## Summary",
        "",
        "| Case | Rules | Check | Pass rate | n/a |",
        "|---|---|---|---|---|",
    ]
    for case in cases:
        samples = results[case.id]
        names = _check_names(samples)
        errored = sum(1 for sample in samples if sample.error)
        for name in names:
            passed, failed, na, judged = _rate(samples, name)
            scored = passed + failed
            rate = f"{passed}/{scored} ({passed / scored:.0%})" if scored else "–"
            label = f"{name} **[model judge]**" if judged else name
            lines.append(f"| {case.id} | {case.rules} | {label} | {rate} | {na} |")
        if errored:
            lines.append(f"| {case.id} | {case.rules} | sample errored | {errored}/{len(samples)} errored | |")
    lines += ["", "## Cases", ""]
    for case in cases:
        lines += [f"### {case.id}: {case.title}", "", f"Rules: {case.rules}", ""]
        for index, sample in enumerate(results[case.id], start=1):
            lines.append(f"#### Sample {index} ({sample.seconds:.0f}s, ${sample.cost_usd:.4f})")
            lines.append("")
            if sample.error:
                lines += ["Errored:", "", _quote(sample.error), ""]
            for check in sample.checks:
                mark = "n/a" if check.ok is None else ("pass" if check.ok else "FAIL")
                judged = " [model judge]" if check.judged else ""
                detail = f": {check.detail}" if check.detail else ""
                lines.append(f"- {mark}: {check.name}{judged}{detail}")
            if sample.transcript:
                lines += ["", "<details><summary>Transcript</summary>", ""]
                for label, text in sample.transcript:
                    lines += [f"{label}:", "", _quote(text), ""]
                lines += ["</details>"]
            lines.append("")
    return "\n".join(lines) + "\n"


def save(report: str, results: dict[str, list[Sample]]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = REPORT_DIR / f"{stem}.md"
    path.write_text(report, encoding="utf-8")
    raw = {
        case_id: [
            {**asdict(sample), "models": sorted(sample.models)} for sample in samples
        ]
        for case_id, samples in results.items()
    }
    (REPORT_DIR / f"{stem}.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="samples per case (default 3)")
    parser.add_argument("--cases", default="", help="comma-separated case ids (default all)")
    parser.add_argument("--jobs", type=int, default=3, help="samples run at once (default 3)")
    parser.add_argument("--list", action="store_true", help="list cases and exit")
    args = parser.parse_args()

    if args.list:
        for case in CASES:
            print(f"{case.id:15} {case.rules:22} {case.title}")
        return 0
    wanted = {item.strip() for item in args.cases.split(",") if item.strip()}
    unknown = wanted - {case.id for case in CASES}
    if unknown:
        parser.error(f"unknown case ids: {', '.join(sorted(unknown))}")
    cases = [case for case in CASES if not wanted or case.id in wanted]
    if args.runs < 1 or args.jobs < 1:
        parser.error("--runs and --jobs must be at least 1")

    try:
        assert_claude_login()
    except ApiKeyPresent as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f"Running {len(cases)} case(s) x {args.runs} run(s), {args.jobs} at once.", flush=True)
    started = time.monotonic()
    try:
        results = asyncio.run(run_all(cases, args.runs, args.jobs))
    except ApiKeyPresent as exc:
        print(exc, file=sys.stderr)
        return 2
    report = render(cases, results, args.runs, time.monotonic() - started)
    path = save(report, results)
    print(f"Report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
