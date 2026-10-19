"""Bounded background work [AN-25]: at most N at once, the rest wait in order.

The one-shot Claude calls (the profile pass and the session title) share a
queue; the key check, which a reply waits on, has its own.
"""

import asyncio
import functools
import threading

import pytest

from polaris.work_queue import CLAUDE_CALLS, TURN_CALLS, WorkQueue, run_claude_call


def test_no_more_than_the_limit_runs_at_once():
    work = WorkQueue("test", workers=2)
    gate = threading.Event()
    lock = threading.Lock()
    running = 0
    peak = 0

    def job() -> None:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        gate.wait(5)
        with lock:
            running -= 1

    for _ in range(5):
        work.submit(job)
    assert not work.has_free_worker()

    gate.set()
    assert work.wait(5)
    assert peak == 2
    assert work.has_free_worker()


def test_waiting_work_starts_in_the_order_it_came():
    work = WorkQueue("test", workers=1)
    started: list[int] = []
    for n in range(5):
        work.submit(functools.partial(started.append, n))

    assert work.wait(5)
    assert started == [0, 1, 2, 3, 4]


def test_work_that_raises_does_not_stop_the_queue():
    work = WorkQueue("test", workers=1)
    ran: list[str] = []

    def broken() -> None:
        raise RuntimeError("boom")

    work.submit(broken)
    work.submit(functools.partial(ran.append, "after"))

    assert work.wait(5)
    assert ran == ["after"]


def test_a_queue_needs_a_worker():
    with pytest.raises(ValueError):
        WorkQueue("test", workers=0)


def test_a_claude_call_returns_its_result_or_raises_its_error():
    async def answer() -> int:
        return 42

    async def broken() -> int:
        raise ValueError("no answer")

    async def main() -> None:
        assert await run_claude_call(answer) == 42
        with pytest.raises(ValueError, match="no answer"):
            await run_claude_call(broken)

    asyncio.run(main())


def test_a_claude_call_runs_off_the_caller_loop():
    async def which_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    async def main() -> None:
        assert await run_claude_call(which_loop) is not asyncio.get_running_loop()

    asyncio.run(main())


def test_a_claude_call_runs_on_the_queue_it_is_given():
    own = WorkQueue("test-own", workers=1)

    async def thread_name() -> str:
        return threading.current_thread().name

    async def main() -> None:
        assert (await run_claude_call(thread_name, own)).startswith("test-own")

    asyncio.run(main())


def test_a_turn_call_does_not_wait_behind_busy_claude_calls():
    gate = threading.Event()
    for _ in range(CLAUDE_CALLS.workers):
        CLAUDE_CALLS.submit(functools.partial(gate.wait, 5))

    async def answer() -> int:
        return 42

    async def main() -> None:
        assert await asyncio.wait_for(run_claude_call(answer, TURN_CALLS), 2) == 42

    try:
        asyncio.run(main())
    finally:
        gate.set()
        assert CLAUDE_CALLS.wait(5)
