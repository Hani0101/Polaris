"""Shared pieces for the live evals.

Every sample runs in its own temporary data dir, so the learner's real
profile.json and polaris.db are never read or written. The teaching agent,
profile pass and animation writer are the real ones from polaris/. Only the
SDK client is wrapped, to record tool calls, tool results, models and cost.

A check is a code check unless it says judged=True. A judged check asks a
Haiku-class model one yes/no question about one reply, with a fixed schema.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

from polaris.chat import Chat
from polaris.login import reject_api_key_credential
from polaris.tool_policy import DISALLOWED_TOOLS
from polaris.teaching import ClaudeTeachingAgent

API_DIR = Path(__file__).resolve().parent.parent


# --- results -----------------------------------------------------------------


@dataclass
class Check:
    """One scored claim about one sample. ok is None when the check does not apply."""

    name: str
    ok: bool | None
    detail: str = ""
    judged: bool = False


@dataclass
class Sample:
    checks: list[Check] = field(default_factory=list)
    transcript: list[tuple[str, str]] = field(default_factory=list)
    cost_usd: float = 0.0
    models: set[str] = field(default_factory=set)
    error: str | None = None
    seconds: float = 0.0

    def check(
        self, name: str, ok: bool | None, detail: str = "", *, judged: bool = False
    ) -> None:
        self.checks.append(Check(name, ok, detail, judged))

    def note(self, label: str, text: str) -> None:
        self.transcript.append((label, text))


CaseRun = Callable[[Path, Sample], Awaitable[None]]


@dataclass(frozen=True)
class Case:
    id: str
    rules: str
    title: str
    run: CaseRun


# --- data dir ------------------------------------------------------------------


def real_data_dir() -> Path:
    return Path(os.environ.get("POLARIS_DATA", API_DIR / "data")).resolve()


def temp_data_dir() -> tempfile.TemporaryDirectory[str]:
    holder = tempfile.TemporaryDirectory(prefix="polaris-eval-")
    path = Path(holder.name).resolve()
    real = real_data_dir()
    if path == real or path.is_relative_to(real):
        holder.cleanup()
        raise RuntimeError(f"Eval data dir {path} is inside the real data dir {real}.")
    return holder


# --- recording ---------------------------------------------------------------


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]
    is_error: bool | None = None
    result: str = ""


@dataclass
class CallLog:
    calls: list[ToolCall] = field(default_factory=list)
    cost_usd: float = 0.0
    models: set[str] = field(default_factory=set)

    def observe(self, message: object) -> None:
        if isinstance(message, SystemMessage) and message.subtype == "init":
            source = message.data.get("apiKeySource")
            if isinstance(source, str) and source:
                reject_api_key_credential(source)
        elif isinstance(message, AssistantMessage):
            self.models.add(message.model)
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    self.calls.append(ToolCall(block.id, block.name, dict(block.input)))
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    for call in self.calls:
                        if call.id == block.tool_use_id:
                            call.is_error = bool(block.is_error)
                            call.result = _block_text(block.content)
        elif isinstance(message, ResultMessage):
            self.cost_usd += message.total_cost_usd or 0.0


def _block_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", "")) for item in content if isinstance(item, dict)
        )
    return ""


class RecordingClient:
    """ClaudeSDKClient with every received message copied into a CallLog."""

    def __init__(self, options: ClaudeAgentOptions, log: CallLog) -> None:
        self._inner = ClaudeSDKClient(options)
        self._log = log

    async def connect(self) -> None:
        await self._inner.connect()

    async def query(self, prompt: str, session_id: str = "default") -> None:
        await self._inner.query(prompt, session_id=session_id)

    async def receive_response(self) -> AsyncIterator[object]:
        async for message in self._inner.receive_response():
            self._log.observe(message)
            yield message

    async def disconnect(self) -> None:
        await self._inner.disconnect()


def recording_query(log: CallLog) -> Callable[..., AsyncIterator[object]]:
    """query() for the profile pass and animation writer, copied into a CallLog."""

    async def run(*, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[object]:
        async for message in query(prompt=prompt, options=options):
            log.observe(message)
            yield message

    return run


# --- teaching ----------------------------------------------------------------


@dataclass
class TurnRecord:
    reply: str
    artifacts: list[dict[str, Any]]
    calls: list[ToolCall]

    def calls_named(self, name: str) -> list[ToolCall]:
        return [call for call in self.calls if call.name == name]

    def artifacts_of(self, kind: str) -> list[dict[str, Any]]:
        return [item for item in self.artifacts if item.get("kind") == kind]


class TeachingRun:
    """A real Chat and ClaudeTeachingAgent in a temp data dir.

    No profile pass and no animation writer are bound, so a turn never
    writes the profile and never starts a background animation.
    """

    def __init__(self, data_dir: Path, facts: tuple[str, ...]) -> None:
        self.data_dir = data_dir
        self.log = CallLog()
        if facts:
            # Chat moves profile.json into the database on its first read.
            (data_dir / "profile.json").write_text(
                json.dumps({"facts": list(facts)}), encoding="utf-8"
            )
        self.agent = ClaudeTeachingAgent(
            data_dir / "claude-work",
            client_factory=lambda options: RecordingClient(options, self.log),
        )
        self.chat = Chat(data_dir, self.agent)
        session, _ = self.chat.start()
        self.session_id = str(session["id"])

    async def turn(self, message: str) -> TurnRecord:
        start = len(self.log.calls)
        parts: list[str] = []
        artifacts: list[dict[str, Any]] = []
        async for item in self.chat.stream_reply(self.session_id, message):
            if isinstance(item, str):
                parts.append(item)
            else:
                artifacts.append(dict(item))
        return TurnRecord("".join(parts), artifacts, self.log.calls[start:])

    async def close(self, sample: Sample) -> None:
        sample.cost_usd += self.log.cost_usd
        sample.models |= self.log.models
        try:
            await self.agent.close_all()
        finally:
            self.chat.close()


# --- model judge ---------------------------------------------------------------

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "boolean"},
        "reason": {"type": "string", "maxLength": 300},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


def judge_prompt() -> str:
    return (
        "You grade one tutoring reply against one yes/no question.\n"
        "Answer only from the text you are given.\n"
        "verdict is true only when the reply clearly meets the question.\n"
        "reason is one sentence that quotes or points at the part of the reply you used.\n"
    )


async def judge(question: str, material: str, *, cwd: Path, sample: Sample) -> tuple[bool | None, str]:
    """One Haiku-class call, one yes/no question, fixed schema. Labelled judged in the report."""

    log = CallLog()
    options = ClaudeAgentOptions(
        system_prompt=judge_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        model="haiku",
        output_format={"type": "json_schema", "schema": JUDGE_SCHEMA},
        disallowed_tools=DISALLOWED_TOOLS,
        permission_mode="dontAsk",
        max_turns=3,
        cwd=cwd,
        verbatim_prompts=True,
        allowed_tools=[],
    )
    prompt = f"Question:\n{question}\n\n{material}"
    verdict: bool | None = None
    reason = "The judge returned no verdict."
    async for message in recording_query(log)(prompt=prompt, options=options):
        if (
            isinstance(message, ResultMessage)
            and message.subtype == "success"
            and isinstance(message.structured_output, dict)
        ):
            found = message.structured_output.get("verdict")
            if isinstance(found, bool):
                verdict = found
                reason = str(message.structured_output.get("reason", ""))
    sample.cost_usd += log.cost_usd
    sample.models |= {f"judge:{model}" for model in log.models}
    return verdict, reason
