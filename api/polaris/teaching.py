"""Teaching replies through the Claude Agent SDK.

Streaming input (ClaudeSDKClient) is the mode the SDK documents for a chat
UI. include_partial_messages yields StreamEvent text deltas as the reply is
produced. A custom system prompt is the documented choice for a non-coding
agent. tools=[] disables built-in tools. setting_sources=[] and skills=[]
keep filesystem settings and skills out. verbatim_prompts sends the
assembled profile and earlier turns without @path expansion.

Profile facts go in the turn prompt only. The system prompt is fixed when
the client connects, so a later change to the profile stays in the turn.
If the stream stops before a ResultMessage, the client is disconnected.
Otherwise the unread tail would be returned as the next reply. interrupt()
does not clear that buffer (Python SDK reference, "Using interrupts").
Disconnecting drops the client instead of interrupting and draining.
"""

import contextlib
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    SystemMessage,
)

from polaris.agent import ReplyResult
from polaris.login import ApiKeyPresent, reject_api_key_credential
from polaris.models import Profile, Turn

_MISSING_PROFILE = (
    "Ask for what the profile is missing: "
    "how they want to be taught, what they can already do, and where they struggle. "
    "Do not teach the topic yet."
)


class TeachingFailed(RuntimeError):
    """The agent finished without a successful reply."""


def format_facts(profile: Profile) -> str:
    if not profile.facts:
        return "- (no facts yet)"
    return "\n".join(f"- {fact}" for fact in profile.facts)


def teaching_prompt() -> str:
    return (
        "You are Polaris. You teach one learner in a conversation.\n"
        "The profile facts for a reply are in that turn.\n"
        "When the turn lists no facts:\n"
        f"{_MISSING_PROFILE}\n"
        "When the turn lists facts, teach the topic in the learner message using those facts.\n"
        "Do not store, update, or delete profile facts.\n"
    )


def turn_prompt(
    profile: Profile,
    learner_message: str,
    prior_turns: Sequence[Turn] = (),
) -> str:
    lines = [
        "Profile facts, read for this reply:",
        format_facts(profile),
    ]
    if not profile.facts:
        lines.append(_MISSING_PROFILE)
    if prior_turns:
        lines.append("")
        lines.append("Earlier turns:")
        for turn in prior_turns:
            lines.append(f"Learner: {turn.learner_message}")
            lines.append(f"Polaris: {turn.reply}")
    lines.append("")
    lines.append("Learner message:")
    lines.append(learner_message)
    return "\n".join(lines)


def teaching_options(*, cwd: Path) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=teaching_prompt(),
        tools=[],
        skills=[],
        setting_sources=[],
        strict_mcp_config=True,
        mcp_servers={},
        include_partial_messages=True,
        verbatim_prompts=True,
        permission_mode="dontAsk",
        max_turns=1,
        cwd=cwd,
    )


def text_delta(message: StreamEvent) -> str:
    event = message.event
    if event.get("type") != "content_block_delta":
        return ""
    delta = event.get("delta", {})
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return ""
    text = delta.get("text", "")
    return text if isinstance(text, str) else ""


@dataclass
class ReplyWatch:
    """Pull learner-visible text out of one receive_response() stream."""

    sdk_session_id: str | None = None
    reached_result: bool = False

    async def text(self, messages: AsyncIterator[object]) -> AsyncIterator[str]:
        saw_delta = False
        async for message in messages:
            if isinstance(message, SystemMessage) and message.subtype == "init":
                source = message.data.get("apiKeySource")
                if isinstance(source, str) and source:
                    reject_api_key_credential(source)
                continue
            if isinstance(message, StreamEvent):
                chunk = text_delta(message)
                if chunk:
                    saw_delta = True
                    yield chunk
                continue
            if isinstance(message, ResultMessage):
                self.sdk_session_id = message.session_id
                self.reached_result = True
                if message.is_error or message.subtype != "success":
                    detail = message.result or ""
                    if not detail and message.errors:
                        detail = ", ".join(message.errors)
                    raise TeachingFailed(detail or "The reply failed.")
                if not saw_delta and message.result:
                    yield message.result


ClientFactory = Callable[[ClaudeAgentOptions], Any]


def _default_client(options: ClaudeAgentOptions) -> ClaudeSDKClient:
    return ClaudeSDKClient(options)


class ClaudeTeachingAgent:
    """One ClaudeSDKClient per open Polaris session. Disconnect when the learner leaves."""

    def __init__(
        self,
        work_dir: Path,
        client_factory: ClientFactory = _default_client,
    ) -> None:
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._client_factory = client_factory
        self._clients: dict[str, Any] = {}

    async def reply(
        self,
        *,
        session_id: str,
        profile: Profile,
        learner_message: str,
        prior_turns: Sequence[Turn],
        sdk_session_id: str | None,
    ) -> AsyncIterator[str | ReplyResult]:
        client, include_transcript = await self._ensure_client(
            session_id,
            sdk_session_id,
            prior_turns,
        )
        prompt = turn_prompt(
            profile,
            learner_message,
            prior_turns if include_transcript else (),
        )
        await client.query(prompt)
        watch = ReplyWatch()
        try:
            async for chunk in watch.text(client.receive_response()):
                yield chunk
        finally:
            if not watch.reached_result:
                await self.close_session(session_id)
        if watch.reached_result:
            yield ReplyResult(sdk_session_id=watch.sdk_session_id)

    async def close_session(self, session_id: str) -> None:
        client = self._clients.pop(session_id, None)
        if client is not None:
            await client.disconnect()

    async def close_all(self) -> None:
        for session_id in list(self._clients):
            await self.close_session(session_id)

    async def _ensure_client(
        self,
        session_id: str,
        sdk_session_id: str | None,
        prior_turns: Sequence[Turn],
    ) -> tuple[Any, bool]:
        existing = self._clients.get(session_id)
        if existing is not None:
            return existing, False
        options = teaching_options(cwd=self.work_dir)
        include_transcript = False
        if sdk_session_id:
            options = replace(options, resume=sdk_session_id)
        elif prior_turns:
            include_transcript = True
        client = self._client_factory(options)
        try:
            await client.connect()
        except Exception:
            with contextlib.suppress(Exception):
                await client.disconnect()
            raise
        self._clients[session_id] = client
        return client, include_transcript
