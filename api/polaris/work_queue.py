"""Bounded background work: a queue served by a fixed number of threads.

Animation jobs run on one per app (AN-01), so only a few write and render at
once and the rest wait their turn in order. The one-shot Claude calls made
off the turn (the profile pass and the session title) share ``CLAUDE_CALLS``,
so several sessions ending together do not start several Claude CLIs at once.
The key check runs inside a turn, so it has ``TURN_CALLS`` and never waits
behind them.

The threads are daemons. Work still queued when Polaris stops is dropped; an
animation job left that way is failed at the next start (AN-24).
"""

from __future__ import annotations

import asyncio
import functools
import queue
import sys
import threading
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def new_cli_loop() -> asyncio.AbstractEventLoop:
    """A loop that can spawn the Claude CLI. On Windows that is a ProactorEventLoop."""

    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


class WorkQueue:
    """Runs submitted work in order, at most ``workers`` at a time."""

    def __init__(self, name: str, workers: int) -> None:
        if workers < 1:
            raise ValueError("A work queue needs at least one worker.")
        self.name = name
        self.workers = workers
        self._queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self._lock = threading.Condition()
        self._threads = 0
        # Submitted and not yet finished: running plus waiting.
        self._in_flight = 0

    def has_free_worker(self) -> bool:
        """Whether work submitted now would start at once rather than wait."""

        with self._lock:
            return self._in_flight < self.workers

    def submit(self, work: Callable[[], None]) -> None:
        """Queue ``work``. It reports its own failures; an exception is dropped."""

        with self._lock:
            self._in_flight += 1
            if self._threads < min(self.workers, self._in_flight):
                self._threads += 1
                threading.Thread(
                    target=self._serve,
                    name=f"{self.name}-{self._threads}",
                    daemon=True,
                ).start()
        self._queue.put(work)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until all submitted work has finished. False on timeout."""

        with self._lock:
            return self._lock.wait_for(lambda: self._in_flight == 0, timeout)

    def _serve(self) -> None:
        while True:
            work = self._queue.get()
            try:
                work()
            except Exception:
                pass
            finally:
                with self._lock:
                    self._in_flight -= 1
                    self._lock.notify_all()


# Two at a time, so a title is not held up by a long profile pass alone.
CLAUDE_CALLS = WorkQueue("polaris-claude-call", workers=2)
# Calls a reply waits on.
TURN_CALLS = WorkQueue("polaris-turn-call", workers=2)


async def run_claude_call(
    make: Callable[[], Awaitable[T]], work: WorkQueue = CLAUDE_CALLS
) -> T:
    """Run a one-shot Claude call on ``work`` and await its result.

    ``make`` builds the coroutine on the worker's own loop, one that can spawn
    the Claude CLI even when the caller's loop cannot.
    """

    caller = asyncio.get_running_loop()
    future: asyncio.Future[T] = caller.create_future()

    def settle(outcome: Callable[[], None]) -> None:
        try:
            caller.call_soon_threadsafe(lambda: future.done() or outcome())
        except RuntimeError:
            pass  # The caller's loop closed while the call ran.

    def call() -> None:
        loop = new_cli_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(make())
        except BaseException as exc:
            settle(functools.partial(future.set_exception, exc))
        else:
            settle(functools.partial(future.set_result, result))
        finally:
            # Close a query stream left open by an error, as asyncio.run does.
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

    work.submit(call)
    return await future
