"""A picture of one whiteboard, sent with the learner's next turn.

The browser exports the board as a PNG after the learner draws on it. The
picture goes to the agent with that one turn, beside the text description of
the same board, so marks can still name element ids (WB-03, WB-09). It is
not stored. Later turns see the text description only.
"""

import base64
import binascii
from dataclasses import dataclass

PICTURE_MEDIA_TYPE = "image/png"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class PictureLimits:
    max_bytes: int = 2_000_000
    max_side: int = 2_000


PICTURE_LIMITS = PictureLimits()


@dataclass(frozen=True)
class BoardPicture:
    """data is base64 PNG bytes, checked by picture_errors."""

    whiteboard_id: str
    media_type: str
    data: str


def _png_size(raw: bytes) -> tuple[int, int] | None:
    # The IHDR chunk comes first: length, type, then width and height.
    if len(raw) < 24 or raw[12:16] != b"IHDR":
        return None
    return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")


def picture_errors(media_type: str, data: str) -> list[str]:
    """Why a picture cannot be sent. Empty means it can."""

    if media_type != PICTURE_MEDIA_TYPE:
        return [f"picture must be {PICTURE_MEDIA_TYPE}"]
    if len(data) > PICTURE_LIMITS.max_bytes * 4 // 3 + 4:
        return ["picture is too large"]
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        return ["picture is not base64"]
    if not raw.startswith(_PNG_SIGNATURE):
        return ["picture is not a PNG"]
    if len(raw) > PICTURE_LIMITS.max_bytes:
        return ["picture is too large"]
    size = _png_size(raw)
    if size is None:
        return ["picture is not a PNG"]
    width, height = size
    if not (0 < width <= PICTURE_LIMITS.max_side and 0 < height <= PICTURE_LIMITS.max_side):
        return [f"picture must be at most {PICTURE_LIMITS.max_side} pixels on each side"]
    return []
