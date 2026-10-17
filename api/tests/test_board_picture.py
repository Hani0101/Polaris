"""A picture of the learner's whiteboard reaches the next turn (WB-03, WB-09).

These tests never call the model.
"""

import asyncio
import base64
import copy
import struct
import zlib
from pathlib import Path

from polaris.board_picture import PICTURE_LIMITS, BoardPicture, picture_errors
from polaris.models import Pointing, Profile
from polaris.teaching import ClaudeTeachingAgent, turn_prompt
from polaris.whiteboard import check_drawing, describe_whiteboard, summarize_whiteboard
from test_chat import make_client, parse_sse
from test_quiz import FILLED_PROFILE
from test_teaching import delta, result
from test_whiteboard import valid_whiteboard
from test_whiteboard_artifact import OneDrawingStub


def png(width: int = 2, height: int = 2) -> str:
    """A real, tiny, all-white PNG as base64."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    raw = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(raw).decode()


def test_a_small_png_is_accepted():
    assert picture_errors("image/png", png()) == []


def test_a_bad_picture_is_refused():
    assert picture_errors("image/jpeg", png()) == ["picture must be image/png"]
    assert picture_errors("image/png", "not base64!") == ["picture is not base64"]
    assert picture_errors("image/png", base64.b64encode(b"GIF89a....").decode()) == [
        "picture is not a PNG"
    ]
    huge = png(PICTURE_LIMITS.max_side + 1, 1)
    assert picture_errors("image/png", huge) == [
        f"picture must be at most {PICTURE_LIMITS.max_side} pixels on each side"
    ]


class PictureClient:
    """Reads a streamed user message the way the SDK client writes it."""

    def __init__(self, messages) -> None:
        self.messages = messages
        self.sent: list[object] = []

    async def connect(self) -> None:
        return None

    async def query(self, prompt, session_id: str = "default") -> None:
        del session_id
        if isinstance(prompt, str):
            self.sent.append(prompt)
            return
        async for message in prompt:
            self.sent.append(message)

    async def receive_response(self):
        for message in self.messages:
            yield message

    async def disconnect(self) -> None:
        return None


def _board():
    checked = check_drawing(valid_whiteboard())
    assert checked.whiteboard is not None
    return checked.whiteboard


def test_the_picture_goes_with_the_turn_text_as_one_message(tmp_path: Path):
    created: list[PictureClient] = []

    def factory(_options):
        client = PictureClient([delta("I see two boxes."), result()])
        created.append(client)
        return client

    agent = ClaudeTeachingAgent(tmp_path, client_factory=factory)
    board = _board()
    picture = BoardPicture(whiteboard_id=board.id, media_type="image/png", data=png())

    async def run() -> None:
        async for _item in agent.reply(
            session_id="session-1",
            profile=Profile(("likes pictures",)),
            learner_message="Is my drawing right?",
            prior_turns=(),
            sdk_session_id=None,
            whiteboards=(board,),
            picture=picture,
        ):
            pass

    asyncio.run(run())

    [message] = created[0].sent
    assert message["type"] == "user"
    text, image = message["message"]["content"]
    assert text["type"] == "text"
    assert "Is my drawing right?" in text["text"]
    # The text description still names the ids, so marks can target them.
    assert describe_whiteboard(board) in text["text"]
    assert "A picture of whiteboard wb-1" in text["text"]
    assert "check with them" in text["text"]
    assert image == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": png()},
    }


def test_a_turn_without_a_picture_stays_plain_text(tmp_path: Path):
    created: list[PictureClient] = []

    def factory(_options):
        client = PictureClient([delta("Hi."), result()])
        created.append(client)
        return client

    agent = ClaudeTeachingAgent(tmp_path, client_factory=factory)

    async def run() -> None:
        async for _item in agent.reply(
            session_id="session-1",
            profile=Profile(("likes pictures",)),
            learner_message="Hello",
            prior_turns=(),
            sdk_session_id=None,
        ):
            pass

    asyncio.run(run())

    assert len(created[0].sent) == 1
    assert isinstance(created[0].sent[0], str)


class PictureStub(OneDrawingStub):
    """Records the picture each reply receives."""

    def __init__(self, drawing: dict) -> None:
        super().__init__(drawing)
        self.pictures: list[BoardPicture | None] = []

    async def reply(self, *, picture=None, **kwargs):
        self.pictures.append(picture)
        async for chunk in super().reply(**kwargs):
            yield chunk


def test_the_api_passes_a_picture_of_a_session_whiteboard(make_client):
    stub = PictureStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    client.post(f"/api/sessions/{session['id']}/turns", json={"message": "Draw it."})

    response = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={
            "message": "Here is my sketch.",
            "picture": {"whiteboard_id": "wb-1", "media_type": "image/png", "data": png()},
        },
    )

    assert response.status_code == 200, response.text
    events, _rest = parse_sse(response.text)
    assert events[-1]["done"] is True
    assert stub.pictures[0] is None
    assert stub.pictures[1] == BoardPicture("wb-1", "image/png", png())
    # The picture is not stored with the turn.
    saved = client.get(f"/api/sessions/{session['id']}").json()
    assert "picture" not in saved["turns"][1]


def test_the_api_refuses_a_picture_of_an_unknown_whiteboard_or_a_bad_png(make_client):
    stub = PictureStub(valid_whiteboard())
    client, _agent = make_client(stub, profile=FILLED_PROFILE)
    session = client.post("/api/sessions").json()
    client.post(f"/api/sessions/{session['id']}/turns", json={"message": "Draw it."})

    unknown = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={
            "message": "Look.",
            "picture": {"whiteboard_id": "wb-none", "media_type": "image/png", "data": png()},
        },
    )
    bad = client.post(
        f"/api/sessions/{session['id']}/turns",
        json={
            "message": "Look.",
            "picture": {"whiteboard_id": "wb-1", "media_type": "image/png", "data": "abc"},
        },
    )

    assert unknown.status_code == 404
    assert bad.status_code == 422
    assert "picture" in bad.json()["detail"]


# The prompt keeps full detail only for the boards the turn is about.


def _second_board(board_id: str):
    data = copy.deepcopy(valid_whiteboard())
    data["id"] = board_id
    data["description"] = "Another picture of halves"
    data["version"] = 4
    checked = check_drawing(data)
    assert checked.whiteboard is not None
    return checked.whiteboard


def test_older_whiteboards_get_one_line_and_the_latest_gets_full_detail():
    old = _board()
    new = _second_board("wb-2")

    prompt = turn_prompt(Profile(("x",)), "Next?", whiteboards=(old, new))

    assert summarize_whiteboard(old) in prompt
    assert describe_whiteboard(old) not in prompt
    assert describe_whiteboard(new) in prompt
    assert summarize_whiteboard(old).startswith("Whiteboard wb-1 (summary): ")
    assert "7 parts, 2 by the learner." in summarize_whiteboard(old)
    assert summarize_whiteboard(new).startswith(
        "Whiteboard wb-2 (summary): Another picture of halves. 7 parts"
    )


def test_a_pointed_or_pictured_older_whiteboard_keeps_full_detail():
    old = _board()
    new = _second_board("wb-2")

    pointed = turn_prompt(
        Profile(("x",)),
        "This one?",
        whiteboards=(old, new),
        pointing=Pointing(whiteboard_id="wb-1", element_ids=("rect-1",)),
    )
    pictured = turn_prompt(
        Profile(("x",)),
        "Look.",
        whiteboards=(old, new),
        picture=BoardPicture("wb-1", "image/png", png()),
    )

    assert describe_whiteboard(old) in pointed
    assert describe_whiteboard(old) in pictured
    assert png() not in pictured
