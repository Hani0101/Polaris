"""Session title writer (CH-20, CH-21). A Haiku-class model reads the first
message of a session and returns a short title. It sees nothing else.

Uses one-shot query() with a plain-text result (streaming-vs-single-mode).
model="haiku" (configuration, model aliases). setting_sources=[] and
skills=[] keep filesystem settings and skills out; verbatim_prompts sends the
message without @path expansion. The query runs on the shared queue of
one-shot Claude calls, on a loop that can spawn the Claude CLI, as the
profile pass does.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Protocol

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)

from polaris.login import reject_api_key_credential
from polaris.tool_policy import DISALLOWED_TOOLS
from polaris.work_queue import run_claude_call

QueryFn = Callable[..., AsyncIterator[object]]

MAX_TITLE_LENGTH = 80

TITLE_PROMPT = (
    "You name a conversation from the learner's first message. "
    "Reply with the title only: plain text, at most six words, in the language "
    "of the message, with no quotes, no Markdown, and no ending punctuation. "
    "Name the topic. Do not answer the message."
)


class TitleWriter(Protocol):
    async def write(self, message: str) -> str: ...


class TitleFailed(Exception):
    pass


def clean_title(raw: str) -> str:
    """The first non-empty line, without quotes or Markdown, cut to the limit."""

    for line in raw.splitlines():
        text = re.sub(r"[*_`#>]+", "", line).strip().strip("\"'“”‘’").strip()
        if text:
            return text[:MAX_TITLE_LENGTH].rstrip()
    return ""


def title_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=TITLE_PROMPT,
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        model="haiku",
        disallowed_tools=DISALLOWED_TOOLS,
        permission_mode="dontAsk",
        max_turns=1,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )


class ClaudeTitleWriter:
    """One-shot Haiku call over the first message of a session."""

    def __init__(self, work_dir: Path, query_fn: QueryFn = query) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn

    async def write(self, message: str) -> str:
        options = title_options(cwd=self.work_dir)
        try:
            messages = await self._collect(message, options)
        except Exception as exc:
            raise TitleFailed("The title could not be written.") from exc
        result: ResultMessage | None = None
        for item in messages:
            if isinstance(item, SystemMessage) and item.subtype == "init":
                source = item.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if isinstance(item, ResultMessage):
                result = item
        if result is None or result.subtype != "success" or not result.result:
            raise TitleFailed("The title writer returned no result.")
        return clean_title(result.result)

    async def _collect(self, prompt: str, options: ClaudeAgentOptions) -> list[object]:
        return await run_claude_call(lambda: self._gather(prompt, options))

    async def _gather(self, prompt: str, options: ClaudeAgentOptions) -> list[object]:
        return [item async for item in self._query_fn(prompt=prompt, options=options)]
