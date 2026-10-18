"""Flashcard decks: every card is tied to a source in the session, and code
checks each source before the deck is stored (FC-06, decision 0012). No second
model is used. Ratings stay with the deck and never reach the profile (FC-16)."""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# FC-09: a request for more is honored up to this many cards.
MAX_CARDS = 30
# FC-05: a back is a summary of at most about three sentences.
MAX_FRONT_CHARS = 200
MAX_BACK_CHARS = 600
MAX_TITLE_CHARS = 80
# A quoted phrase this short would match almost any text, so it proves nothing.
MIN_QUOTE_WORDS = 3
MAX_QUOTE_CHARS = 300

GOT_IT = "got_it"
AGAIN = "again"
RATINGS = (GOT_IT, AGAIN)

PDF = "pdf"
IMAGE = "image"

_QUOTE_MARKS = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        " ": " ",
    }
)
_SPACE = re.compile(r"\s+")


class InvalidDeck(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class MissingDeck(Exception):
    def __init__(self) -> None:
        super().__init__("No flashcard deck with that id.")


class InvalidRating(Exception):
    def __init__(self) -> None:
        super().__init__('Rate a card of this deck "got_it" or "again".')


@dataclass(frozen=True)
class SourceResource:
    """A resource of the session as the source check sees it: its extracted text."""

    id: str
    kind: str
    name: str
    # PDF pages, or parts of other text. Empty for an image.
    pages: tuple[str, ...]


def comparable(text: str) -> str:
    """Text as the quote check compares it: same case, quote marks, and spacing."""

    folded = unicodedata.normalize("NFKC", text).translate(_QUOTE_MARKS).casefold()
    return _SPACE.sub(" ", folded).strip()


def normalize_deck(
    spec: dict[str, Any],
    *,
    resources: Sequence[SourceResource],
    turn_count: int,
) -> dict[str, Any]:
    """Return the stored deck, or raise InvalidDeck naming every card that fails.

    A card that fails is a refusal of the whole deck (FC-06). turn_count is the
    number of earlier turns in the session; a turn is cited by its number.
    """

    title = spec.get("title")
    cards = spec.get("cards")
    if not isinstance(title, str) or not title.strip():
        raise InvalidDeck("title is blank")
    if not isinstance(cards, list) or not cards:
        raise InvalidDeck("cards are missing")
    if len(cards) > MAX_CARDS:
        raise InvalidDeck(
            f"a deck has at most {MAX_CARDS} cards; send {MAX_CARDS} or fewer "
            "and offer the learner a second deck"
        )
    by_id = {resource.id: resource for resource in resources}
    stored: list[dict[str, Any]] = []
    problems: list[str] = []
    for number, card in enumerate(cards, start=1):
        try:
            stored.append(_normalize_card(card, number, by_id, turn_count))
        except InvalidDeck as exc:
            problems.append(f"- card {number}: {exc}")
    if problems:
        raise InvalidDeck(
            "The deck was not stored. These cards failed the source check:\n"
            + "\n".join(problems)
        )
    return {"title": title.strip()[:MAX_TITLE_CHARS], "cards": stored}


def _normalize_card(
    card: Any,
    number: int,
    resources: Mapping[str, SourceResource],
    turn_count: int,
) -> dict[str, Any]:
    if not isinstance(card, dict):
        raise InvalidDeck("is not an object")
    front = _text(card.get("front"), "front", MAX_FRONT_CHARS)
    back = _text(card.get("back"), "back", MAX_BACK_CHARS)
    return {
        "id": f"c{number}",
        "front": front,
        "back": back,
        "source": _checked_source(card.get("source"), resources, turn_count),
    }


def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDeck(f"{field} is blank")
    text = value.strip()
    if len(text) > limit:
        raise InvalidDeck(f"{field} is over {limit} characters; keep it short")
    return text


def _checked_source(
    source: Any, resources: Mapping[str, SourceResource], turn_count: int
) -> dict[str, Any]:
    """FC-06: a cited turn exists, a cited PDF page exists, a quoted phrase is in the text."""

    if not isinstance(source, dict):
        raise InvalidDeck("has no source; every card cites a turn or a resource")
    turn = source.get("turn")
    resource_id = source.get("resource_id")
    if turn is not None and resource_id is not None:
        raise InvalidDeck("cites both a turn and a resource; cite one")
    if turn is not None:
        if not isinstance(turn, int) or isinstance(turn, bool):
            raise InvalidDeck("turn must be a whole number")
        if not 1 <= turn <= turn_count:
            if turn_count == 0:
                raise InvalidDeck(f"cites turn {turn}, but this session has no earlier turns")
            raise InvalidDeck(
                f"cites turn {turn}, but this session has turns 1 to {turn_count}"
            )
        return {"kind": "turn", "turn": turn}
    if not isinstance(resource_id, str) or not resource_id.strip():
        raise InvalidDeck("has no source; every card cites a turn or a resource")
    resource = resources.get(resource_id.strip())
    if resource is None:
        raise InvalidDeck(
            f"cites resource {resource_id.strip()}, which is not in this session"
        )
    if resource.kind == IMAGE:
        raise InvalidDeck(
            f'cites the image "{resource.name}"; an image has no text to check, '
            "so a card cannot cite it"
        )
    quote = _quote(source.get("quote"))
    if resource.kind == PDF:
        page = source.get("page")
        if not isinstance(page, int) or isinstance(page, bool):
            raise InvalidDeck(f'cites the PDF "{resource.name}" without a page')
        total = len(resource.pages)
        if not 1 <= page <= total:
            raise InvalidDeck(
                f'cites page {page} of "{resource.name}", which has {total} '
                f'page{"" if total == 1 else "s"}'
            )
        if quote is not None and comparable(quote) not in comparable(resource.pages[page - 1]):
            raise InvalidDeck(
                f'quotes a phrase that is not on page {page} of "{resource.name}"'
            )
        stored: dict[str, Any] = {
            "kind": "page",
            "resource_id": resource.id,
            "name": resource.name,
            "page": page,
        }
        if quote is not None:
            stored["quote"] = quote
        return stored
    if quote is None:
        raise InvalidDeck(
            f'cites "{resource.name}" without a quoted phrase; quote the words the card uses'
        )
    if comparable(quote) not in comparable("\n\n".join(resource.pages)):
        raise InvalidDeck(f'quotes a phrase that is not in "{resource.name}"')
    return {
        "kind": "quote",
        "resource_id": resource.id,
        "name": resource.name,
        "quote": quote,
    }


def _quote(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidDeck("quote is blank")
    quote = value.strip().strip("\"'“”‘’").strip()
    if len(quote.split()) < MIN_QUOTE_WORDS:
        raise InvalidDeck(
            f"quote is under {MIN_QUOTE_WORDS} words; quote a phrase, not a word"
        )
    if len(quote) > MAX_QUOTE_CHARS:
        raise InvalidDeck(f"quote is over {MAX_QUOTE_CHARS} characters; quote a phrase")
    return quote


def public_payload(
    deck_id: str,
    session_id: str,
    stored: dict[str, Any],
    ratings: Mapping[str, str],
    resource_names: Mapping[str, str],
) -> dict[str, Any]:
    """The deck as the learner sees it. resource_names is the session's resources
    now: a renamed resource shows its new name, a removed one is marked (FC-18)."""

    cards = []
    for card in stored["cards"]:
        source = dict(card["source"])
        resource_id = source.get("resource_id")
        if resource_id is not None:
            name = resource_names.get(resource_id)
            if name is None:
                source["removed"] = True
            else:
                source["name"] = name
        cards.append(
            {
                "id": card["id"],
                "front": card["front"],
                "back": card["back"],
                "source": source,
                "rating": ratings.get(card["id"]),
            }
        )
    return {
        "id": deck_id,
        "kind": "deck",
        "session_id": session_id,
        "title": stored["title"],
        "cards": cards,
        "counts": counts(stored, ratings),
    }


def counts(stored: dict[str, Any], ratings: Mapping[str, str]) -> dict[str, int]:
    marks = [ratings.get(card["id"]) for card in stored["cards"]]
    return {
        GOT_IT: marks.count(GOT_IT),
        AGAIN: marks.count(AGAIN),
        "unrated": marks.count(None),
    }


def rate(
    stored: dict[str, Any], ratings: Mapping[str, str], card_id: str, rating: str
) -> dict[str, str]:
    """FC-14: each card keeps its latest rating. A card can be rated again."""

    if rating not in RATINGS or card_id not in {card["id"] for card in stored["cards"]}:
        raise InvalidRating()
    return {**ratings, card_id: rating}


def describe_deck(payload: dict[str, Any]) -> str:
    """FC-15: what a later reply reads about a deck. The fronts of the cards
    rated "again", and how many are unrated."""

    tally = payload["counts"]
    total = len(payload["cards"])
    line = (
        f'Deck {payload["id"]} "{payload["title"]}": {total} '
        f'card{"" if total == 1 else "s"}, {tally[GOT_IT]} got it, '
        f'{tally[AGAIN]} again, {tally["unrated"]} unrated.'
    )
    again = [card["front"] for card in payload["cards"] if card["rating"] == AGAIN]
    if not again:
        return line
    return "\n".join([line, "Cards the learner rated again:"] + [f"- {front}" for front in again])
