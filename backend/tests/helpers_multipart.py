"""Reading back what was actually put on the wire to Telegram.

sendMediaGroup is multipart: the JSON describing the album rides in one
part, the image bytes in the others. The tests assert on captions, so they
need that part back out of the raw body.
"""

from __future__ import annotations

import json

_SEPARATOR = "\r\n\r\n"
_BOUNDARY = "\r\n--"


def media_json(body: bytes) -> list[dict]:
    text = body.decode("latin-1")
    part = text.split('name="media"')[1].split(_SEPARATOR, 1)[1]
    return json.loads(part.split(_BOUNDARY, 1)[0])
