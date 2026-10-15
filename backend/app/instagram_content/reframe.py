"""Two ways to save a good subject from a bad background.

A photo can be strong and still score low because of what is around the
subject -- a plastic bag on the table, a stranger's leg at the edge. The
score judges the whole frame, so the fix is the frame, not the subject:

* **crop** -- pull in until the clutter is outside the picture. Nothing is
  invented, nothing is retouched; it is the same photo, closer.
* **blur** -- keep the wider frame but push the background out of focus,
  the way a portrait lens would. The clutter is still there, it just stops
  competing with the subject.

Retouching things away (inpainting) is deliberately not here: on a busy
table with glass and reflections it smears, and it would be the one step
that puts something in the photo that was never in the room. For a single
favourite shot Brano has Canva for that.

Where the subject is comes from the same vision model that scored the
photo -- asked for one box, in normalized coordinates, about one image.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

#: How much room is left around the subject when cropping. A box drawn
#: tight against the subject and cut exactly there looks cramped.
_MARGIN = 0.05
#: Blur strength relative to the image's long edge, so a 2560px photo and a
#: 1080px one come out looking the same.
_BLUR_FRACTION = 0.012
#: Width of the soft edge between sharp subject and blurred background, as
#: a fraction of the long edge. A hard edge is what makes a fake portrait
#: mode look fake.
_FEATHER_FRACTION = 0.03

logger = logging.getLogger(__name__)


class ReframeError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubjectBox:
    """Where the subject sits, as fractions of width/height (0..1)."""

    x0: float
    y0: float
    x1: float
    y1: float
    note: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.x0 < self.x1 <= 1 and 0 <= self.y0 < self.y1 <= 1):
            raise ReframeError(f"subject box outside the image or inverted: {self}")

    def pixels(self, width: int, height: int, margin: float = 0.0) -> tuple[int, int, int, int]:
        x0 = max(0.0, self.x0 - margin)
        y0 = max(0.0, self.y0 - margin)
        x1 = min(1.0, self.x1 + margin)
        y1 = min(1.0, self.y1 + margin)
        return (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))


@dataclass(frozen=True)
class SubjectFinderConfig:
    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("AURON_VISION_MODEL", "claude-sonnet-5"))
    timeout_seconds: float = 30.0


_PROMPT = (
    "Where is the subject of this photo -- the thing it is actually about?\n"
    "Respond with ONLY a JSON object, no other text, no markdown fences:\n"
    '{"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0, "note": "one short sentence"}\n\n'
    "x0,y0 is the top-left and x1,y1 the bottom-right corner of the tightest box that still holds "
    "the whole subject, as fractions of the image width and height (0 to 1).\n"
    "Include the subject completely; leaving part of it outside the box is worse than a box slightly "
    "too large. Exclude background clutter wherever that is possible without cutting the subject.\n"
    "note: what the subject is, and what clutter sits outside the box."
)


class SubjectFinder:
    """One vision call, one box. Separate from the ingest analysis on
    purpose: that one runs for every file and is paid for once, this one
    runs only when a photo is actually being reframed."""

    def __init__(self, config: SubjectFinderConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or SubjectFinderConfig()
        self._client = client

    def find(self, image_bytes: bytes, media_type: str = "image/jpeg") -> SubjectBox:
        if not self.config.api_key:
            raise ReframeError("ANTHROPIC_API_KEY is not set -- cannot ask where the subject is")
        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode("ascii")}},
                        {"type": "text", "text": _PROMPT},
                    ]}],
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise ReframeError(f"Anthropic API returned {response.status_code}: {response.text[:300]}")
            blocks = response.json().get("content", [])
            raw = "".join(b["text"] for b in blocks if b.get("type") == "text").strip().strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()
            parsed = json.loads(raw)
        except httpx.HTTPError as exc:
            raise ReframeError(f"could not reach the Anthropic API: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ReframeError(f"subject box response was not JSON: {exc}") from exc
        finally:
            if should_close:
                client.close()
        try:
            return SubjectBox(
                x0=float(parsed["x0"]), y0=float(parsed["y0"]),
                x1=float(parsed["x1"]), y1=float(parsed["y1"]),
                note=str(parsed.get("note", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReframeError(f"subject box response was incomplete: {parsed}") from exc


def crop_to_subject(source: Path, box: SubjectBox, destination: Path, margin: float = _MARGIN) -> Path:
    """The same photo, closer. Clutter outside the box is gone because it
    is outside the picture -- not painted over."""
    with Image.open(source) as image:
        image = image.convert("RGB")
        left, top, right, bottom = box.pixels(image.width, image.height, margin)
        if right - left < 8 or bottom - top < 8:
            raise ReframeError("the subject box is too small to crop to")
        image.crop((left, top, right, bottom)).save(destination, "JPEG", quality=92)
    return destination


def blur_background(source: Path, box: SubjectBox, destination: Path, margin: float = _MARGIN) -> Path:
    """The wider frame kept, the background pushed out of focus.

    The mask is a rounded rectangle around the subject with a soft edge --
    an approximation of what a lens does, not a cut-out of the subject
    itself. On a subject that fills its box it reads naturally; a subject
    with gaps around it (a chair, a bicycle) will keep a sharp halo of
    background inside the box. That is the honest limit of doing this
    without a segmentation model.
    """
    with Image.open(source) as image:
        image = image.convert("RGB")
        long_edge = max(image.size)
        blurred = image.filter(ImageFilter.GaussianBlur(radius=max(2, long_edge * _BLUR_FRACTION)))
        mask = Image.new("L", image.size, 0)
        left, top, right, bottom = box.pixels(image.width, image.height, margin)
        radius = round(min(right - left, bottom - top) * 0.15)
        ImageDraw.Draw(mask).rounded_rectangle((left, top, right, bottom), radius=radius, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(2, long_edge * _FEATHER_FRACTION)))
        Image.composite(image, blurred, mask).save(destination, "JPEG", quality=92)
    return destination


def reframe_file(source: Path, mode: str, destination: Path, finder: SubjectFinder | None = None) -> tuple[Path, SubjectBox]:
    """Find the subject in `source` and apply `mode` ("crop" or "blur")."""
    if mode not in ("crop", "blur"):
        raise ReframeError(f"unknown reframe mode {mode!r} -- use 'crop' or 'blur'")
    if not source.is_file():
        raise ReframeError(f"no such image: {source}")
    box = (finder or SubjectFinder()).find(_as_jpeg(source))
    logger.info("subject box for %s: %s", source.name, box)
    if mode == "crop":
        return crop_to_subject(source, box, destination), box
    return blur_background(source, box, destination), box


def _as_jpeg(source: Path, max_edge: int = 1400) -> bytes:
    """A small copy for the vision call: the box is normalized, so a full
    12MP upload would only cost time and tokens."""
    with Image.open(source) as image:
        image = image.convert("RGB")
        image.thumbnail((max_edge, max_edge))
        buffer = BytesIO()
        image.save(buffer, "JPEG", quality=85)
        return buffer.getvalue()


def reframe_pool_item(media_ref: str, mode: str, finder: SubjectFinder | None = None) -> dict:
    """Reframe one pool item's processed file and make the result the file
    that gets previewed, sent and posted.

    The graded original stays on disk under its own name: a crop that turns
    out too tight has to be undoable without fetching from Drive again.
    processed_media_ref is cleared, so the next upload run puts the new
    version into "AURON fertig" instead of leaving Drive on the old one.
    """
    from .media_processing import output_dir
    from .media_pool_service import media_pool_service

    item = next((i for i in media_pool_service.list_all() if i.media_ref == media_ref), None)
    if item is None:
        raise ReframeError(f"no pool item with media_ref {media_ref}")
    if item.processed_file is None:
        raise ReframeError(f"{media_ref} has no processed file yet -- grade it first")

    source = output_dir() / item.processed_file
    graded_original = output_dir() / f"{media_ref}.graded.jpg"
    if not graded_original.is_file():
        # First reframe of this item: keep the graded version under a name
        # nothing else writes to, so later reframes start from it and not
        # from an already cropped file.
        graded_original.write_bytes(source.read_bytes())

    destination = output_dir() / f"{media_ref}.{mode}.jpg"
    _, box = reframe_file(graded_original, mode, destination, finder=finder)
    media_pool_service.set_processed_file(media_ref, destination.name)
    return {
        "media_ref": media_ref,
        "mode": mode,
        "processed_file": destination.name,
        "subject": box.note,
        "box": [box.x0, box.y0, box.x1, box.y1],
    }
