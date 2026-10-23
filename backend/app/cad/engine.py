"""The CAD engine behind AURON's 3D parts -- one interchangeable piece (Brano, 2026-10-23: "if we get
something as strong as SolidWorks later, we swap it in without rebuilding").

An engine takes a part's source in its own language and returns an STL (millimetres). Everything else --
storage, the dashboard's 3D view, AURON's tool -- only knows this interface. A new engine (CadQuery,
build123d, Onshape's API, a local SolidWorks bridge) is one class here and one entry in ENGINES;
CAD_ENGINE in .env picks it.

OpenSCAD first: free, runs headless, and its language can only describe shapes -- AURON writing a part
never means AURON running Python in the API container. What OpenSCAD could still do with files
(include/use/import/surface) is refused before it runs.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol


class CadError(ValueError):
    pass


class CadEngine(Protocol):
    name: str
    language: str          # what AURON writes, named in his tool's description

    def build(self, source: str) -> bytes:
        """The part as STL bytes, or CadError with the engine's own message (so AURON can fix his code)."""
        ...


class OpenScadEngine:
    name = "openscad"
    language = "OpenSCAD"
    TIMEOUT_S = 90
    # reading files from the machine: never in a part AURON writes
    FORBIDDEN = re.compile(r"\b(include|use)\s*<|\b(import|surface)\s*\(", re.I)

    def __init__(self, binary: str | None = None):
        self.binary = binary or shutil.which("openscad") or "openscad"

    def check(self, source: str) -> None:
        if len(source) > 60_000:
            raise CadError("Quelltext zu lang (höchstens 60 000 Zeichen)")
        if self.FORBIDDEN.search(source):
            raise CadError("include/use/import/surface sind gesperrt -- das Teil muss sich selbst beschreiben")

    def build(self, source: str) -> bytes:
        self.check(source)
        with tempfile.TemporaryDirectory(prefix="cad-") as d:
            src, out = Path(d) / "part.scad", Path(d) / "part.stl"
            src.write_text(source, encoding="utf-8")
            try:
                r = subprocess.run([self.binary, "-o", str(out), str(src)], cwd=d, capture_output=True, text=True,
                                   timeout=self.TIMEOUT_S)
            except FileNotFoundError as exc:
                raise CadError("OpenSCAD ist nicht installiert") from exc
            except subprocess.TimeoutExpired as exc:
                raise CadError(f"Berechnung dauerte über {self.TIMEOUT_S} s -- weniger Details ($fn) oder einfachere Form") from exc
            log = (r.stderr or "") + (r.stdout or "")
            if r.returncode != 0 or not out.exists() or out.stat().st_size == 0:
                errors = [l for l in log.splitlines() if "ERROR" in l or "WARNING" in l] or log.splitlines()[-6:]
                raise CadError("OpenSCAD: " + " | ".join(errors)[:1200])
            return out.read_bytes()


ENGINES = {"openscad": OpenScadEngine}


def get_engine() -> CadEngine:
    name = (os.getenv("CAD_ENGINE") or "openscad").lower()
    if name not in ENGINES:
        raise CadError(f"CAD_ENGINE {name!r} unbekannt; es gibt {list(ENGINES)}")
    return ENGINES[name]()
