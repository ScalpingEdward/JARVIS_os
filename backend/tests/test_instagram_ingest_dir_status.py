"""Watching the sweeper that keeps the video handoff directory clear.

Three processes touch this directory and exactly one of them may delete:
n8n writes and never deletes, AURON reads and never deletes, and the
ingest-sweeper sidecar removes anything past the retention window on a timer.
Files are never reused -- the next run downloads and overwrites, since a
leftover is the likeliest candidate for a truncated download.

So a file inside the window is unremarkable. A file OLDER than it is the
signal these tests are about: it means the sweeper has stopped. The sweeper
itself is silent by design, so without this the first sign of it dying would
be a full disk. AURON reports that state on every ingest and on demand -- and
being mounted read-only, it cannot make the evidence go away by cleaning.
"""

import logging
import os
import time

import pytest

from app.instagram_content.analyze_and_ingest import _report_ingest_directory
from app.instagram_content.ingest_paths import (
    DEFAULT_RETENTION_HOURS,
    ingest_directory_status,
    retention_hours,
)

HOUR = 3600


@pytest.fixture
def ingest_dir(tmp_path, monkeypatch):
    root = tmp_path / "ingest"
    root.mkdir()
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(root))
    return root


def _file(root, name: str, *, age_hours: float = 0.0, size: int = 1024):
    path = root / name
    path.write_bytes(b"x" * size)
    if age_hours:
        stamp = time.time() - age_hours * HOUR
        os.utime(path, (stamp, stamp))
    return path


# -- the retention window is configuration ----------------------------------


def test_the_retention_window_defaults_to_24_hours():
    assert retention_hours() == DEFAULT_RETENTION_HOURS == 24.0


def test_the_retention_window_can_be_configured(monkeypatch):
    monkeypatch.setenv("AURON_INGEST_RETENTION_HOURS", "12")
    assert retention_hours() == 12.0


def test_a_nonsense_retention_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("AURON_INGEST_RETENTION_HOURS", "soon")
    assert retention_hours() == DEFAULT_RETENTION_HOURS
    monkeypatch.setenv("AURON_INGEST_RETENTION_HOURS", "0")
    assert retention_hours() == DEFAULT_RETENTION_HOURS


# -- what the directory reports ---------------------------------------------


def test_an_empty_directory_reports_nothing_pending(ingest_dir):
    status = ingest_directory_status()
    assert (status.file_count, status.total_bytes, status.oldest_age_hours) == (0, 0, None)
    assert status.stale_files == []
    assert status.available is True


def test_count_size_and_oldest_age_are_reported(ingest_dir):
    _file(ingest_dir, "a.mp4", size=1000)
    _file(ingest_dir, "b.mp4", age_hours=5, size=2000)
    _file(ingest_dir, "c.mp4", age_hours=40, size=3000)

    status = ingest_directory_status()

    assert status.file_count == 3
    assert status.total_bytes == 6000
    assert status.oldest_age_hours == pytest.approx(40, abs=0.1)
    assert status.retention_hours == 24.0


def test_only_files_past_the_window_count_as_stale(ingest_dir, monkeypatch):
    """A recently handed-over file is normal and must not be flagged -- only
    one the sweeper should already have taken."""
    monkeypatch.setenv("AURON_INGEST_RETENTION_HOURS", "24")
    _file(ingest_dir, "fresh.mp4", age_hours=1)
    _file(ingest_dir, "today.mp4", age_hours=20)
    _file(ingest_dir, "sweeper_missed_this.mp4", age_hours=100)

    status = ingest_directory_status()

    assert [f.name for f in status.stale_files] == ["sweeper_missed_this.mp4"]
    assert status.file_count == 3, "everything is still counted, not just the stale ones"


def test_stale_is_measured_against_the_same_window_the_sweeper_uses(ingest_dir, monkeypatch):
    """One definition of the window, read by both the api and the sweeper.
    Two thresholds would drift and AURON would flag files the sweeper has no
    intention of touching yet."""
    monkeypatch.setenv("AURON_INGEST_RETENTION_HOURS", "10")
    _file(ingest_dir, "keep.mp4", age_hours=5)
    _file(ingest_dir, "sweep.mp4", age_hours=20)

    status = ingest_directory_status()

    assert status.retention_hours == 10.0
    assert [f.name for f in status.stale_files] == ["sweep.mp4"]
    assert status.stale_files[0].stale is True


def test_subdirectories_are_not_counted_as_files(ingest_dir):
    (ingest_dir / "nested").mkdir()
    _file(ingest_dir, "a.mp4")
    assert ingest_directory_status().file_count == 1


def test_a_missing_directory_is_reported_not_crashed(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(tmp_path / "gone"))

    status = ingest_directory_status()

    assert status.available is False
    assert "not readable" in status.detail
    assert status.file_count == 0


def test_the_status_is_read_only_and_leaves_every_file_alone(ingest_dir):
    """AURON mounts this directory read-only. Reporting must never be
    mistaken for cleaning -- if it cleaned, it would erase the very evidence
    that the sweeper has stopped."""
    _file(ingest_dir, "sweeper_missed_this.mp4", age_hours=500)

    ingest_directory_status()

    assert (ingest_dir / "sweeper_missed_this.mp4").exists()


# -- it is stated on every ingest, not only when something sweeps -----------


def test_an_empty_directory_is_still_mentioned(ingest_dir, caplog):
    with caplog.at_level(logging.INFO):
        _report_ingest_directory()
    assert any("empty" in r.getMessage() for r in caplog.records)


def test_files_within_the_window_are_reported_without_alarm(ingest_dir, caplog):
    _file(ingest_dir, "a.mp4", age_hours=2, size=2_097_152)

    with caplog.at_level(logging.INFO):
        _report_ingest_directory()

    record = next(r for r in caplog.records if "ingest directory holds" in r.getMessage())
    assert record.levelno == logging.INFO
    assert "1 file(s)" in record.getMessage()
    assert "2.0 MB" in record.getMessage()


def test_a_file_past_the_window_is_a_warning_and_names_it(ingest_dir, caplog):
    """The whole purpose: a stopped sweeper announces itself here, on an
    ordinary ingest, rather than eventually as a full disk."""
    _file(ingest_dir, "sweeper_missed_this.mp4", age_hours=100)

    with caplog.at_level(logging.INFO):
        _report_ingest_directory()

    record = next(r for r in caplog.records if "ingest directory holds" in r.getMessage())
    assert record.levelno == logging.WARNING
    assert "sweeper_missed_this.mp4" in record.getMessage()
    assert "24" in record.getMessage()


def test_an_unavailable_directory_is_warned_about(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("JARVIS_INGEST_DIR", str(tmp_path / "gone"))

    with caplog.at_level(logging.INFO):
        _report_ingest_directory()

    assert any(
        r.levelno == logging.WARNING and "unavailable" in r.getMessage() for r in caplog.records
    )


# -- the endpoint -----------------------------------------------------------


def test_the_endpoint_exposes_the_same_state(ingest_dir):
    from fastapi.testclient import TestClient

    from app.main import app

    _file(ingest_dir, "sweeper_missed_this.mp4", age_hours=100, size=4096)

    response = TestClient(app).get("/v1/instagram/media-pool/ingest-dir")

    assert response.status_code == 200
    body = response.json()
    assert body["file_count"] == 1
    assert body["total_bytes"] == 4096
    assert body["retention_hours"] == 24.0
    assert [f["name"] for f in body["stale_files"]] == ["sweeper_missed_this.mp4"]
