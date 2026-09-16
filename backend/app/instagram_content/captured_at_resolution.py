from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum


class CapturedAtSource(str, Enum):
    """Where a captured_at timestamp actually came from.

    Recorded alongside the timestamp on purpose: an upload time is not a
    capture time, and the two must stay distinguishable. Chronological
    grouping and story ordering read captured_at, and an item whose
    timestamp is really "when it reached Drive" would sort as if it had
    been shot then -- a silent, unfalsifiable error once both are in the
    same column with no way to tell them apart.
    """

    #: EXIF DateTimeOriginal, read from the image itself. When the shutter fired.
    exif = "exif"
    #: The video container's own creation_time (MP4 mvhd). When the recording
    #: was made, as long as the exporting tool wrote a real value.
    video_metadata = "video_metadata"
    #: Google Drive's createdTime. When the file arrived, NOT when it was shot.
    #: A fallback, and the weakest one -- treat it as an upper bound.
    upload_time = "upload_time"


#: Anything at or before this is a zeroed-out field, not a real timestamp.
#: MP4 counts from 1904-01-01 and a missing mvhd creation_time is written as
#: 0, which decodes to exactly that; a zeroed Unix timestamp decodes to
#: 1970-01-01. Neither is a date anyone filmed anything on.
_EARLIEST_PLAUSIBLE = datetime(2000, 1, 1, tzinfo=timezone.utc)

#: Tolerance for a camera clock running ahead, or a timezone written as if
#: it were UTC. Beyond this the value is wrong, not merely skewed.
_FUTURE_TOLERANCE = timedelta(hours=24)


def is_plausible_capture_time(value: datetime | None, *, now: datetime | None = None) -> bool:
    if value is None:
        return False
    reference = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return _EARLIEST_PLAUSIBLE <= value <= reference + _FUTURE_TOLERANCE


def resolve_captured_at(
    *,
    exif: datetime | None = None,
    video_creation_time: datetime | None = None,
    upload_time: datetime | None = None,
    now: datetime | None = None,
) -> tuple[datetime | None, CapturedAtSource | None]:
    """Picks the best available capture time and says which source it is.

    Order is by how close the source sits to the moment of recording: EXIF
    and the container's own creation_time describe the recording itself,
    the upload time only bounds it from above. Each candidate must survive
    a plausibility check first -- a zeroed mvhd field decodes to 1904 and
    would otherwise beat a perfectly good upload time.

    Returns (None, None) when nothing plausible is available. That is a
    real answer, not a failure: it keeps the item flagged as incompletely
    analyzed rather than inventing a timestamp.
    """
    for candidate, source in (
        (exif, CapturedAtSource.exif),
        (video_creation_time, CapturedAtSource.video_metadata),
        (upload_time, CapturedAtSource.upload_time),
    ):
        if is_plausible_capture_time(candidate, now=now):
            assert candidate is not None  # narrowed by is_plausible_capture_time
            return (
                candidate if candidate.tzinfo else candidate.replace(tzinfo=timezone.utc),
                source,
            )
    return None, None
