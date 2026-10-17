"""The teaching agent follows the installed Claude Agent SDK.

These tests never start the Claude CLI. A stand-in client records the options
and yields the message types the streaming-output doc describes.
"""

import asyncio
import copy
import json
from pathlib import Path

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    CLIConnectionError,
    CLINotFoundError,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
)

from polaris.chat import Chat
from polaris.login import ApiKeyPresent
from polaris.models import Pointing, Profile, Turn
from polaris.agent import ReplyResult
from polaris.key_check import KeyCheckFailed
from polaris.quiz import normalize_spec
from polaris.teaching import (
    CREATE_QUIZ_SCHEMA,
    CREATE_QUIZ_TOOL,
    DRAW_WHITEBOARD_DESCRIPTION,
    DRAW_WHITEBOARD_SCHEMA,
    DRAW_WHITEBOARD_TOOL,
    ClaudeTeachingAgent,
    TeachingFailed,
    _OffLoopClient,
    reply_error_message,
    teaching_options,
    turn_prompt,
)
from polaris.whiteboard import WHITEBOARD_TOOL_LIMITS, check_drawing, describe_whiteboard
from test_quiz import QUIZ_SPEC
from test_whiteboard import valid_whiteboard


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
    assert list(options.mcp_servers) == ["polaris"]
    assert options.allowed_tools == [CREATE_QUIZ_TOOL, DRAW_WHITEBOARD_TOOL]
    assert options.include_partial_messages is True
    assert options.verbatim_prompts is True
    assert options.permission_mode == "dontAsk"
    assert options.max_turns == 1 + WHITEBOARD_TOOL_LIMITS.max_fix_attempts + 3
    assert CREATE_QUIZ_SCHEMA["additionalProperties"] is False
    assert CREATE_QUIZ_SCHEMA["properties"]["questions"]["minItems"] == 1
    question = CREATE_QUIZ_SCHEMA["properties"]["questions"]["items"]
    assert question["additionalProperties"] is False
    choices = question["properties"]["choices"]
    assert choices["minItems"] == 2
    assert choices["items"]["additionalProperties"] is False
    assert choices["items"]["properties"]["why_wrong"]["type"] == "string"
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
    assert "Do not call create_quiz." in prompt
    assert "Do not call draw_whiteboard." in prompt
    assert "call draw_whiteboard." in prompt
    assert "Do not grade the learner's choices." in prompt
    assert "how parts connect" in DRAW_WHITEBOARD_DESCRIPTION
    assert "do not use it for a quiz" in DRAW_WHITEBOARD_DESCRIPTION
    assert "version 4" in DRAW_WHITEBOARD_DESCRIPTION
    assert "version 5" in DRAW_WHITEBOARD_DESCRIPTION
    assert "math" in DRAW_WHITEBOARD_DESCRIPTION
    assert "latex" in DRAW_WHITEBOARD_DESCRIPTION
    assert "code" in DRAW_WHITEBOARD_DESCRIPTION
    assert "Do not draw a formula or code as shapes." in DRAW_WHITEBOARD_DESCRIPTION
    assert "version 6" in DRAW_WHITEBOARD_DESCRIPTION
    assert "graph" in DRAW_WHITEBOARD_DESCRIPTION
    assert "freehand curve" in DRAW_WHITEBOARD_DESCRIPTION
    assert "version 6" in prompt
    assert "graph element" in prompt
    assert "cannot see the drawing" in DRAW_WHITEBOARD_DESCRIPTION
    assert DRAW_WHITEBOARD_SCHEMA["properties"]["description"]["type"] == "string"
    assert "[[step:step-1]]" in DRAW_WHITEBOARD_DESCRIPTION
    assert "[[step:<that step's id>]]" in prompt
    assert DRAW_WHITEBOARD_SCHEMA["type"] == "object"
    assert DRAW_WHITEBOARD_SCHEMA["additionalProperties"] is True


