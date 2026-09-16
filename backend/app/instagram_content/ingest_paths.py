from __future__ import annotations

import os
from pathlib import Path

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
