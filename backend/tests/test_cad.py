import shutil

import pytest

from app.assistant import tools
from app.cad import engine, service
from app.dashboard_layout import ui

CUBE = b"""solid t
facet normal 0 0 1
 outer loop
  vertex 0 0 0
  vertex 80 0 0
  vertex 80 40 12.5
 endloop
endfacet
endsolid t
"""


class FakeEngine:
    name, language = "fake", "OpenSCAD"

    def build(self, source):
        engine.OpenScadEngine().check(source)
        if "fehler" in source:
            raise engine.CadError("OpenSCAD: ERROR: Parser error in line 1")
        return CUBE


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AURON_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(service, "get_engine", lambda: FakeEngine())


def test_auron_designs_a_part_it_is_stored_measured_and_shown():
    start = ui.since(0)["last"]
    out, failed = tools.run("cad", {"action": "create", "name": "Handyhalterung", "source": "cube([80,40,12.5]);"})
    assert not failed and '"size_mm": [80.0, 40.0, 12.5]' in out
    assert ui.since(start)["commands"][-1]["do"] == "show_model"
    p = service.find("halterung")
    assert service.get(p["id"])["source"] == "cube([80,40,12.5]);" and service.stl(p["id"]) == CUBE
    out, _ = tools.run("cad", {"action": "update", "part": "Handyhalterung", "source": "cube([80,40,14.5]);"})
    assert '"version": 2' in out and len(service.parts()) == 1


def test_an_engine_error_comes_back_to_auron_and_nothing_is_stored():
    out, _ = tools.run("cad", {"action": "create", "name": "Kaputt", "source": "fehler("})
    assert "Parser error" in out and "fix the source" in out and service.parts() == []


def test_reading_files_from_the_machine_is_refused():
    for src in ('include <x.scad>', 'use <y.scad>', 'import("/etc/passwd");', 'surface(file="/app/x");'):
        with pytest.raises(engine.CadError):
            engine.OpenScadEngine().check(src)


def test_a_new_engine_is_picked_by_name(monkeypatch):
    monkeypatch.setenv("CAD_ENGINE", "solidworks")
    with pytest.raises(engine.CadError):
        engine.get_engine()


@pytest.mark.skipif(not shutil.which("openscad"), reason="OpenSCAD not installed here")
def test_openscad_builds_a_real_part():
    assert service.bbox(engine.OpenScadEngine().build("cube([10,20,5]);")) == [10.0, 20.0, 5.0]