class FakeKeyCheck:
    """Answers without the key (QZ-12). Records what it was shown."""

    def __init__(self, answers: dict[str, str] | None = None, fail: bool = False) -> None:
        self.answers = answers if answers is not None else {"q1": "b", "q2": "b"}
        self.fail = fail
        self.seen: list[dict] = []

    async def answer(self, quiz: dict) -> dict[str, str]:
        self.seen.append(quiz)
        if self.fail:
            raise KeyCheckFailed("no answer")
        ids = [question["id"] for question in quiz["questions"]]
        return {qid: self.answers[qid] for qid in ids if qid in self.answers}


def _agent(
    tmp_path: Path,
    messages,
    created: list[FakeClient],
    key_check: FakeKeyCheck | None = None,
) -> ClaudeTeachingAgent:
    def factory(options):
        client = FakeClient(options, messages)
        created.append(client)
        return client

    return ClaudeTeachingAgent(
        tmp_path, client_factory=factory, key_check=key_check or FakeKeyCheck()
    )


async def _collect(agent: ClaudeTeachingAgent, **kwargs) -> tuple[str, ReplyResult]:
    parts: list[str] = []
    done: ReplyResult | None = None
    async for item in agent.reply(
        session_id=kwargs.get("session_id", "session-1"),
        profile=kwargs.get("profile", Profile(("struggles with fractions",))),
        learner_message=kwargs.get("learner_message", "How do I add fractions?"),
        prior_turns=kwargs.get("prior_turns", ()),
        sdk_session_id=kwargs.get("sdk_session_id"),
        whiteboards=kwargs.get("whiteboards", ()),
        pointing=kwargs.get("pointing"),
        simplify=kwargs.get("simplify"),
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


def test_the_next_turn_prompt_includes_the_learner_drawing_and_comment(tmp_path: Path):
    """WB-03: the agent input for the next turn contains the drawing and comment."""

    data = valid_whiteboard()
    box = copy.deepcopy(data["steps"][1]["elements"][0])
    box["id"] = "learner-box"
    box["author"] = "learner"
    box["position"] = {"x": 120, "y": 40}
    data["steps"][1]["elements"].append(box)
    data["comments"] = [
        {
            "id": "comment-1",
            "author": "learner",
            "text": "the left box is the whole",
            "element_id": "rect-1",
        }
    ]
    checked = check_drawing(data)
    assert checked.whiteboard is not None
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Yes."), result()], created)

    asyncio.run(
        _collect(
            agent,
            learner_message="What did I mark?",
            whiteboards=(checked.whiteboard,),
        )
    )

    prompt = created[0].prompts[0]
    assert "Whiteboards in this session:" in prompt
    assert "rectangle learner-box by learner at (120, 40)" in prompt
    assert (
        'comment comment-1 by learner about rect-1: "the left box is the whole"'
        in prompt
    )


def test_the_agent_input_names_the_pointed_at_elements(tmp_path: Path):
    """WB-08: the turn prompt names the pointed-at parts in the whiteboard text form."""

    checked = check_drawing(valid_whiteboard())
    assert checked.whiteboard is not None
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("The left box is the whole."), result()], created)

    asyncio.run(
        _collect(
            agent,
            learner_message="What are these parts?",
            whiteboards=(checked.whiteboard,),
            pointing=Pointing("wb-1", ("rect-1", "text-1")),
        )
    )

    prompt = created[0].prompts[0]
    pointed, _, _message = prompt.partition("Learner message:")
    pointed = pointed.split("The learner pointed at these parts", 1)[1]
    assert pointed.startswith(" of whiteboard wb-1:")
    assert "- rectangle rect-1 by agent at (10, 20)" in pointed
    assert '- text text-1 by agent at (10, 20) "half"' in pointed
    assert "ellipse-1" not in pointed
    assert "shape:" not in prompt


