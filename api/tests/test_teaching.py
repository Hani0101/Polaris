"""The teaching agent follows the installed Claude Agent SDK.

These tests never start the Claude CLI. A stand-in client records the options
and yields the message types the streaming-output doc describes.
"""

import asyncio
from pathlib import Path

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
)

from polaris.login import ApiKeyPresent
from polaris.models import Profile, Turn
from polaris.agent import ReplyResult
from polaris.teaching import (
    ClaudeTeachingAgent,
    TeachingFailed,
    teaching_options,
    turn_prompt,
)


def result(session_id: str = "sdk-1", **overrides) -> ResultMessage:
    fields = {
        "subtype": "success",
        "duration_ms": 1,
        "duration_api_ms": 1,
        "is_error": False,
        "num_turns": 1,
        "session_id": session_id,
        "result": None,
        "errors": None,
    }
    fields.update(overrides)
    return ResultMessage(**fields)


def delta(text: str) -> StreamEvent:
    return StreamEvent(
        uuid="event-1",
        session_id="sdk-1",
        event={
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": text},
        },
    )


class FakeClient:
    def __init__(self, options, messages) -> None:
        self.options = options
        self.messages = messages
        self.prompts: list[str] = []
        self.disconnected = False

    async def connect(self) -> None:
        return None

    async def query(self, prompt: str, session_id: str = "default") -> None:
        del session_id
        self.prompts.append(prompt)

    async def receive_response(self):
        for message in self.messages:
            yield message

    async def disconnect(self) -> None:
        self.disconnected = True


def test_options_match_the_sdk_docs(tmp_path: Path):
    options = teaching_options(cwd=tmp_path)

    assert options.tools == []
    assert options.skills == []
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.mcp_servers == {}
    assert options.include_partial_messages is True
    assert options.verbatim_prompts is True
    assert options.permission_mode == "dontAsk"
    assert options.max_turns == 1
    assert options.cwd == tmp_path
    assert isinstance(options.system_prompt, str)
    prompt = options.system_prompt
    assert "struggles with fractions" not in prompt
    assert "(no facts yet)" not in prompt
    assert "Do not ask the learner to fill in a profile." not in prompt
    assert "teach anyway" not in prompt
    assert "Do not store, update, or delete profile facts." in prompt
    assert "When the turn lists no facts" in prompt
    assert "Do not teach the topic yet." in prompt


def _agent(tmp_path: Path, messages, created: list[FakeClient]) -> ClaudeTeachingAgent:
    def factory(options):
        client = FakeClient(options, messages)
        created.append(client)
        return client

    return ClaudeTeachingAgent(tmp_path, client_factory=factory)


async def _collect(agent: ClaudeTeachingAgent, **kwargs) -> tuple[str, ReplyResult]:
    parts: list[str] = []
    done: ReplyResult | None = None
    async for item in agent.reply(
        session_id=kwargs.get("session_id", "session-1"),
        profile=kwargs.get("profile", Profile(("struggles with fractions",))),
        learner_message=kwargs.get("learner_message", "How do I add fractions?"),
        prior_turns=kwargs.get("prior_turns", ()),
        sdk_session_id=kwargs.get("sdk_session_id"),
    ):
        if isinstance(item, ReplyResult):
            done = item
        else:
            parts.append(item)
    if done is None:
        raise AssertionError("The reply did not reach a result.")
    return "".join(parts), done


