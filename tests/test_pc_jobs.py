import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import pc_jobs  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    roots = {"Desktop": tmp_path / "Plocha", "Dokumente": tmp_path / "Dokumenty", "Downloads": tmp_path / "Downloads"}
    for r in roots.values():
        r.mkdir()
    monkeypatch.setattr(pc_jobs, "ROOTS", roots)
    monkeypatch.setattr(pc_jobs, "TRASH", roots["Dokumente"] / "AURON-Papierkorb")
    monkeypatch.setattr(pc_jobs, "LOG", roots["Dokumente"] / "AURON-Protokoll.txt")
    return roots


def test_a_checked_plan_moves_copies_writes_and_never_deletes(home):
    d = home["Desktop"]
    (d / "a.jpg").write_text("x"); (d / "b.pdf").write_text("y"); (d / "old.txt").write_text("z")
    steps = [{"op": "mkdir", "path": str(d / "Bilder")},
             {"op": "move", "from": str(d / "a.jpg"), "to": str(d / "Bilder")},
             {"op": "copy", "from": str(d / "b.pdf"), "to": str(home["Dokumente"] / "b.pdf")},
             {"op": "write", "path": str(home["Dokumente"] / "Notiz.txt"), "text": "Hallo"},
             {"op": "trash", "path": str(d / "old.txt")}]
    report = pc_jobs.run(steps, "Desktop aufräumen")
    assert (d / "Bilder" / "a.jpg").exists() and (d / "b.pdf").exists() and (home["Dokumente"] / "b.pdf").exists()
    assert (home["Dokumente"] / "Notiz.txt").read_text(encoding="utf-8") == "Hallo"
    assert not (d / "old.txt").exists() and len(list(pc_jobs.TRASH.iterdir())) == 1   # in the bin, not gone
    assert "ABGEBROCHEN" not in report and "Desktop aufräumen" in pc_jobs.LOG.read_text(encoding="utf-8")


def test_anything_outside_the_three_folders_or_with_secrets_is_refused(home, tmp_path):
    for bad in ([{"op": "move", "from": str(tmp_path / "x"), "to": str(home["Desktop"])}],            # outside
                [{"op": "move", "from": str(home["Desktop"] / ".." / ".." / "Windows"), "to": str(home["Desktop"])}],
                [{"op": "copy", "from": str(home["Desktop"] / "Instagram token.txt"), "to": str(home["Dokumente"])}],
                [{"op": "move", "from": str(home["Downloads"] / ".env"), "to": str(home["Dokumente"])}],
                [{"op": "delete", "path": str(home["Desktop"] / "a")}],                                 # no such step
                [{"op": "run", "cmd": "rm -rf /"}], []):
        with pytest.raises(pc_jobs.PlanError):
            pc_jobs.check(bad)


def test_nothing_is_overwritten_and_the_plan_is_read_from_the_last_json_block(home):
    d = home["Desktop"]
    (d / "a.txt").write_text("1"); (home["Dokumente"] / "a.txt").write_text("2")
    report = pc_jobs.run([{"op": "move", "from": str(d / "a.txt"), "to": str(home["Dokumente"])}], "x")
    assert "ABGEBROCHEN" in report and (d / "a.txt").exists() and (home["Dokumente"] / "a.txt").read_text() == "2"
    summary, steps = pc_jobs.parse("Ich räume auf.\nSensible Daten: keine\n```json\n" + json.dumps([{"op": "mkdir", "path": "x"}]) + "\n```")
    assert summary.startswith("Ich räume auf") and steps == [{"op": "mkdir", "path": "x"}]
