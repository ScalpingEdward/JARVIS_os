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
import tempfile
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

#: Longest edge a processed video keeps. Instagram shows nothing above
#: 1080x1920 and re-encodes anything larger down to it, so every pixel past
#: this is paid for twice -- once here in memory and encode time, once more
#: when Instagram throws it away. A 4K iPhone clip graded at full size ran
#: the 3.5 GB Docker VM out of memory at 0.1 fps.
MAX_VIDEO_EDGE_PX = 1920

#: Photos keep more than a video frame: Brano posts carousels himself from
#: the app, which scales down on its own, and a crop to 4:5 may still come
#: later. 2560 px leaves room for that without shipping 12 MP originals.
MAX_PHOTO_EDGE_PX = 2560

#: ffmpeg otherwise starts one worker per core for decoding, filtering and
#: encoding each, and every one holds its own frames. On an 8-core laptop
#: with a small VM that alone is enough to hit the memory limit.
_FFMPEG_THREADS = "2"

#: Transfer functions that mark HDR footage. iPhones record HLG
#: (arib-std-b67) by default; smpte2084 is PQ, the other common one.
_HDR_TRANSFERS = frozenset({"arib-std-b67", "smpte2084"})

FFPROBE_BINARY = "ffprobe"

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
    tone_mapped: bool = False

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


def is_hdr(source: Path) -> bool:
    """Whether the first video stream carries an HDR transfer function.

    Asked of the file, not assumed from where it came from: a Lightroom
    export of the same clip is SDR, the untouched iPhone original is HLG.
    """
    completed = _run([
        FFPROBE_BINARY, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=color_transfer", "-of", "csv=p=0", str(source),
    ])
    if completed.returncode != 0:
        raise MediaProcessingError(
            f"ffprobe could not read {source.name}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()[-400:]}"
        )
    # A real iPhone file prints "arib-std-b67," -- the trailing field is its
    # (empty) side-data list. A generated test clip has none and prints the
    # bare value, which is why a plain comparison passed every test and
    # missed every actual HDR video.
    transfer = completed.stdout.decode("utf-8", "replace").strip().split(",")[0]
    return transfer in _HDR_TRANSFERS


def _fit_filter(max_edge: int) -> str:
    """Shrink so neither edge exceeds max_edge, keeping the shape. Never
    upscales -- min() leaves anything already small enough untouched."""
    return (
        f"scale='min({max_edge},iw)':'min({max_edge},ih)'"
        f":force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


#: HDR -> SDR. The LUT is a Lightroom look built on SDR Rec.709; applied to
#: HLG values it lands on the wrong colours. Linearise, map the highlights
#: down with hable, and hand the LUT the Rec.709 picture it was made for.
_TONEMAP_FILTERS = [
    "zscale=t=linear:npl=100",
    "format=gbrpf32le",
    "zscale=p=bt709",
    "tonemap=tonemap=hable:desat=0",
    "zscale=t=bt709:m=bt709:r=tv",
    "format=yuv420p",
]


def _build_video_filters(
    ratio: tuple[int, int] | None,
    lut: Path | None,
    *,
    max_edge: int | None = None,
    tone_map: bool = False,
) -> list[str]:
    # Order matters for cost: crop and shrink first, so the tone map and the
    # LUT -- both per-pixel float work -- only ever see the pixels that ship.
    filters = []
    if ratio is not None:
        filters.append(_crop_filter(ratio))
    if max_edge is not None:
        filters.append(_fit_filter(max_edge))
    if tone_map:
        filters.extend(_TONEMAP_FILTERS)
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
    tone_map = is_hdr(source)
    destination = _destination(source, output_name)
    # -threads before -i limits the decoder, after it the encoder;
    # -filter_threads covers the filter graph in between.
    command = [FFMPEG_BINARY, "-y", "-threads", _FFMPEG_THREADS, "-filter_threads", _FFMPEG_THREADS]
    if trim_start_seconds is not None:
        # Before -i: ffmpeg seeks rather than decoding and discarding.
        command += ["-ss", f"{trim_start_seconds:.3f}"]
    command += ["-i", str(source)]
    if trim_end_seconds is not None:
        command += ["-t", f"{trim_end_seconds - trim_start_seconds:.3f}"]

    filters = _build_video_filters(ratio, lut, max_edge=MAX_VIDEO_EDGE_PX, tone_map=tone_map)
    command += ["-vf", ",".join(filters)]
    command += [
        "-threads", _FFMPEG_THREADS,
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
        tone_mapped=tone_map,
    )


def _upright_copy(source: Path) -> Path | None:
    """ffmpeg ignores the EXIF orientation flag, so a portrait phone photo
    stored sideways would come out sideways. Pillow applies the flag; the
    upright pixels go to a temp file that ffmpeg then grades. None when the
    file is already upright (or Pillow cannot read it -- ffmpeg gets the
    original and fails loudly on its own if it cannot either)."""
    try:
        from PIL import Image, ImageOps

        with Image.open(source) as image:
            if image.getexif().get(0x0112, 1) == 1:
                return None
            upright = ImageOps.exif_transpose(image)
            handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            handle.close()
            upright.save(handle.name, format="PNG")
            return Path(handle.name)
    except Exception:  # noqa: BLE001
        return None


def process_image(
    source: Path,
    *,
    ratio: tuple[int, int] | None = RATIO_FEED,
    output_name: str | None = None,
    max_edge: int | None = MAX_PHOTO_EDGE_PX,
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
    upright = _upright_copy(source)
    filters = _build_video_filters(ratio, lut, max_edge=max_edge)
    command = [FFMPEG_BINARY, "-y", "-i", str(upright or source)]
    if filters:
        command += ["-vf", ",".join(filters)]
    command += ["-q:v", "2", str(destination)]

    try:
        completed = _run(command)
    finally:
        if upright is not None:
            upright.unlink(missing_ok=True)
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
