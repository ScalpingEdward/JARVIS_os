from __future__ import annotations

import os
import time
from pathlib import Path

from .media_pool_models import IngestDirectoryFile, IngestDirectoryStatus

#: Where n8n drops a downloaded video for AURON to read. Mounted into the API
#: container read-only, and only this subdirectory -- n8n writes, AURON reads.
#: Overridable so tests (and any future relocation) do not depend on the
#: container layout.
_DEFAULT_INGEST_ROOT = "/data/images/ingest"

_INGEST_ROOT_ENV = "JARVIS_INGEST_DIR"

#: Container formats the frame extraction step can actually open. An
#: allowlist rather than a denylist: anything not named here is refused,
#: so a new extension has to be a deliberate decision.
ALLOWED_VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v"})


#: How long a leftover file may sit here before it counts as residue. A file
#: is only deleted once AURON confirms its item ingested, so anything still
#: around is from a run that failed -- and a failed download can have left a
#: truncated file behind. Nothing here is ever reused: the next run downloads
#: and overwrites regardless, so the window bounds how long the residue is
#: visible, not how long it is trusted.
_RETENTION_HOURS_ENV = "AURON_INGEST_RETENTION_HOURS"
DEFAULT_RETENTION_HOURS = 72.0


def retention_hours() -> float:
    raw = os.environ.get(_RETENTION_HOURS_ENV)
    if not raw:
        return DEFAULT_RETENTION_HOURS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_RETENTION_HOURS
    return value if value > 0 else DEFAULT_RETENTION_HOURS


def ingest_directory_status(*, now: float | None = None) -> IngestDirectoryStatus:
    """What is currently lying in the handoff directory.

    Read-only by design: this reports, it never deletes. AURON mounts the
    directory read-only and n8n is the only writer, so cleaning up is n8n's
    job -- `stale_files` tells it exactly what has outlived the window, from
    a single definition of that window rather than two that drift.
    """
    window = retention_hours()
    reference = now if now is not None else time.time()
    root = ingest_root()

    try:
        entries = [entry for entry in root.iterdir() if entry.is_file()]
    except OSError as exc:
        return IngestDirectoryStatus(
            file_count=0, total_bytes=0, retention_hours=window,
            available=False, detail=f"{root} is not readable: {exc}",
        )

    files: list[IngestDirectoryFile] = []
    total_bytes = 0
    oldest: float | None = None
    for entry in entries:
        try:
            stat = entry.stat()
        except OSError:
            continue  # vanished between listing and stat -- n8n owns this directory
        age_hours = max(0.0, (reference - stat.st_mtime) / 3600)
        total_bytes += stat.st_size
        oldest = age_hours if oldest is None else max(oldest, age_hours)
        files.append(IngestDirectoryFile(
            name=entry.name, size_bytes=stat.st_size,
            age_hours=round(age_hours, 3), stale=age_hours > window,
        ))

    return IngestDirectoryStatus(
        file_count=len(files),
        total_bytes=total_bytes,
        oldest_age_hours=round(oldest, 3) if oldest is not None else None,
        retention_hours=window,
        stale_files=[f for f in files if f.stale],
    )


class IngestPathError(ValueError):
    """A supplied path is not something AURON is willing to open."""


def ingest_root() -> Path:
    return Path(os.environ.get(_INGEST_ROOT_ENV, _DEFAULT_INGEST_ROOT))


def resolve_ingest_path(video_path: str) -> Path:
    """Turns a caller-supplied path into a real file inside the ingest
    directory, or refuses.

    A path arriving in a request is input, not an instruction: it says which
    file to read, and nothing it contains may widen what AURON is allowed to
    read. Every check below exists to keep that true.

    Accepts a path relative to the ingest root ("abc123.mp4") or an absolute
    one that lands inside it. Everything else -- traversal, a symlink
    pointing out of the root, a directory, a device node, an unexpected
    extension -- is refused with a reason rather than opened.
    """
    if not video_path or not video_path.strip():
        raise IngestPathError("video_path is empty")

    if "\x00" in video_path:
        raise IngestPathError("video_path contains a null byte")

    root = ingest_root()
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise IngestPathError(f"the ingest directory {root} is not available: {exc}") from exc

    candidate = Path(video_path)
    combined = candidate if candidate.is_absolute() else resolved_root / candidate

    try:
        # resolve() follows symlinks, so a link pointing out of the root
        # lands outside it here and is caught by the containment check
        # below -- the link itself never needs to be special-cased.
        resolved = combined.resolve(strict=True)
    except FileNotFoundError as exc:
        raise IngestPathError(f"no such file under the ingest directory: {video_path!r}") from exc
    except OSError as exc:
        raise IngestPathError(f"cannot resolve {video_path!r}: {exc}") from exc

    if not resolved.is_relative_to(resolved_root):
        # Covers ".." traversal, an absolute path elsewhere on the filesystem,
        # and a symlink whose target lives outside the root.
        raise IngestPathError(f"{video_path!r} resolves outside the ingest directory")

    if not resolved.is_file():
        raise IngestPathError(f"{video_path!r} is not a regular file")

    if resolved.suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_SUFFIXES))
        raise IngestPathError(f"{video_path!r} has an unsupported extension (allowed: {allowed})")

    return resolved
