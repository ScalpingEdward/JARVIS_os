from __future__ import annotations

import base64
import logging
import subprocess
from pathlib import Path

from .media_pool_models import FrameSample

logger = logging.getLogger(__name__)

FFPROBE_BINARY = "ffprobe"
FFMPEG_BINARY = "ffmpeg"

#: One frame roughly every this many seconds. Constant spacing rather than a
#: constant count: twelve frames of a 2-second clip are twelve near-identical
#: images, and twelve frames of a 46-second one are too coarse to locate a
#: 15-30s window. The trim analyzer picks from exactly the timestamps it is
#: shown, so this spacing *is* the precision of the resulting cut.
DEFAULT_SPACING_SECONDS = 2.5

#: At least 3 -- the trim analyzer refuses fewer. At most 20: comfortably
#: under the 30-frame cap on a request, and past roughly this many an extra
#: frame stops adding information.
MIN_FRAMES = 3
MAX_FRAMES = 20

#: Skip the first and last 5%. On phone footage the opening frame is
#: regularly black, blurred, or mid-movement toward the shutter, and the
#: closing one often catches the reach for the stop button. Those are the
#: worst candidates for a cover and the least informative for analysis.
EDGE_MARGIN_FRACTION = 0.05

#: Frames are handed to a vision model, not archived. Capping the width
#: keeps each JPEG small without touching footage that is already smaller
#: (min(1280, iw) never upscales).
MAX_FRAME_WIDTH_PX = 1280
FRAME_MEDIA_TYPE = "image/jpeg"

_PROBE_TIMEOUT_SECONDS = 30.0
_FRAME_TIMEOUT_SECONDS = 30.0

#: A client-supplied duration may differ slightly from what ffprobe reads --
#: container rounding, a different atom. Beyond either of these the two
#: disagree about the file itself and that is worth seeing.
_DURATION_ABS_TOLERANCE_SECONDS = 0.5
_DURATION_REL_TOLERANCE = 0.02


class VideoFrameExtractionError(RuntimeError):
    """ffprobe/ffmpeg could not be run, or could not make sense of the file."""


def _run(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise VideoFrameExtractionError(f"{command[0]} is not installed in this image") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoFrameExtractionError(f"{command[0]} timed out after {timeout}s") from exc


def _stderr_tail(completed: subprocess.CompletedProcess[bytes], limit: int = 300) -> str:
    return completed.stderr.decode("utf-8", "replace").strip()[-limit:]


def probe_duration_seconds(video_path: Path) -> float:
    """The video's real duration, read from the file itself.

    AURON treats this as authoritative and never the caller's value: the
    sampling plan is derived from it, and a wrong duration would sample
    past the end of the file or bunch every frame into its first seconds.
    """
    completed = _run(
        [
            FFPROBE_BINARY,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise VideoFrameExtractionError(f"ffprobe failed for {video_path.name}: {_stderr_tail(completed)}")

    raw = completed.stdout.decode("utf-8", "replace").strip()
    try:
        duration = float(raw)
    except ValueError as exc:
        raise VideoFrameExtractionError(
            f"ffprobe returned no usable duration for {video_path.name}: {raw!r}"
        ) from exc

    if duration <= 0:
        raise VideoFrameExtractionError(f"{video_path.name} reports a duration of {duration}s")
    return duration


def warn_on_duration_mismatch(video_path: Path, probed: float, claimed: float | None) -> bool:
    """Logs when the caller's duration and ffprobe's disagree meaningfully.

    ffprobe's value is used either way -- this only surfaces the
    disagreement, so a systematic drift between the two sources becomes
    visible before anyone decides to drop one of them.
    """
    if claimed is None:
        return False
    delta = abs(probed - claimed)
    if delta <= _DURATION_ABS_TOLERANCE_SECONDS and delta <= probed * _DURATION_REL_TOLERANCE:
        return False
    logger.warning(
        "duration mismatch for %s: ffprobe %.3fs vs supplied %.3fs (delta %.3fs, %.1f%%); using ffprobe",
        video_path.name, probed, claimed, delta, (delta / probed * 100) if probed else 0.0,
    )
    return True


def frame_timestamps(
    duration_seconds: float,
    *,
    spacing_seconds: float = DEFAULT_SPACING_SECONDS,
    min_frames: int = MIN_FRAMES,
    max_frames: int = MAX_FRAMES,
    margin_fraction: float = EDGE_MARGIN_FRACTION,
) -> list[float]:
    """Evenly spaced sample points across the usable middle of the video."""
    if duration_seconds <= 0:
        raise VideoFrameExtractionError(f"cannot sample a video of {duration_seconds}s")

    count = max(min_frames, min(max_frames, round(duration_seconds / spacing_seconds)))
    start = duration_seconds * margin_fraction
    end = duration_seconds * (1 - margin_fraction)

    if count == 1 or end <= start:
        return [round(duration_seconds / 2, 3)]

    step = (end - start) / (count - 1)
    return [round(start + step * i, 3) for i in range(count)]


def extract_frames(video_path: Path, timestamps: list[float]) -> list[FrameSample]:
    """One JPEG per timestamp, as base64, ready for the vision step.

    Each frame is a separate ffmpeg call with -ss ahead of -i, which seeks
    by keyframe before decoding instead of decoding the whole file. A frame
    that cannot be read fails the whole extraction rather than silently
    yielding a shorter, differently-spaced set -- the timestamps are the
    contract the analysis is built on.
    """
    frames: list[FrameSample] = []
    for timestamp in timestamps:
        completed = _run(
            [
                FFMPEG_BINARY,
                "-nostdin",
                "-ss", f"{timestamp:.3f}",
                "-i", str(video_path),
                "-frames:v", "1",
                "-vf", f"scale=w='min({MAX_FRAME_WIDTH_PX},iw)':h=-2",
                "-f", "image2",
                "-vcodec", "mjpeg",
                "-",
            ],
            timeout=_FRAME_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0 or not completed.stdout:
            raise VideoFrameExtractionError(
                f"ffmpeg could not read a frame at {timestamp:.3f}s of {video_path.name}: "
                f"{_stderr_tail(completed)}"
            )
        frames.append(
            FrameSample(
                timestamp_seconds=timestamp,
                image_base64=base64.b64encode(completed.stdout).decode("ascii"),
                image_media_type=FRAME_MEDIA_TYPE,
            )
        )
    return frames


def sample_video(video_path: Path, *, claimed_duration_seconds: float | None = None) -> tuple[float, list[FrameSample]]:
    """Read the real duration, then sample frames across it.

    Returns ffprobe's duration alongside the frames, because that value --
    not the caller's -- is what the pool entry should carry.
    """
    duration = probe_duration_seconds(video_path)
    warn_on_duration_mismatch(video_path, duration, claimed_duration_seconds)
    return duration, extract_frames(video_path, frame_timestamps(duration))


def representative_frame(frames: list[FrameSample]) -> FrameSample:
    """The frame handed to the single-image vision analyzer.

    The middle of the sampled range, deliberately: it is the cheapest choice
    that is not the opening frame, which is the one systematically most
    likely to be black or blurred. Choosing properly -- across all frames,
    for the cover -- is its own step.
    """
    if not frames:
        raise VideoFrameExtractionError("no frames were extracted")
    return frames[len(frames) // 2]