def test_a_simpler_request_attaches_the_whiteboard_text(tmp_path: Path):
    """WB-11: the turn prompt carries the whiteboard text and asks for fewer elements."""

    checked = check_drawing(valid_whiteboard())
    assert checked.whiteboard is not None
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("A simpler drawing."), result()], created)

    asyncio.run(
        _collect(
            agent,
            learner_message="Draw a simpler version of this whiteboard.",
            whiteboards=(checked.whiteboard,),
            simplify=checked.whiteboard,
        )
    )

    prompt = created[0].prompts[0]
    assert "Call draw_whiteboard" in prompt
    assert "fewer elements" in prompt
    assert "simplifies set to wb-1" in prompt
    assert "Do not send an image." in prompt
    assert "Do not change or delete the original whiteboard." in prompt
    assert describe_whiteboard(checked.whiteboard) in prompt
    assert "image:" not in prompt
    assert "simplifies" in DRAW_WHITEBOARD_DESCRIPTION
    assert DRAW_WHITEBOARD_SCHEMA["properties"]["simplifies"]["type"] == "string"
    assert "fewer elements" in created[0].options.system_prompt


def test_an_earlier_pointed_turn_stays_named_in_the_prompt():
    checked = check_drawing(valid_whiteboard())
    assert checked.whiteboard is not None

    prompt = turn_prompt(
        Profile(("wants short explanations",)),
        "And the other box?",
        prior_turns=(
            Turn(
                "What is this part?",
                "The left box is the whole.",
                pointing=Pointing("wb-1", ("rect-1",)),
            ),
        ),
        whiteboards=(checked.whiteboard,),
    )

    earlier = prompt.split("Earlier turns:", 1)[1].split("Whiteboards in this session:", 1)[0]
    assert "The learner pointed at these parts of whiteboard wb-1:" in earlier
    assert "rectangle rect-1 by agent at (10, 20)" in earlier
    assert "ellipse-1" not in earlier


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


def _capture_quiz_handlers(monkeypatch) -> list:
    import polaris.teaching as teaching_mod

    handlers: list = []
    original = teaching_mod.teaching_options

    def wrapped(*, cwd: Path, create_quiz=None, draw_whiteboard=None):
        handlers.append(create_quiz)
        return original(
            cwd=cwd,
            create_quiz=create_quiz,
            draw_whiteboard=draw_whiteboard,
        )

    monkeypatch.setattr(teaching_mod, "teaching_options", wrapped)
    return handlers


ONE_QUESTION = {
    "title": "Fractions",
    "questions": [
        {
            "id": "q1",
            "prompt": "What is 1/2 of 4?",
            "choices": [
                {"id": "a", "text": "1", "why_wrong": "1 is half of 2, not of 4."},
                {"id": "b", "text": "2"},
            ],
            "correct_choice_id": "b",
            "explanation": "Half of 4 is 2.",
        }
    ],
}


def test_create_quiz_tool_stores_for_the_open_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    stored: list[tuple[str, dict]] = []
    handlers = _capture_quiz_handlers(monkeypatch)

    def store(session_id: str, spec: dict) -> dict:
        stored.append((session_id, spec))
        return {"id": "quiz-1"}

    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Ok"), result()], created)
    agent.bind_store(store)

    asyncio.run(_collect(agent, session_id="session-9"))
    payload = asyncio.run(handlers[0](ONE_QUESTION))

    assert stored == [("session-9", ONE_QUESTION)]
    assert payload.get("is_error") is not True
    assert "quiz-1" in payload["content"][0]["text"]
    assert created[0].options.tools == []
    assert created[0].options.allowed_tools == [CREATE_QUIZ_TOOL, DRAW_WHITEBOARD_TOOL]
    assert created[0].options.max_turns == 1 + WHITEBOARD_TOOL_LIMITS.max_fix_attempts + 3


