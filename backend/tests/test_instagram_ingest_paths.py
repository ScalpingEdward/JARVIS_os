"""The path handoff between n8n and AURON, and what it refuses to open.

n8n downloads a video from Drive, writes it into a directory both containers
see, and passes the path -- instead of ~26 MB of base64 per video through
the request body. The directory is mounted into the API container read-only
and only the ingest subdirectory is exposed.

A path in a request body is input, not an instruction. These tests pin down
that nothing inside one can widen what AURON is willing to read.
"""

import os
import sys

import pytest

from app.instagram_content.ingest_paths import (
    IngestPathError,
    ingest_root,
    resolve_ingest_path,
)


@pytest.fixture
def ingest_dir(tmp_path, monkeypatch):
    root = tmp_path / "ingest"
    root.mkdir()
    (root / "clip.mp4").write_bytes(b"not really an mp4, but a real file")
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(root))
    return root


# -- the happy path ---------------------------------------------------------


def test_a_relative_path_resolves_inside_the_root(ingest_dir):
    assert resolve_ingest_path("clip.mp4") == (ingest_dir / "clip.mp4").resolve()


def test_an_absolute_path_inside_the_root_is_accepted(ingest_dir):
    assert resolve_ingest_path(str(ingest_dir / "clip.mp4")) == (ingest_dir / "clip.mp4").resolve()


def test_a_file_in_a_subdirectory_of_the_root_is_accepted(ingest_dir):
    nested = ingest_dir / "2026-09-16"
    nested.mkdir()
    (nested / "clip.mov").write_bytes(b"x")
    assert resolve_ingest_path("2026-09-16/clip.mov") == (nested / "clip.mov").resolve()


def test_every_allowed_extension_is_accepted_case_insensitively(ingest_dir):
    for name in ("a.MP4", "b.Mov", "c.m4v"):
        (ingest_dir / name).write_bytes(b"x")
        assert resolve_ingest_path(name).name == name


def test_the_root_comes_from_the_environment(ingest_dir):
    assert ingest_root() == ingest_dir


# -- escaping the root ------------------------------------------------------


def test_traversal_out_of_the_root_is_refused(ingest_dir, tmp_path):
    (tmp_path / "secret.mp4").write_bytes(b"x")

    with pytest.raises(IngestPathError, match="outside the ingest directory"):
        resolve_ingest_path("../secret.mp4")


def test_deep_traversal_is_refused(ingest_dir):
    with pytest.raises(IngestPathError):
        resolve_ingest_path("../../../../etc/passwd")


def test_traversal_that_dips_back_in_is_still_evaluated_on_the_real_target(ingest_dir, tmp_path):
    """'sub/../../outside.mp4' normalises to outside the root. The check runs
    on the resolved target, so the harmless-looking prefix changes nothing."""
    (tmp_path / "outside.mp4").write_bytes(b"x")
    (ingest_dir / "sub").mkdir()

    with pytest.raises(IngestPathError, match="outside the ingest directory"):
        resolve_ingest_path("sub/../../outside.mp4")


def test_an_absolute_path_elsewhere_on_the_filesystem_is_refused(ingest_dir, tmp_path):
    (tmp_path / "elsewhere.mp4").write_bytes(b"x")

    with pytest.raises(IngestPathError, match="outside the ingest directory"):
        resolve_ingest_path(str(tmp_path / "elsewhere.mp4"))


@pytest.mark.skipif(
    sys.platform == "win32" and not os.environ.get("CI"),
    reason="creating a symlink on Windows needs developer mode or admin rights",
)
def test_a_symlink_pointing_out_of_the_root_is_refused(ingest_dir, tmp_path):
    """The reason resolve() is used rather than a string prefix check: a link
    sitting legitimately inside the root can still target anything."""
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    try:
        (ingest_dir / "link.mp4").symlink_to(outside)
    except OSError as exc:  # pragma: no cover - platform dependent
        pytest.skip(f"symlinks unavailable here: {exc}")

    with pytest.raises(IngestPathError, match="outside the ingest directory"):
        resolve_ingest_path("link.mp4")


# -- not a file we will open ------------------------------------------------


def test_a_missing_file_is_refused(ingest_dir):
    with pytest.raises(IngestPathError, match="no such file"):
        resolve_ingest_path("nope.mp4")


def test_a_directory_is_refused(ingest_dir):
    (ingest_dir / "adir.mp4").mkdir()

    with pytest.raises(IngestPathError, match="not a regular file"):
        resolve_ingest_path("adir.mp4")


def test_an_unexpected_extension_is_refused(ingest_dir):
    (ingest_dir / "payload.sh").write_bytes(b"#!/bin/sh\n")

    with pytest.raises(IngestPathError, match="unsupported extension"):
        resolve_ingest_path("payload.sh")


def test_an_extensionless_file_is_refused(ingest_dir):
    (ingest_dir / "clip").write_bytes(b"x")

    with pytest.raises(IngestPathError, match="unsupported extension"):
        resolve_ingest_path("clip")


def test_an_empty_path_is_refused(ingest_dir):
    with pytest.raises(IngestPathError, match="empty"):
        resolve_ingest_path("")
    with pytest.raises(IngestPathError, match="empty"):
        resolve_ingest_path("   ")


def test_a_null_byte_is_refused(ingest_dir):
    with pytest.raises(IngestPathError, match="null byte"):
        resolve_ingest_path("clip.mp4\x00.txt")


def test_a_missing_ingest_directory_is_reported_not_crashed(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(tmp_path / "does-not-exist"))

    with pytest.raises(IngestPathError, match="not available"):
        resolve_ingest_path("clip.mp4")


# -- the ingest endpoint fails that item, not the batch ---------------------


def test_a_bad_video_path_fails_only_its_own_item(ingest_dir, monkeypatch):
    from app.instagram_content.analyze_and_ingest import analyze_and_ingest
    from app.instagram_content.media_pool_models import MediaAnalyzeAndIngestItem
    from app.instagram_content.media_pool_service import MediaPoolService
    from app.instagram_content.models import MediaType
    from app.instagram_content.vision_analysis import VisionAnalysisResult

    class _StubAnalyzer:
        def analyze(self, **kwargs):
            return VisionAnalysisResult(
                theme="gym-mirror-selfie", tags=["gym"], aesthetic_score=0.7, reasoning="stub"
            )

    service = MediaPoolService()
    service.reset()

    response = analyze_and_ingest(
        items=[
            MediaAnalyzeAndIngestItem(
                media_ref="escapes", media_type=MediaType.video,
                duration_seconds=9.3, video_path="../outside.mp4",
            ),
            MediaAnalyzeAndIngestItem(
                media_ref="fine", media_type=MediaType.image,
                image_base64="ZmFrZQ==", image_media_type="image/jpeg",
            ),
        ],
        analyzer=_StubAnalyzer(),
        pool_service=service,
    )

    by_ref = {r.media_ref: r for r in response.results}
    assert by_ref["escapes"].success is False
    assert "ingest directory" in by_ref["escapes"].error
    assert by_ref["fine"].success is True
    assert response.analyzed_and_ingested == 1
