"""The router picks Manim for maths and heavy graphs, Lottie for the rest [AN-21].

The evaluation call is covered with a fake query; the keyword fallback and
the chat worker's use of the chosen writer are covered without Claude.
"""

import asyncio
import json
from pathlib import Path

from claude_agent_sdk import ResultMessage

from polaris.animation import READY
from polaris.animation_router import (
    DEFAULT_ROUTER_MODEL,
    LOTTIE,
    MANIM,
    ROUTE_FILE,
    ROUTE_SCHEMA,
    AnimationRouter,
    choose_engine,
    keyword_route,
)
from test_animation import (
    AnimationJobStub,
    FakeWriter,
    _animating_client,
    _good,
    _job_from_events,
)
from test_chat import make_client, post_turn  # noqa: F401 - fixture


def _answer(engine: str | None, reason: str = "Because.") -> ResultMessage:
    output = None if engine is None else {"engine": engine, "reason": reason}
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="router-1",
        structured_output=output,
    )


def _fake_query(engine: str | None, seen: list | None = None):
    async def fake_query(*, prompt, options):
        if seen is not None:
            seen.append((prompt, options))
        yield _answer(engine)

    return fake_query


class UnusedWriter:
    engine = "manim"

    async def write(self, *args, **kwargs):
        raise AssertionError("The router chose the other writer.")


def test_the_model_picks_the_engine(tmp_path: Path):
    seen: list = []
    route = asyncio.run(
        choose_engine(
            "Show the derivative as the slope of a tangent line.",
            "What is a derivative?",
            cwd=tmp_path,
            query_fn=_fake_query(MANIM, seen),
        )
    )

    assert route.engine == MANIM and route.by == "model"
    prompt, options = seen[0]
    assert "What is a derivative?" in prompt
    assert "slope of a tangent line" in prompt
    assert options.tools == [] and options.allowed_tools == []
    assert options.setting_sources == []
    assert options.output_format == {"type": "json_schema", "schema": ROUTE_SCHEMA}
    assert options.model == DEFAULT_ROUTER_MODEL


def test_a_failed_evaluation_falls_back_to_keywords(tmp_path: Path):
    async def broken_query(*, prompt, options):
        raise RuntimeError("The CLI is not there.")
        yield  # pragma: no cover - makes this an async generator

    maths = asyncio.run(
        choose_engine("Integrate x^2 from 0 to 1.", cwd=tmp_path, query_fn=broken_query)
    )
    story = asyncio.run(
        choose_engine("How a letter travels through the post.", cwd=tmp_path, query_fn=_fake_query(None))
    )

    assert (maths.engine, maths.by) == (MANIM, "keywords")
    assert (story.engine, story.by) == (LOTTIE, "keywords")


def test_keywords_send_maths_and_heavy_graphs_to_manim():
    for text in (
        "Solve the quadratic equation x² - 5x + 6 = 0.",
        "Plot sin(x) and cos(x) on the same axes.",
        "Run Dijkstra's shortest path on a weighted graph.",
        "Prove the Pythagorean theorem with squares on each side.",
    ):
        assert keyword_route(text).engine == MANIM, text
    for text in (
        "How the heart pumps blood around the body.",
        "The water cycle: evaporation, clouds, and rain.",
        "Show binary search halving a sorted list of cards.",
        "How a small business grows a customer base.",
    ):
        assert keyword_route(text).engine == LOTTIE, text


def test_the_job_uses_the_writer_the_router_chose(make_client, tmp_path: Path):  # noqa: F811
    """Scenario: a non-maths request is made with Lottie [AN-21]."""

    lottie = FakeWriter([_good()])
    router = AnimationRouter(
        manim=UnusedWriter(),
        lottie=lottie,
        work_dir=tmp_path,
        query_fn=_fake_query(LOTTIE),
    )
    client, app_chat = _animating_client(make_client, router, AnimationJobStub())
    session = client.post("/api/sessions").json()
    job = _job_from_events(post_turn(client, session["id"], "Show me fractions with pizza."))
    app_chat.wait_for_animation_jobs(10)

    assert len(lottie.calls) == 1
    status = client.get(f"/api/sessions/{session['id']}/jobs/{job['id']}").json()
    assert status["status"] == READY
    route = json.loads((app_chat.animation_work_dir(job["id"]) / ROUTE_FILE).read_text())
    assert route["engine"] == LOTTIE and route["by"] == "model"
