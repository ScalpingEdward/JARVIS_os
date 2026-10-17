import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.backup import service as svc

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))


def test_encryption_round_trip_and_wrong_passphrase():
    from backup import decrypt, encrypt
    blob = encrypt(b"hello auron", "correct horse battery")
    assert blob.startswith(b"AURONBK1") and b"hello" not in blob
    assert decrypt(blob, "correct horse battery") == b"hello auron"
    with pytest.raises(Exception):
        decrypt(blob, "wrong passphrase!!")


def test_status_keeps_the_last_good_run_and_alerts_on_trouble(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(svc, "_telegram", sent.append)
    b = svc.BackupService(tmp_path / "s.json")
    now = datetime.now(timezone.utc)
    b.report({"at": now.isoformat(), "ok": True, "places": {"laptop": "ok", "onedrive": "ok", "google_drive": "ok"}})
    assert sent == [] and b.view()["stale"] is False
    b.report({"at": now.isoformat(), "ok": True, "places": {"laptop": "ok", "onedrive": "ok", "google_drive": "Fehler: x"}})
    assert "unvollständig" in sent[-1] and "google_drive" in sent[-1]
    b.report({"at": now.isoformat(), "ok": False, "error": "disk", "places": {}})
    assert "fehlgeschlagen" in sent[-1]
    assert b.view()["last_ok_at"] == now.isoformat()            # a failed run does not erase the last good one


def test_nags_once_a_day_when_stale(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(svc, "_telegram", sent.append)
    b = svc.BackupService(tmp_path / "s.json")
    old = datetime.now(timezone.utc) - timedelta(hours=60)
    b.report({"at": old.isoformat(), "ok": True, "places": {"laptop": "ok", "onedrive": "ok"}})
    assert b.check() is True and b.check() is False and len(sent) == 1
