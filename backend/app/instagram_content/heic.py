"""iPhone photos arrive as HEIC, which Instagram refuses (JPEG only) -- and Live Photos bring a
short MOV of the same name that is not a clip anyone shot on purpose.

HEIC is turned into JPEG right at ingest, EXIF included (the capture time and Lightroom's
"Software" tag decide the shoot day and the grading chain), so everything after this point only
ever sees JPEG. A Live-Photo companion MOV never enters the pool.
"""
from __future__ import annotations

import base64
import re
from io import BytesIO
from pathlib import PurePath

from PIL import Image

try:  # registers HEIC/HEIF with Pillow; without it a HEIC is refused below, never passed on
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_READY = True
except ImportError:  # pragma: no cover -- the image installs it (requirements.txt)
    HEIF_READY = False

HEIC_TYPES = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
LIVE_PHOTO_MAX_SECONDS = 3.0
_IPHONE_NAME = re.compile(r"^IMG_(E)?\d{3,5}$", re.IGNORECASE)


class HeicError(RuntimeError):
    pass


def is_heic(data: bytes, media_type: str | None = None, file_name: str | None = None) -> bool:
    if (media_type or "").lower() in HEIC_TYPES:
        return True
    if file_name and PurePath(file_name).suffix.lower() in (".heic", ".heif"):
        return True
    # ISO-BMFF: "ftyp" at byte 4, then a HEIF brand
    return data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")


def to_jpeg_base64(image_base64: str, quality: int = 92) -> str:
    """HEIC bytes (base64) -> JPEG bytes (base64), EXIF kept. Raises instead of guessing."""
    if not HEIF_READY:
        raise HeicError("HEIC photo, but pillow-heif is not installed -- refused instead of passed on unreadable")
    try:
        img = Image.open(BytesIO(base64.b64decode(image_base64)))
        img.load()
        exif = img.info.get("exif")
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = BytesIO()
        img.save(out, "JPEG", quality=quality, **({"exif": exif} if exif else {}))
    except Exception as exc:  # noqa: BLE001 -- any decode failure ends this item with a reason
        raise HeicError(f"could not convert HEIC to JPEG: {exc}") from exc
    return base64.b64encode(out.getvalue()).decode("ascii")


def live_photo_companion(file_name: str | None, duration_seconds: float, known_photo_stems: set[str]) -> bool:
    """A MOV under 3 s that belongs to a still: same name as a photo we know, or an iPhone camera
    name (IMG_1234). A deliberately short clip with any other name still goes in."""
    if not file_name or duration_seconds >= LIVE_PHOTO_MAX_SECONDS:
        return False
    p = PurePath(file_name)
    if p.suffix.lower() != ".mov":
        return False
    return p.stem.lower() in known_photo_stems or bool(_IPHONE_NAME.match(p.stem))
