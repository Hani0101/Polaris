"""Session-end profile pass. A Haiku-class model reads the session and
returns fact changes. The teaching agent does not write the profile.

Uses one-shot query() with structured output (streaming-vs-single-mode,
structured-outputs). model="haiku" (configuration, model aliases).
setting_sources=[] and skills=[] keep filesystem settings and skills out.
verbatim_prompts sends the session text without @path expansion.
On Windows, uvicorn --reload uses SelectorEventLoop, which cannot spawn
the Claude CLI, so the query runs on a ProactorEventLoop in a worker
thread, matching the teaching client.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)

from polaris.login import reject_api_key_credential
from polaris.models import FactChange, Profile, Turn

QueryFn = Callable[..., AsyncIterator[object]]

CHANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["ADD", "UPDATE", "DELETE", "IGNORE"],
                    },
                    "fact": {"type": "string"},
                    "replaces": {"type": "string"},
                },
                "required": ["action", "fact"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["changes"],
    "additionalProperties": False,
}


def profile_pass_prompt() -> str:
    return (
        "You read one Polaris session and the current profile facts.\n"
        "Decide which facts are true now.\n"
        "A milestone is the fact that the learner understood a concept.\n"
        "Send fact changes as ADD, UPDATE, DELETE, or IGNORE.\n"
        "A fact already stored is not added again. A repeat is UPDATE or IGNORE.\n"
        "Do not teach. Do not draw. Do not create a quiz.\n"
    )


def session_prompt(profile: Profile, turns: Sequence[Turn]) -> str:
    lines = ["Current profile facts:"]
    if profile.facts:
        lines.extend(f"- {fact}" for fact in profile.facts)
    else:
        lines.append("- (no facts yet)")
    lines.append("")
    lines.append("Session turns:")
    if not turns:
        lines.append("(none)")
    else:
        for turn in turns:
            lines.append(f"Learner: {turn.learner_message}")
            lines.append(f"Polaris: {turn.reply}")
    return "\n".join(lines)


def profile_pass_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=profile_pass_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        model="haiku",
        output_format={"type": "json_schema", "schema": CHANGE_SCHEMA},
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )


def parse_changes(data: object) -> tuple[FactChange, ...]:
    if not isinstance(data, dict):
        return ()
    raw = data.get("changes")
    if not isinstance(raw, list):
        return ()
    parsed: list[FactChange] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        fact = item.get("fact")
        if not isinstance(action, str) or not isinstance(fact, str):
            continue
        replaces = item.get("replaces")
        if replaces is not None and not isinstance(replaces, str):
            replaces = None
        parsed.append(FactChange(action.strip().upper(), fact, replaces))
    return tuple(parsed)


def _off_loop_required() -> bool:
    if sys.platform != "win32":
        return False
    loop = asyncio.get_running_loop()
    return not isinstance(loop, asyncio.ProactorEventLoop)


def _cli_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


class ClaudeProfilePass:
    """One-shot Haiku pass over a session that just ended."""

    def __init__(
        self,
        work_dir: Path,
        query_fn: QueryFn = query,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn

    async def run(
        self, *, turns: Sequence[Turn], profile: Profile
    ) -> tuple[FactChange, ...]:
        options = profile_pass_options(cwd=self.work_dir)
        prompt = session_prompt(profile, turns)
        try:
            messages = await self._collect(prompt, options)
        except Exception:
            return ()
        for message in messages:
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if isinstance(message, ResultMessage):
                if message.subtype == "success" and message.structured_output:
                    return parse_changes(message.structured_output)
        return ()

    async def _collect(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> list[object]:
        if not _off_loop_required():
            return [
                message
                async for message in self._query_fn(prompt=prompt, options=options)
            ]
        return await self._collect_off_loop(prompt, options)

    async def _collect_off_loop(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> list[object]:
        loop = _cli_loop()
        caller = asyncio.get_running_loop()
        future: asyncio.Future[list[object]] = caller.create_future()

        def worker() -> None:
            asyncio.set_event_loop(loop)
            try:
                gathered = loop.run_until_complete(self._gather(prompt, options))
                caller.call_soon_threadsafe(future.set_result, gathered)
            except BaseException as exc:
                caller.call_soon_threadsafe(future.set_exception, exc)
            finally:
                loop.close()

        threading.Thread(
            target=worker, name="polaris-profile-pass", daemon=True
        ).start()
        return await future

    async def _gather(
        self, prompt: str, options: ClaudeAgentOptions
    ) -> list[object]:
        return [
            message
            async for message in self._query_fn(prompt=prompt, options=options)
        ]
