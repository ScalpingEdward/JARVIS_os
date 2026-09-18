"""Actually cutting, cropping and grading a file -- the step that was only
ever described before.

`edit_plan.py` has always written down what should happen to a media item:
crop to this ratio, apply that grade, trim to this window. Nothing carried
it out. n8n's image has no ffmpeg, the publish workflow only makes the
original file public and hands Instagram its URL, so what went out was
whatever came in.

The capability was here the whole time -- ffmpeg and Pillow both live in
this container, and the ingest step already has the file on disk. This
module is the missing execution.

Three deliberate boundaries:

* **Never touches the source.** Every operation writes a new file to the
  output directory. The Drive original stays exactly as uploaded, so a bad
  grade or a wrong crop costs a re-run, never the footage.
* **No LUT means no grade, not a guessed one.** Colour is Brano's own look,
  exported from Lightroom as a .cube file. Without it the geometry and the
  cut still run, and the file comes back honestly ungraded rather than
  approximated with invented curve values.
* **Failure is loud.** A refused crop or a broken cut raises instead of
  silently passing the original through -- an unprocessed file that claims
  to be processed is exactly the kind of quiet lie this project has paid
  for twice already.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

FFMPEG_BINARY = "ffmpeg"

#: Where processed files are written. A separate directory from the ingest
#: one, which AURON mounts read-only: n8n writes there, AURON reads. This is
#: the other direction -- AURON writes, n8n picks up and uploads.
_OUTPUT_DIR_ENV = "JARVIS_PROCESSED_DIR"
_DEFAULT_OUTPUT_DIR = "/data/images/processed"

#: Brano's own Lightroom look, exported as a 3D LUT. Absent, grading is
#: skipped rather than approximated.
_LUT_PATH_ENV = "AURON_COLOR_LUT"

#: Instagram's real display ratios. 4:5 is the tallest the feed still shows
#: at full size; 9:16 is the Reel/full-screen format.
RATIO_FEED = (4, 5)
RATIO_REEL = (9, 16)

_TIMEOUT_SECONDS = 300.0


class MediaProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessedMedia:
    """What came out, and what was actually done to it -- each flag is a
    fact about this file, not a copy of what was requested."""

    path: Path
    cropped_to: tuple[int, int] | None = None
    trimmed_from: float | None = None
    trimmed_to: float | None = None
    graded: bool = False

    @property
    def was_trimmed(self) -> bool:
        return self.trimmed_from is not None


def output_dir() -> Path:
    return Path(os.environ.get(_OUTPUT_DIR_ENV, _DEFAULT_OUTPUT_DIR))


def lut_path() -> Path | None:
    """The configured LUT, only if it is really there. A path pointing at a
    missing file is the same as no LUT -- ffmpeg would fail the whole
    operation over it, and losing a cut because a colour file moved would be
    absurd."""
    raw = os.environ.get(_LUT_PATH_ENV)
    if not raw:
        return None
    path = Path(raw)
    if not path.is_file():
        logger.warning("AURON_COLOR_LUT points at %s, which does not exist -- continuing ungraded", path)
        return None
    return path


def _run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(command, capture_output=True, timeout=_TIMEOUT_SECONDS, check=False)
    except FileNotFoundError as exc:
        raise MediaProcessingError(f"{command[0]} is not installed in this container") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessingError(f"{command[0]} timed out after {_TIMEOUT_SECONDS}s") from exc


def _crop_filter(ratio: tuple[int, int]) -> str:
    """Centre crop to a ratio without ever upscaling.

    Picks the largest rectangle of the target shape that fits inside the
    source and takes it from the centre. Phone footage is usually already
    9:16 or 4:3, so this is typically a small trim rather than a reframe --
    but it is a crop, not a stretch: nothing here changes the subject's
    proportions.
    """
    w, h = ratio
    return (
        f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})'"
        f":'(iw-min(iw,ih*{w}/{h}))/2':'(ih-min(ih,iw*{h}/{w}))/2'"
    )


def _build_video_filters(ratio: tuple[int, int] | None, lut: Path | None) -> list[str]:
    filters = []
    if ratio is not None:
        filters.append(_crop_filter(ratio))
    if lut is not None:
        # ffmpeg's filter syntax treats ':' and '\' specially; a Windows-style
        # path would otherwise be read as further filter arguments.
        escaped = str(lut).replace("\\", "/").replace(":", "\\:")
        filters.append(f"lut3d='{escaped}'")
    return filters


def process_video(
    source: Path,
    *,
    ratio: tuple[int, int] | None = RATIO_REEL,
    trim_start_seconds: float | None = None,
    trim_end_seconds: float | None = None,
    output_name: str | None = None,
) -> ProcessedMedia:
    """Cut, crop and grade one video into a new file.

    Re-encodes rather than stream-copies: a crop and a LUT both require it,
    and a stream copy could only cut on keyframes, which would move the cut
    by up to several seconds away from the window the frame analysis
    actually chose.
    """
    if not source.is_file():
        raise MediaProcessingError(f"no such video: {source}")
    if (trim_start_seconds is None) != (trim_end_seconds is None):
        raise MediaProcessingError("a trim needs both a start and an end, or neither")
    if trim_start_seconds is not None:
        if trim_start_seconds < 0:
            raise MediaProcessingError("trim start cannot be negative")
        if trim_end_seconds <= trim_start_seconds:
            raise MediaProcessingError(
                f"trim end ({trim_end_seconds}) must be after its start ({trim_start_seconds})"
            )

    lut = lut_path()
    destination = _destination(source, output_name)
    command = [FFMPEG_BINARY, "-y"]
    if trim_start_seconds is not None:
        # Before -i: ffmpeg seeks rather than decoding and discarding.
        command += ["-ss", f"{trim_start_seconds:.3f}"]
    command += ["-i", str(source)]
    if trim_end_seconds is not None:
        command += ["-t", f"{trim_end_seconds - trim_start_seconds:.3f}"]

    filters = _build_video_filters(ratio, lut)
    if filters:
        command += ["-vf", ",".join(filters)]
    command += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",       # what every player and Instagram expects
        "-movflags", "+faststart",   # metadata at the front, so playback starts immediately
        "-c:a", "aac", "-b:a", "192k",
        str(destination),
    ]

    completed = _run(command)
    if completed.returncode != 0 or not destination.is_file():
        raise MediaProcessingError(
            f"ffmpeg could not process {source.name}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()[-400:]}"
        )
    return ProcessedMedia(
        path=destination,
        cropped_to=ratio,
        trimmed_from=trim_start_seconds,
        trimmed_to=trim_end_seconds,
        graded=lut is not None,
    )


def process_image(
    source: Path,
    *,
    ratio: tuple[int, int] | None = RATIO_FEED,
    output_name: str | None = None,
) -> ProcessedMedia:
    """Crop and grade one photo into a new file.

    Runs through ffmpeg rather than Pillow so a photo and a video get the
    identical crop arithmetic and the identical LUT applied the identical
    way. Two implementations of "the account's look" would drift, and the
    whole point of one grade is that a feed reads as one feed.
    """
    if not source.is_file():
        raise MediaProcessingError(f"no such image: {source}")

    lut = lut_path()
    destination = _destination(source, output_name)
    filters = _build_video_filters(ratio, lut)
    command = [FFMPEG_BINARY, "-y", "-i", str(source)]
    if filters:
        command += ["-vf", ",".join(filters)]
    command += ["-q:v", "2", str(destination)]

    completed = _run(command)
    if completed.returncode != 0 or not destination.is_file():
        raise MediaProcessingError(
            f"ffmpeg could not process {source.name}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()[-400:]}"
        )
    return ProcessedMedia(path=destination, cropped_to=ratio, graded=lut is not None)


def _destination(source: Path, output_name: str | None) -> Path:
    directory = output_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MediaProcessingError(f"cannot write to {directory}: {exc}") from exc
    if not os.access(directory, os.W_OK):
        raise MediaProcessingError(
            f"{directory} is not writable -- AURON mounts the ingest directory read-only "
            f"on purpose; processed files need their own writable directory."
        )
    return directory / (output_name or source.name)


def free_output_space_bytes() -> int | None:
    """How much room is left where processed files go. None when the
    directory is not reachable at all."""
    try:
        return shutil.disk_usage(output_dir()).free
    except OSError:
        return None
