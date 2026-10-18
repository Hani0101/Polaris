"""Flashcard scenarios: FC-01 through FC-18, CH-12, and decision 0012.

The UI rules (FC-02, FC-03, FC-11, FC-13, FC-19) are checked in the web tests.
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from polaris.agent import ReplyResult
from polaris.app import create_app
from polaris.flashcards import (
    MAX_CARDS,
    InvalidDeck,
    SourceResource,
    describe_deck,
    normalize_deck,
)
from polaris.models import Fact, Profile, Turn
from polaris.profile_pass import session_prompt
from polaris.teaching import (
    CREATE_FLASHCARDS_SCHEMA,
    CREATE_FLASHCARDS_TOOL,
    DECK_CHECK_ATTEMPTS,
    ClaudeTeachingAgent,
    teaching_options,
    teaching_prompt,
    turn_prompt,
)
from test_resources import PNG, add_note, make_pdf, new_session, upload

FILLED_PROFILE = '{\n  "facts": ["wants short explanations"]\n}\n'

PHOTOSYNTHESIS = (
    "Photosynthesis turns light into chemical energy. "
    "Chlorophyll absorbs mostly red and blue light."
)


def card(front: str = "What is photosynthesis?", **source) -> dict:
    return {
        "front": front,
        "back": "Plants turn light into chemical energy.",
        "source": source or {"turn": 1},
    }


class DeckAgent:
    """Teaches on the first turns, and stores the queued deck when one is queued."""

    def __init__(self) -> None:
        self.chat = None
        self.next_deck: dict | None = None
        self.refusal: str | None = None
        self.seen_decks: list[list[dict]] = []
        self.fail_after_deck = False

    async def reply(self, *, session_id, learner_message, decks=(), **_extra):
        self.seen_decks.append(list(decks))
        yield f"About {learner_message}. "
        if self.next_deck is not None:
            spec, self.next_deck = self.next_deck, None
            try:
                self.chat.create_deck(session_id, spec)
            except InvalidDeck as exc:
                self.refusal = str(exc)
            if self.fail_after_deck:
                raise RuntimeError("the reply failed")
        yield ReplyResult(sdk_session_id=None)

    async def close_session(self, session_id: str) -> None:
        pass


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    opened: list[TestClient] = []

    def make(profile_pass=None):
        (tmp_path / "profile.json").write_text(FILLED_PROFILE, encoding="utf-8")
        agent = DeckAgent()
        client = TestClient(create_app(tmp_path, agent, profile_pass=profile_pass))
        agent.chat = client.app.state.chat
        client.__enter__()
        opened.append(client)
        return client, agent

    yield make
    for client in opened:
        client.__exit__(None, None, None)


def send(client, session_id: str, message: str) -> list[dict]:
    response = client.post(f"/api/sessions/{session_id}/turns", json={"message": message})
    assert response.status_code == 200, response.text
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.split("\n")
        if line.startswith("data: ")
    ]


def decks_in(client, session_id: str) -> list[dict]:
    saved = client.get(f"/api/sessions/{session_id}").json()
    return [
        artifact
        for turn in saved["turns"]
        for artifact in turn["artifacts"]
        if artifact["kind"] == "deck"
    ]


def taught_session(client, turns: int = 1) -> str:
    session = new_session(client)
    for number in range(turns):
        send(client, session, f"photosynthesis part {number + 1}")
    return session


def ask_for_deck(client, agent, session: str, cards: list[dict]) -> list[dict]:
    agent.next_deck = {"title": "Photosynthesis", "cards": cards}
    return send(client, session, "make flashcards for what we covered")


def test_a_deck_is_in_the_turn_that_asked_for_it(make_client):  # FC-01, FC-12, CH-02
    client, agent = make_client()
    session = taught_session(client)

    events = ask_for_deck(client, agent, session, [card()])

    sent = [event["artifact"] for event in events if "artifact" in event]
    assert [artifact["kind"] for artifact in sent] == ["deck"]
    saved = client.get(f"/api/sessions/{session}").json()
    assert saved["turns"][1]["artifacts"] == sent
    stored = client.get(f"/api/decks/{sent[0]['id']}").json()
    assert stored["session_id"] == session
    assert stored["cards"][0]["front"] == "What is photosynthesis?"


def test_each_card_shows_its_source(make_client):  # FC-05
    client, agent = make_client()
    session = taught_session(client, turns=3)
    pdf = upload(
        client, session, "Notes.pdf", make_pdf(["one", "two", "three", PHOTOSYNTHESIS])
    ).json()
    note = add_note(client, session, "Week 2", "Mitochondria are the site of respiration.").json()

    ask_for_deck(
        client,
        agent,
        session,
        [
            card("Photosynthesis?", resource_id=pdf["id"], page=4),
            card("Mitochondria?", resource_id=note["id"], quote="the site of respiration"),
            card("Turn three?", turn=3),
        ],
    )

    sources = [item["source"] for item in decks_in(client, session)[0]["cards"]]
    assert sources[0] == {"kind": "page", "resource_id": pdf["id"], "name": "Notes.pdf", "page": 4}
    assert sources[1] == {
        "kind": "quote",
        "resource_id": note["id"],
        "name": "Week 2",
        "quote": "the site of respiration",
    }
    assert sources[2] == {"kind": "turn", "turn": 3}


def test_a_deck_uses_only_this_sessions_sources(make_client):  # FC-04
    client, agent = make_client()
    other = new_session(client)
    elsewhere = add_note(client, other, "Mitosis", "Mitosis makes two identical cells.").json()
    session = taught_session(client)

    ask_for_deck(
        client,
        agent,
        session,
        [card(resource_id=elsewhere["id"], quote="makes two identical cells")],
    )

    assert decks_in(client, session) == []
    assert "not in this session" in agent.refusal


def test_a_page_that_does_not_exist_is_refused(make_client):  # FC-06
    client, agent = make_client()
    session = taught_session(client)
    pdf = upload(client, session, "Notes.pdf", make_pdf(["page"] * 12)).json()

    ask_for_deck(
        client, agent, session, [card(), card("Late page?", resource_id=pdf["id"], page=40)]
    )

    assert decks_in(client, session) == []
    assert "card 2: cites page 40" in agent.refusal
    assert "has 12 pages" in agent.refusal


def test_a_phrase_that_is_not_in_the_resource_is_refused(make_client):  # FC-06
    client, agent = make_client()
    session = taught_session(client)
    note = add_note(client, session, "Week 2", PHOTOSYNTHESIS).json()

    ask_for_deck(
        client,
        agent,
        session,
        [card(resource_id=note["id"], quote="plants breathe out nitrogen gas")],
    )

    assert decks_in(client, session) == []
    assert 'quotes a phrase that is not in "Week 2"' in agent.refusal


def test_a_turn_that_does_not_exist_is_refused(make_client):  # FC-06
    client, agent = make_client()
    session = taught_session(client, turns=4)

    ask_for_deck(client, agent, session, [card(turn=9)])

    assert decks_in(client, session) == []
    assert "cites turn 9, but this session has turns 1 to 4" in agent.refusal


def test_the_turn_asking_for_the_deck_is_not_a_source(make_client):  # FC-04, FC-06
    client, agent = make_client()
    session = new_session(client)

    ask_for_deck(client, agent, session, [card(turn=1)])

    assert decks_in(client, session) == []
    assert "no earlier turns" in agent.refusal


def test_an_image_cannot_be_cited():  # FC-06
    image = SourceResource(id="r1", kind="image", name="Leaf.png", pages=())

    with pytest.raises(InvalidDeck, match="an image has no text to check"):
        normalize_deck(
            {"title": "T", "cards": [card(resource_id="r1", quote="a green leaf here")]},
            resources=[image],
            turn_count=0,
        )


def test_a_quote_is_matched_whatever_its_quote_marks_and_spacing():  # FC-06
    note = SourceResource(
        id="r1", kind="note", name="Week 2", pages=("The cell’s  power\nplant is here.",)
    )

    stored = normalize_deck(
        {"title": "T", "cards": [card(resource_id="r1", quote="“the CELL'S power plant”")]},
        resources=[note],
        turn_count=0,
    )

    assert stored["cards"][0]["source"]["quote"] == "the CELL'S power plant"


def test_a_one_word_quote_proves_nothing():  # FC-06
    note = SourceResource(id="r1", kind="note", name="Week 2", pages=("the cell",))

    with pytest.raises(InvalidDeck, match="under 3 words"):
        normalize_deck(
            {"title": "T", "cards": [card(resource_id="r1", quote="cell")]},
            resources=[note],
            turn_count=0,
        )


def test_a_pdf_quote_must_be_on_the_cited_page():  # FC-06
    pdf = SourceResource(id="r1", kind="pdf", name="Notes.pdf", pages=("alpha beta gamma", "delta"))

    with pytest.raises(InvalidDeck, match="not on page 2"):
        normalize_deck(
            {"title": "T", "cards": [card(resource_id="r1", page=2, quote="alpha beta gamma")]},
            resources=[pdf],
            turn_count=0,
        )


class RefusingStore:
    def __init__(self, refusals: int) -> None:
        self.refusals = refusals
        self.calls = 0

    def __call__(self, session_id: str, spec: dict) -> dict:
        self.calls += 1
        if self.calls <= self.refusals:
            raise InvalidDeck("The deck was not stored. These cards failed:\n- card 1: bad")
        return {"id": "deck-1", "cards": spec["cards"]}


def _agent(tmp_path, store: RefusingStore) -> ClaudeTeachingAgent:
    agent = ClaudeTeachingAgent(tmp_path)
    agent.bind_store(lambda _session, _spec: {"id": "quiz"}, create_deck=store)
    return agent


def test_a_refused_deck_may_be_sent_once_more(tmp_path):  # FC-06
    store = RefusingStore(refusals=1)
    agent = _agent(tmp_path, store)
    spec = {"title": "T", "cards": [card()]}

    first = asyncio.run(agent.handle_create_flashcards("s1", spec))
    second = asyncio.run(agent.handle_create_flashcards("s1", spec))

    assert first["is_error"] is True
    assert "card 1: bad" in first["content"][0]["text"]
    assert "send the whole deck once more" in first["content"][0]["text"]
    assert "is_error" not in second
    assert "Deck stored as id deck-1" in second["content"][0]["text"]


def test_a_deck_that_fails_twice_stores_nothing(tmp_path):  # FC-06, FC-12
    store = RefusingStore(refusals=5)
    agent = _agent(tmp_path, store)
    spec = {"title": "T", "cards": [card()]}

    results = [
        asyncio.run(agent.handle_create_flashcards("s1", spec))
        for _ in range(DECK_CHECK_ATTEMPTS + 1)
    ]

    assert all(result["is_error"] for result in results)
    assert store.calls == DECK_CHECK_ATTEMPTS
    assert "Tell the learner which cards failed and why" in results[1]["content"][0]["text"]
    assert "Do not send a deck again" in results[-1]["content"][0]["text"]


def test_a_failed_reply_keeps_no_part_of_its_deck(make_client):  # FC-12
    client, agent = make_client()
    session = taught_session(client)
    agent.fail_after_deck = True

    ask_for_deck(client, agent, session, [card()])

    assert decks_in(client, session) == []
    with client.app.state.chat._lock:
        count = client.app.state.chat._conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
    assert count == 0


def test_past_30_cards_is_refused():  # FC-09
    with pytest.raises(InvalidDeck, match="second deck"):
        normalize_deck(
            {"title": "T", "cards": [card()] * (MAX_CARDS + 1)}, resources=[], turn_count=1
        )
    assert CREATE_FLASHCARDS_SCHEMA["properties"]["cards"]["maxItems"] == MAX_CARDS


def test_30_cards_are_stored():  # FC-09
    stored = normalize_deck({"title": "T", "cards": [card()] * MAX_CARDS}, resources=[], turn_count=1)

    assert len(stored["cards"]) == MAX_CARDS
    assert [item["id"] for item in stored["cards"][:3]] == ["c1", "c2", "c3"]


def test_card_text_is_kept_as_written(make_client):  # FC-10
    client, agent = make_client()
    session = taught_session(client)
    hostile = "<img src=x onerror=alert(1)>"

    ask_for_deck(
        client, agent, session, [{"front": "Q?", "back": hostile, "source": {"turn": 1}}]
    )

    assert decks_in(client, session)[0]["cards"][0]["back"] == hostile


def test_the_prompt_keeps_cards_to_the_sessions_sources(tmp_path):  # FC-04, FC-07, FC-08, FC-09
    prompt = teaching_prompt()

    assert "call create_flashcards" in prompt
    assert "Never write a card from your own memory" in prompt
    assert "fetching from the internet is not available yet" in prompt
    assert "Never pad a deck" in prompt
    assert "Make 5 to 15 cards" in prompt
    assert "Do not call create_flashcards." in prompt
    assert CREATE_FLASHCARDS_TOOL in teaching_options(cwd=tmp_path).allowed_tools


def test_the_prompt_numbers_the_turns():  # FC-05
    prompt = turn_prompt(
        Profile(("likes lists",)),
        "flashcards please",
        prior_turns=(Turn("a", "b"), Turn("c", "d")),
    )

    assert "This session has 2 earlier turns, numbered 1 to 2" in prompt
    assert "Turn 2\nLearner: c" in prompt
    resumed = turn_prompt(Profile(("likes lists",)), "flashcards please", turn_count=4)
    assert "This session has 4 earlier turns" in resumed


def _rate(client, deck: dict, card_id: str, rating: str):
    return client.post(
        f"/api/decks/{deck['id']}/ratings", json={"card_id": card_id, "rating": rating}
    )


def test_ratings_are_kept_and_can_be_reset(make_client):  # FC-14
    client, agent = make_client()
    session = taught_session(client)
    ask_for_deck(client, agent, session, [card("A?"), card("B?"), card("C?")])
    deck = decks_in(client, session)[0]

    assert _rate(client, deck, "c1", "again").status_code == 200
    _rate(client, deck, "c1", "got_it")
    rated = _rate(client, deck, "c2", "again").json()

    assert [item["rating"] for item in rated["cards"]] == ["got_it", "again", None]
    assert rated["counts"] == {"got_it": 1, "again": 1, "unrated": 1}
    assert decks_in(client, session)[0]["counts"]["unrated"] == 1
    reset = client.delete(f"/api/decks/{deck['id']}/ratings").json()
    assert reset["counts"] == {"got_it": 0, "again": 0, "unrated": 3}


@pytest.mark.parametrize(("card_id", "rating"), [("c9", "again"), ("c1", "easy")])
def test_an_invalid_rating_is_refused(make_client, card_id, rating):  # FC-14
    client, agent = make_client()
    session = taught_session(client)
    ask_for_deck(client, agent, session, [card()])
    deck = decks_in(client, session)[0]

    assert _rate(client, deck, card_id, rating).status_code == 422
    assert client.get(f"/api/decks/{deck['id']}").json()["counts"]["unrated"] == 1


def test_an_unknown_deck_is_not_found(make_client):
    client, _agent = make_client()

    assert client.get("/api/decks/missing").status_code == 404
    assert client.delete("/api/decks/missing/ratings").status_code == 404


def test_the_next_reply_sees_the_deck(make_client):  # FC-15
    client, agent = make_client()
    session = taught_session(client)
    ask_for_deck(client, agent, session, [card("What is chlorophyll?"), card("B?"), card("C?")])
    deck = decks_in(client, session)[0]
    _rate(client, deck, "c1", "again")

    send(client, session, "what next?")

    seen = agent.seen_decks[-1]
    assert [item["id"] for item in seen] == [deck["id"]]
    text = describe_deck(seen[0])
    assert "2 unrated" in text
    assert "- What is chlorophyll?" in text
    assert "Flashcard decks in this session" in turn_prompt(
        Profile(("x",)), "next", decks=seen
    )


def test_ratings_stay_out_of_the_profile_pass(make_client):  # FC-16
    client, agent = make_client()
    session = taught_session(client)
    ask_for_deck(client, agent, session, [card("RATED-CARD-FRONT")])
    deck = decks_in(client, session)[0]
    _rate(client, deck, "c1", "again")
    turns = client.app.state.chat._turns(session)

    prompt = session_prompt([Fact("f", "skill", "x", "said", "t", "t")], turns)

    assert any(artifact["kind"] == "deck" for turn in turns for artifact in turn.artifacts)
    assert "RATED-CARD-FRONT" not in prompt
    assert "again" not in prompt


def test_deleting_a_session_deletes_its_decks(make_client):  # FC-17, CH-12
    client, agent = make_client()
    session = taught_session(client)
    ask_for_deck(client, agent, session, [card()])
    deck = decks_in(client, session)[0]
    _rate(client, deck, "c1", "got_it")

    assert client.delete(f"/api/sessions/{session}").status_code == 200

    assert client.get(f"/api/decks/{deck['id']}").status_code == 404
    with client.app.state.chat._lock:
        count = client.app.state.chat._conn.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
    assert count == 0


def test_a_removed_resource_leaves_the_card(make_client):  # FC-18, RS-15
    client, agent = make_client()
    session = taught_session(client)
    pdf = upload(client, session, "Notes.pdf", make_pdf(["a", "b", "c", PHOTOSYNTHESIS])).json()
    ask_for_deck(client, agent, session, [card(resource_id=pdf["id"], page=4)])

    client.delete(f"/api/sessions/{session}/resources/{pdf['id']}")

    kept = decks_in(client, session)[0]["cards"]
    assert len(kept) == 1
    assert kept[0]["source"]["removed"] is True
    assert kept[0]["source"]["page"] == 4


def test_a_renamed_resource_shows_its_new_name(make_client):  # FC-05
    client, agent = make_client()
    session = taught_session(client)
    note = add_note(client, session, "Week 2", PHOTOSYNTHESIS).json()
    ask_for_deck(
        client, agent, session, [card(resource_id=note["id"], quote="turns light into chemical energy")]
    )

    client.patch(f"/api/sessions/{session}/resources/{note['id']}", json={"name": "Biology"})

    assert decks_in(client, session)[0]["cards"][0]["source"]["name"] == "Biology"


def test_an_image_resource_is_refused_in_a_session(make_client):  # FC-06
    client, agent = make_client()
    session = taught_session(client)
    image = upload(client, session, "leaf.png", PNG).json()

    ask_for_deck(client, agent, session, [card(resource_id=image["id"], quote="a green leaf here")])

    assert decks_in(client, session) == []
    assert "an image has no text to check" in agent.refusal