def test_text_deltas_stream_without_duplicating_the_finished_block(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(
        tmp_path,
        [
            SystemMessage(subtype="init", data={"apiKeySource": "none"}),
            delta("Hi"),
            AssistantMessage(content=[TextBlock(text="Hi")], model="test"),
            result(result="Hi"),
        ],
        created,
    )

    text, done = asyncio.run(_collect(agent))

    assert text == "Hi"
    assert done.sdk_session_id == "sdk-1"
    assert "struggles with fractions" in created[0].prompts[0]
    assert "Profile facts, read for this reply:" in created[0].prompts[0]
    assert "Do not teach the topic yet." not in created[0].prompts[0]
    assert "struggles with fractions" not in created[0].options.system_prompt


def test_a_later_reply_on_the_same_client_reads_the_profile_again(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Ok"), result()], created)

    async def twice():
        await _collect(agent, profile=Profile(("struggles with fractions",)))
        await _collect(
            agent,
            profile=Profile(("struggles with graphs",)),
            learner_message="What is a vertex?",
            prior_turns=(Turn("earlier", "reply"),),
        )

    asyncio.run(twice())

    assert len(created) == 1
    assert "struggles with fractions" in created[0].prompts[0]
    assert "struggles with graphs" in created[0].prompts[1]
    assert "Earlier turns" not in created[0].prompts[1]
    assert "What is a vertex?" in created[0].prompts[1]
    assert "struggles with fractions" not in created[0].options.system_prompt
    assert "struggles with graphs" not in created[0].options.system_prompt


def test_reopen_without_an_sdk_session_includes_earlier_turns(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Ok"), result()], created)

    asyncio.run(
        _collect(
            agent,
            prior_turns=(Turn("Remember this", "A fraction is a part of a whole."),),
            sdk_session_id=None,
        )
    )

    prompt = created[0].prompts[0]
    assert "Earlier turns:" in prompt
    assert "Remember this" in prompt
    assert created[0].options.resume is None


def test_resume_uses_the_stored_sdk_session(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Ok"), result()], created)

    asyncio.run(
        _collect(
            agent,
            prior_turns=(Turn("Remember this", "Kept."),),
            sdk_session_id="sdk-9",
        )
    )

    assert created[0].options.resume == "sdk-9"
    assert "Earlier turns" not in created[0].prompts[0]


def test_tool_input_deltas_are_not_shown_as_reply_text(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(
        tmp_path,
        [
            StreamEvent(
                uuid="event-2",
                session_id="sdk-1",
                event={
                    "type": "content_block_delta",
                    "delta": {"type": "input_json_delta", "partial_json": "{\"a\":"},
                },
            ),
            delta("Shown"),
            result(),
        ],
        created,
    )

    text, _done = asyncio.run(_collect(agent))
    assert text == "Shown"


def test_result_text_is_used_when_no_deltas_arrive(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [result(result="Whole reply")], created)
    text, _done = asyncio.run(_collect(agent))
    assert text == "Whole reply"


def test_a_failed_result_raises(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(
        tmp_path,
        [result(subtype="error_during_execution", is_error=True, result="boom")],
        created,
    )
    with pytest.raises(TeachingFailed, match="boom"):
        asyncio.run(_collect(agent))
    assert created[0].disconnected is False


@pytest.mark.parametrize(
    "source",
    ["ANTHROPIC_API_KEY", "apiKeyHelper", "/login managed key"],
)
def test_an_api_key_credential_stops_the_reply(tmp_path: Path, source: str):
    created: list[FakeClient] = []
    agent = _agent(
        tmp_path,
        [
            SystemMessage(subtype="init", data={"apiKeySource": source}),
            delta("should not be shown"),
            result(),
        ],
        created,
    )

    with pytest.raises(ApiKeyPresent):
        asyncio.run(_collect(agent))
    assert created[0].disconnected is True


def test_claude_login_is_not_an_api_key(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(
        tmp_path,
        [
            SystemMessage(subtype="init", data={"apiKeySource": "none"}),
            delta("Hello"),
            result(),
        ],
        created,
    )

    text, _done = asyncio.run(_collect(agent))
    assert text == "Hello"
    assert created[0].disconnected is False


def test_an_empty_profile_asks_and_does_not_teach(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("What do you already know?"), result()], created)

    text, _done = asyncio.run(
        _collect(agent, profile=Profile(()), learner_message="What is a fraction?")
    )

    prompt = created[0].prompts[0]
    assert text == "What do you already know?"
    assert "(no facts yet)" in prompt
    assert "Do not teach the topic yet." in prompt
    assert "how they want to be taught" in prompt
    assert "What is a fraction?" in prompt
    assert "(no facts yet)" not in created[0].options.system_prompt
    assert turn_prompt(Profile(()), "What is a fraction?") == prompt


class QueuedClient:
    """Messages stay queued until a ResultMessage, like the SDK buffer."""

    def __init__(self, options, messages) -> None:
        self.options = options
        self.pending = list(messages)
        self.prompts: list[str] = []
        self.disconnected = False

    async def connect(self) -> None:
        return None

    async def query(self, prompt: str, session_id: str = "default") -> None:
        del session_id
        self.prompts.append(prompt)

    async def receive_response(self):
        while self.pending:
            message = self.pending.pop(0)
            yield message
            if isinstance(message, ResultMessage):
                return

    async def disconnect(self) -> None:
        self.disconnected = True


def test_a_dropped_stream_does_not_poison_the_next_reply(tmp_path: Path):
    created: list[QueuedClient] = []
    batches = [
        [delta("old-head"), delta("old-tail"), result(session_id="sdk-old", result="old")],
        [delta("fresh"), result(session_id="sdk-new", result="fresh")],
    ]

    def factory(options):
        client = QueuedClient(options, batches.pop(0))
        created.append(client)
        return client

    agent = ClaudeTeachingAgent(tmp_path, client_factory=factory)

    async def dropped_then_next():
        stream = agent.reply(
            session_id="session-1",
            profile=Profile(("struggles with fractions",)),
            learner_message="First",
            prior_turns=(),
            sdk_session_id=None,
        )
        first = await stream.__anext__()
        assert first == "old-head"
        await stream.aclose()
        return await _collect(agent, learner_message="Second")

    text, done = asyncio.run(dropped_then_next())

    assert text == "fresh"
    assert "old-tail" not in text
    assert done.sdk_session_id == "sdk-new"
    assert created[0].disconnected is True
    assert created[0].pending
    assert len(created) == 2
    assert "Second" in created[1].prompts[0]
    assert agent._clients["session-1"] is created[1]
