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
from polaris.tool_policy import DISALLOWED_TOOLS
from polaris.models import Fact, FactChange, Turn
from polaris.profile import FACT_BASES, FACT_KINDS, ProfilePassFailed

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
                    "id": {"type": "string"},
                    "kind": {"type": "string", "enum": list(FACT_KINDS)},
                    "text": {"type": "string"},
                    "basis": {"type": "string", "enum": list(FACT_BASES)},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["action", "reason"],
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
        "Return the fact changes that make the profile true now.\n"
        "Do not teach. Do not draw. Do not create a quiz.\n"
        "\n"
        "A fact is one short claim about the learner, in the third person, "
        "under 20 words, that helps teach them later.\n"
        "Each fact has one kind:\n"
        "- goal: the subject, course, exam, or deadline they are working toward\n"
        "- taught: how they want to be taught (pace, examples, drawings, step by step)\n"
        "- struggle: where they struggle; name the idea and the mistake\n"
        "- can_do: what they showed they can already do\n"
        "- milestone: they understood a concept; only when the session shows it, "
        "such as a correct quiz answer or explaining it back in their own words\n"
        "Each fact has one basis: stated (the learner said it), observed (their "
        "answers or drawings show it), or inferred (you read it between the lines).\n"
        "\n"
        "Never store:\n"
        "- a passing mood or state, such as tired today or bored\n"
        "- health, religion, politics, sexuality, money, or details about other "
        "people, unless the learner states it and asks Polaris to teach with it in mind\n"
        "- anything the learner asked Polaris not to remember\n"
        "- what a reply taught, unless the learner showed they understood it\n"
        "- a guess from one slip; one wrong answer is a struggle only when "
        "their own words or a second mistake back it\n"
        "\n"
        "Send fact changes as ADD, UPDATE, DELETE, or IGNORE.\n"
        "UPDATE, DELETE, and IGNORE name a stored fact by its id, such as F2. "
        "Use only ids from the list. A change that names no stored fact is refused.\n"
        "A fact already stored is not added again. A repeat is UPDATE or IGNORE, "
        "even when the learner words it differently.\n"
        "UPDATE a stored fact when the session corrects or sharpens it.\n"
        "DELETE a stored fact when the session shows it is no longer true, "
        "such as a struggle they now handle correctly.\n"
        "An unsorted fact has no kind yet. When the session makes its kind clear, "
        "UPDATE it with that kind.\n"
        "Every change cites the turns it rests on, such as T3, in evidence, "
        "and says why in reason.\n"
        "When nothing in the session is worth storing, return no changes.\n"
    )


def label_facts(facts: Sequence[Fact]) -> dict[str, Fact]:
    """Short ids the pass names facts by. Code maps them back to stored ids."""

    return {f"F{index}": fact for index, fact in enumerate(facts, start=1)}


def label_turns(turns: Sequence[Turn]) -> dict[str, Turn]:
    return {f"T{index}": turn for index, turn in enumerate(turns, start=1)}


def session_prompt(facts: Sequence[Fact], turns: Sequence[Turn]) -> str:
    lines = ["Current profile facts:"]
    if facts:
        lines.extend(
            f"- {label} [{fact.kind}, {fact.basis}, updated {fact.updated_at[:10]}] "
            f"{fact.text}"
            for label, fact in label_facts(facts).items()
        )
    else:
        lines.append("- (no facts yet)")
    lines.append("")
    lines.append("Session turns:")
    if not turns:
        lines.append("(none)")
    else:
        for label, turn in label_turns(turns).items():
            lines.append(f"{label} Learner: {turn.learner_message}")
            lines.append(f"{label} Polaris: {turn.reply}")
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
        disallowed_tools=DISALLOWED_TOOLS,
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )


def parse_changes(
    data: object,
    facts: dict[str, Fact] | None = None,
    turns: dict[str, Turn] | None = None,
) -> tuple[FactChange, ...]:
    """Read the pass output. Short ids become stored ids; an unknown id is kept
    as given so code refuses it instead of guessing."""

    if not isinstance(data, dict):
        return ()
    raw = data.get("changes")
    if not isinstance(raw, list):
        return ()
    facts = facts or {}
    turns = turns or {}
    parsed: list[FactChange] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        action = item.get("action")
        if not isinstance(action, str):
            continue
        label = _optional_str(item.get("id"))
        fact = facts.get(label) if label is not None else None
        evidence = item.get("evidence")
        turn_ids: list[str] = []
        if isinstance(evidence, list):
            for name in evidence:
                turn = turns.get(name) if isinstance(name, str) else None
                if turn is not None and turn.id is not None:
                    turn_ids.append(turn.id)
        parsed.append(
            FactChange(
                action=action.strip().upper(),
                text=_optional_str(item.get("text")) or "",
                id=fact.id if fact is not None else label,
                kind=_optional_str(item.get("kind")),
                basis=_optional_str(item.get("basis")),
                evidence=tuple(turn_ids),
                reason=_optional_str(item.get("reason")) or "",
            )
        )
    return tuple(parsed)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


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
        self, *, turns: Sequence[Turn], facts: Sequence[Fact]
    ) -> tuple[FactChange, ...]:
        options = profile_pass_options(cwd=self.work_dir)
        prompt = session_prompt(facts, turns)
        try:
            messages = await self._collect(prompt, options)
        except Exception as exc:
            raise ProfilePassFailed("The profile pass could not run.") from exc
        result: ResultMessage | None = None
        for message in messages:
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if isinstance(message, ResultMessage):
                result = message
        if result is None or result.subtype != "success":
            raise ProfilePassFailed("The profile pass returned no result.")
        if not isinstance(result.structured_output, dict):
            raise ProfilePassFailed("The profile pass returned no changes object.")
        return parse_changes(
            result.structured_output, label_facts(facts), label_turns(turns)
        )

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
