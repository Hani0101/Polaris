"""The animation writer. It writes the code for one animation job.

It runs outside the learner's turn, so the chat stays usable (AN-01). The
teaching agent only starts the job with a brief. This writer turns the
brief into Python that the sandbox runs (AN-04). On a fix it receives the
code that failed and the sandbox error (AN-05).

Uses one-shot query() with structured output (streaming-vs-single-mode,
structured-outputs), like the profile pass. tools=[], setting_sources=[]
and skills=[] keep built-in tools, filesystem settings and skills out.
verbatim_prompts sends the brief without @path expansion. The caller runs
this on a loop that can spawn the Claude CLI (a ProactorEventLoop on
Windows).
"""

from __future__ import annotations

import asyncio
import sys
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

QueryFn = Callable[..., AsyncIterator[object]]

CODE_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string"}},
    "required": ["code"],
    "additionalProperties": False,
}


def new_cli_loop() -> asyncio.AbstractEventLoop:
    """A loop that can spawn the Claude CLI. On Windows that is a ProactorEventLoop."""

    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


class WriterFailed(RuntimeError):
    """The writer returned no code."""


class AnimationWriter(Protocol):
    async def write(
        self, brief: str, *, failed_code: str | None, error: str | None
    ) -> str:
        """Return Python code for the sandbox. A fix receives the code that failed and its error."""


def animation_writer_prompt() -> str:
    return (
        "You write the code for one Polaris animation.\n"
        "An animation is a moving explanation a learner watches in the browser.\n"
        "Return one Python 3.13 script in the code field.\n"
        "The script runs in a sandbox with the standard library only.\n"
        "It has no network. It cannot start other programs or load native code.\n"
        "It has a time limit, so it must finish in a few seconds.\n"
        "The script must write one file, animation.html, in the working directory.\n"
        "animation.html is a complete, self-contained page.\n"
        "Use inline SVG, CSS, and JavaScript. Load nothing from a URL, "
        "because the page cannot reach the network.\n"
        "The animation plays on its own, loops or can be replayed, and has "
        "a play/pause button.\n"
        "Show short captions that explain each step in plain words.\n"
        "Use a dark background (#0f1115) with light text and strong contrast.\n"
        "Fit any width from 320px up, with no horizontal scroll.\n"
        "When prefers-reduced-motion is set, do not play on your own: show the "
        "first step and let the learner step through with a Next button, "
        "without movement.\n"
        "Keep it focused on the brief. Do not teach anything the brief does not ask for.\n"
    )


def writer_prompt(
    brief: str, *, failed_code: str | None = None, error: str | None = None
) -> str:
    lines = ["Brief:", brief.strip()]
    if error is not None:
        lines += [
            "",
            "Your last script failed in the sandbox. Fix it and return the whole script.",
            "",
            "Last script:",
            failed_code or "(missing)",
            "",
            "Sandbox error:",
            error,
        ]
    return "\n".join(lines)


def animation_writer_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=animation_writer_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        output_format={"type": "json_schema", "schema": CODE_SCHEMA},
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )


class ClaudeAnimationWriter:
    """One-shot query per run: the first script, then each fix."""

    def __init__(self, work_dir: Path, query_fn: QueryFn = query) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._query_fn = query_fn

    async def write(
        self, brief: str, *, failed_code: str | None, error: str | None
    ) -> str:
        options = animation_writer_options(cwd=self.work_dir)
        prompt = writer_prompt(brief, failed_code=failed_code, error=error)
        code: str | None = None
        # Read the whole stream so the CLI process ends before this returns.
        async for message in self._query_fn(prompt=prompt, options=options):
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
            if (
                isinstance(message, ResultMessage)
                and message.subtype == "success"
                and isinstance(message.structured_output, dict)
            ):
                found = message.structured_output.get("code")
                if isinstance(found, str) and found.strip():
                    code = found
        if code is None:
            raise WriterFailed("The animation writer returned no code.")
        return code
