"""The photos curation left lying, sent to the phone so a human can look.

A leftover is an item nobody rejected -- it simply never made it into a
post: too weak to carry one alone, and with nothing else from its shoot day
to fill a carousel. That is a defensible rule and it is also blind to what
Brano knows: what the moment was, what it cost, whether a cluttered corner
could be erased in ten seconds on his phone.

So this does not decide anything. It shows: batches of ten, oldest shoot
day first, each with its score and theme, and Brano says which ones stay.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.instagram_content.media_pool_models import MediaPoolItem
from app.instagram_content.media_pool_service import media_pool_service
from app.instagram_content.models import MediaType

from .preview import PostPreviewSender, PreviewError

BATCH_SIZE = 10

#: The numbered list, frozen on disk. Without it every batch would be
#: numbered against a pool that shifts under it -- one favourite marked and
#: "number 23" would mean a different photo than it did an hour ago.
_REVIEW_LIST = "leftover_review.json"


def _review_path() -> Path:
    return Path(os.getenv("JARVIS_DATA_DIR", "/data")) / _REVIEW_LIST


@dataclass(frozen=True)
class LeftoverBatch:
    sent: int
    remaining: int
    refs: list[str]


def leftover_photos(min_score: float = 0.0, singles_only: bool = False) -> list[MediaPoolItem]:
    """Available, unreserved photos, oldest shoot day first. Items without a
    capture date sort last: there is nothing to place them by.

    singles_only keeps the ones that are alone on their shoot day -- the 110
    that can never form a carousel under the day rule, and the ones most
    likely to belong together by place instead. That grouping is Brano's
    call, not the pool's.
    """
    items = [
        item for item in media_pool_service.list_all()
        if item.media_type == MediaType.image
        and item.available
        and not item.favorite
        and item.aesthetic_score >= min_score
    ]
    if singles_only:
        per_day: dict[str, int] = {}
        for item in items:
            key = item.captured_at.date().isoformat() if item.captured_at else "-"
            per_day[key] = per_day.get(key, 0) + 1
        items = [
            item for item in items
            if per_day[item.captured_at.date().isoformat() if item.captured_at else "-"] == 1
        ]
    # media_ref breaks ties so the order -- and with it every number Brano
    # reads off a caption -- is the same on every run.
    return sorted(items, key=lambda i: (i.captured_at is None, i.captured_at, i.media_ref))


def start_review(min_score: float = 0.0, singles_only: bool = True) -> list[str]:
    """Freeze the list to be reviewed, in order, and number it from 1."""
    refs = [item.media_ref for item in leftover_photos(min_score, singles_only)]
    path = _review_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"refs": refs}), encoding="utf-8")
    return refs


def review_list() -> list[str]:
    path = _review_path()
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("refs", []))


def ref_for_number(number: int) -> str | None:
    """Which photo Brano means when he says "23"."""
    refs = review_list()
    return refs[number - 1] if 1 <= number <= len(refs) else None


def _caption(item: MediaPoolItem, number: int | None = None) -> str:
    day = item.captured_at.date().isoformat() if item.captured_at else "ohne Datum"
    head = f"Nr. {number} · " if number is not None else ""
    line = f"{head}{day} · {item.aesthetic_score:.2f} · {item.theme}"
    if item.analysis_reasoning:
        line += f"\n{item.analysis_reasoning[:250]}"
    else:
        line += f"\n{', '.join(item.tags[:5])}"
    return f"{line}\n{item.media_ref}"


def send_leftovers(
    min_score: float = 0.4,
    offset: int = 0,
    limit: int = BATCH_SIZE,
    sender: PostPreviewSender | None = None,
    client: httpx.Client | None = None,
    use_review_list: bool = False,
) -> LeftoverBatch:
    """Send one batch. The media_ref goes in every caption on purpose: it is
    how Brano names the one he wants kept, and it is the only stable handle
    a photo has."""
    sender = sender or PostPreviewSender()
    if use_review_list:
        refs = review_list()
        by_ref = {item.media_ref: item for item in media_pool_service.list_all()}
        todo = [by_ref[ref] for ref in refs if ref in by_ref]
    else:
        todo = leftover_photos(min_score)
    batch = todo[offset:offset + limit]
    if not batch:
        return LeftoverBatch(sent=0, remaining=0, refs=[])

    # The sender's own client when it has one: in a test that is the mocked
    # transport, and creating a second, real one here would quietly reach
    # for the network instead.
    client = client or sender._client
    own_client = client is None
    client = client or httpx.Client()
    try:
        media = []
        for position, item in enumerate(batch, start=1):
            try:
                media.append((item, sender.media_for(client, item, position)))
            except PreviewError:
                continue
        if not media:
            raise PreviewError("none of this batch could be fetched")
        group = [
            {"type": "photo", "media": f"attach://f{index}",
             "caption": _caption(item, number=offset + index + 1)}
            for index, (item, _) in enumerate(media)
        ]
        files = {f"f{index}": (preview.filename, preview.data) for index, (_, preview) in enumerate(media)}
        import json

        sender._call(client, "sendMediaGroup",
                     {"chat_id": sender.telegram.chat_id, "media": json.dumps(group)}, files)
    finally:
        if own_client:
            client.close()
    return LeftoverBatch(
        sent=len(media),
        remaining=max(0, len(todo) - offset - len(batch)),
        refs=[item.media_ref for item, _ in media],
    )