def test_create_quiz_tool_rejects_a_quiz_without_one_correct_choice(
    tmp_path: Path,
):
    def store(session_id: str, spec: dict) -> dict:
        del session_id
        normalize_spec(spec)
        return {"id": "unused"}

    agent = _agent(tmp_path, [delta("Ok"), result()], [])
    agent.bind_store(store)

    payload = asyncio.run(
        agent.handle_create_quiz(
            "session-1",
            {
                "title": "Broken",
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "Pick one",
                        "choices": [
                            {"id": "a", "text": "1"},
                            {"id": "b", "text": "2"},
                        ],
                        "explanation": "There is no marked choice.",
                    }
                ],
            },
        )
    )

    assert payload["is_error"] is True
    assert payload["content"][0]["text"] == "q1: needs exactly one correct choice"


def test_create_quiz_tool_reports_a_blank_explanation(tmp_path: Path):
    def store(session_id: str, spec: dict) -> dict:
        del session_id
        normalize_spec(spec)
        return {"id": "unused"}

    agent = _agent(tmp_path, [delta("Ok"), result()], [])
    agent.bind_store(store)
    spec = {
        "title": "Fractions",
        "questions": [
            {
                "id": "q2",
                "prompt": "Which fraction equals one whole?",
                "choices": [
                    {"id": "a", "text": "1/2"},
                    {"id": "b", "text": "2/2"},
                ],
                "correct_choice_id": "b",
                "explanation": "   ",
            }
        ],
    }

    payload = asyncio.run(agent.handle_create_quiz("session-1", spec))

    assert payload["is_error"] is True
    assert payload["content"][0]["text"] == "q2: explanation is blank"


def test_create_quiz_tool_refuses_a_key_the_check_disagrees_with(tmp_path: Path):
    """QZ-12: a second model picks another choice, so the quiz is not stored."""

    stored: list[dict] = []
    check = FakeKeyCheck({"q1": "a"})
    agent = _agent(tmp_path, [delta("Ok"), result()], [], key_check=check)
    agent.bind_store(lambda session_id, spec: stored.append(spec) or {"id": "x"})

    payload = asyncio.run(agent.handle_create_quiz("session-1", ONE_QUESTION))

    assert payload["is_error"] is True
    text = payload["content"][0]["text"]
    assert "disagreed" in text
    assert '- q1: it chose a ("1"), the key says b.' in text
    assert stored == []


def test_create_quiz_tool_refuses_a_quiz_the_check_cannot_answer(tmp_path: Path):
    """QZ-12: when the check cannot finish, the quiz is not stored."""

    stored: list[dict] = []
    check = FakeKeyCheck(fail=True)
    agent = _agent(tmp_path, [delta("Ok"), result()], [], key_check=check)
    agent.bind_store(lambda session_id, spec: stored.append(spec) or {"id": "x"})

    payload = asyncio.run(agent.handle_create_quiz("session-1", ONE_QUESTION))

    assert payload["is_error"] is True
    assert "could not be checked" in payload["content"][0]["text"]
    assert stored == []


def test_a_quiz_refused_twice_is_not_checked_again(tmp_path: Path):
    """QZ-12: one retry per reply, so a refused quiz cannot use up the turn budget."""

    check = FakeKeyCheck({"q1": "a"})
    agent = _agent(tmp_path, [delta("Ok"), result()], [], key_check=check)
    agent.bind_store(lambda session_id, spec: {"id": "x"})

    async def three_tries():
        return [
            await agent.handle_create_quiz("session-1", ONE_QUESTION) for _ in range(3)
        ]

    payloads = asyncio.run(three_tries())

    assert [payload["is_error"] for payload in payloads] == [True, True, True]
    assert "too many times" in payloads[2]["content"][0]["text"]
    assert len(check.seen) == 2

    asyncio.run(_collect(agent, session_id="session-1"))
    check.answers = {"q1": "b"}
    payload = asyncio.run(agent.handle_create_quiz("session-1", ONE_QUESTION))
    assert payload.get("is_error") is not True


def test_the_key_check_never_sees_the_key(tmp_path: Path):
    check = FakeKeyCheck()
    agent = _agent(tmp_path, [delta("Ok"), result()], [], key_check=check)
    agent.bind_store(lambda session_id, spec: {"id": "quiz-1"})

    payload = asyncio.run(agent.handle_create_quiz("session-1", QUIZ_SPEC))

    assert payload.get("is_error") is not True
    shown = json.dumps(check.seen)
    assert "correct_choice_id" not in shown
    assert "explanation" not in shown
    assert "why_wrong" not in shown
    assert [question["id"] for question in check.seen[0]["questions"]] == ["q1", "q2"]


def test_a_quiz_without_notes_is_refused_before_the_check(tmp_path: Path):
    """QZ-13: a wrong choice without a note never reaches the key check."""

    check = FakeKeyCheck()
    agent = _agent(tmp_path, [delta("Ok"), result()], [], key_check=check)
    agent.bind_store(lambda session_id, spec: {"id": "quiz-1"})
    spec = copy.deepcopy(ONE_QUESTION)
    del spec["questions"][0]["choices"][0]["why_wrong"]

    payload = asyncio.run(agent.handle_create_quiz("session-1", spec))

    assert payload["is_error"] is True
    assert payload["content"][0]["text"] == "q1: choice a needs a why_wrong note"
    assert check.seen == []


def test_overlapping_clients_store_quiz_on_their_own_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    stored: list[str] = []
    handlers = _capture_quiz_handlers(monkeypatch)

    def store(session_id: str, spec: dict) -> dict:
        del spec
        stored.append(session_id)
        return {"id": f"quiz-{session_id}"}

    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Ok"), result()], created)
    agent.bind_store(store)

    async def overlap():
        await _collect(agent, session_id="session-a")
        await _collect(agent, session_id="session-b")
        await handlers[0](ONE_QUESTION)
        await handlers[1](ONE_QUESTION)

    asyncio.run(overlap())

    assert [client.options.max_turns for client in created] == [
        1 + WHITEBOARD_TOOL_LIMITS.max_fix_attempts + 3,
        1 + WHITEBOARD_TOOL_LIMITS.max_fix_attempts + 3,
    ]
    assert stored == ["session-a", "session-b"]
    assert handlers[0] is not handlers[1]


def test_bind_store_sends_create_quiz_through_chat(tmp_path: Path):
    created: list[FakeClient] = []
    agent = _agent(tmp_path, [delta("Ok"), result()], created)
    chat = Chat(tmp_path, agent)
    session, _ended = chat.start()

    payload = asyncio.run(agent.handle_create_quiz(session["id"], QUIZ_SPEC))
    quiz_id = payload["content"][0]["text"].split("id ", 1)[1].split(".", 1)[0]
    stored = chat.get_quiz(quiz_id)

    assert payload.get("is_error") is not True
    assert stored["id"] == quiz_id
    assert stored["session_id"] == session["id"]
    assert stored["title"] == "Fractions"
    assert stored["score"] is None


def test_reply_error_message_names_a_missing_cli():
    assert "Claude Code was not found" in reply_error_message(CLINotFoundError())


def test_reply_error_message_names_a_windows_spawn_failure():
    try:
        raise CLIConnectionError("Failed to start Claude Code: ") from NotImplementedError()
    except CLIConnectionError as exc:
        message = reply_error_message(exc)
    assert "cannot spawn processes" in message


def test_off_loop_client_forwards_connect_query_and_stream():
    inner = FakeClient(None, [delta("Hi"), result()])
    hosted = _OffLoopClient(inner)

    async def run():
        await hosted.connect()
        await hosted.query("hello")
        messages = [message async for message in hosted.receive_response()]
        await hosted.disconnect()
        return messages

    messages = asyncio.run(run())
    assert inner.prompts == ["hello"]
    assert inner.disconnected is True
    assert any(isinstance(message, StreamEvent) for message in messages)

