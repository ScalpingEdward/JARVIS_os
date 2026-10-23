"""AURON's 3D parts: what he designed, kept as source + STL in /data/cad/<id>/, shown on the dashboard.

Each part keeps its source, so it can be changed later ("2 mm dicker") and rebuilt -- by this engine or a
better one. The STL is what a 3D printer's slicer takes.
"""
from __future__ import annotations

import json
import os
import re
import struct
import time
import uuid
from pathlib import Path

from .engine import CadError, get_engine


def root() -> Path:
    return Path(os.getenv("AURON_DATA_DIR", "/data")) / "cad"


def _dir(part_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{8}", part_id or ""):
        raise CadError(f"kein Teil {part_id!r}")
    return root() / part_id


def bbox(stl: bytes) -> list[float]:
    """Size in mm (x, y, z) from an ASCII or binary STL."""
    pts: list[tuple[float, float, float]] = []
    if stl[:5].lower() == b"solid" and b"facet" in stl[:400]:
        for m in re.finditer(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", stl):
            pts.append(tuple(float(v) for v in m.groups()))
    else:
        n = struct.unpack_from("<I", stl, 80)[0]
        for i in range(n):
            off = 84 + i * 50 + 12
            for k in range(3):
                pts.append(struct.unpack_from("<3f", stl, off + k * 12))
    if not pts:
        raise CadError("das Teil ist leer -- keine Fläche erzeugt")
    return [round(max(p[i] for p in pts) - min(p[i] for p in pts), 2) for i in range(3)]


def _meta(d: Path) -> dict:
    return json.loads((d / "meta.json").read_text(encoding="utf-8"))


def parts() -> list[dict]:
    if not root().exists():
        return []
    out = [_meta(d) for d in root().iterdir() if (d / "meta.json").exists()]
    return sorted(out, key=lambda m: m["updated"], reverse=True)


def get(part_id: str) -> dict:
    d = _dir(part_id)
    if not (d / "meta.json").exists():
        raise CadError(f"kein Teil {part_id!r}")
    return {**_meta(d), "source": (d / "part.src").read_text(encoding="utf-8")}


def stl(part_id: str) -> bytes:
    return (_dir(part_id) / "part.stl").read_bytes()


def find(name: str) -> dict:
    n = (name or "").strip().lower()
    hit = [p for p in parts() if p["id"] == n or p["name"].lower() == n] or [p for p in parts() if n and n in p["name"].lower()]
    if not hit:
        raise CadError(f"kein Teil {name!r}")
    return hit[0]


def save(name: str, source: str, description: str = "", part_id: str | None = None) -> dict:
    """Build the source; only a part that built is stored. part_id: a new version of that part."""
    name = " ".join((name or "").split())[:80]
    if not name:
        raise CadError("das Teil braucht einen Namen")
    engine = get_engine()
    data = engine.build(source)
    size = bbox(data)
    d = _dir(part_id) if part_id else root() / uuid.uuid4().hex[:8]
    d.mkdir(parents=True, exist_ok=True)
    old = _meta(d) if (d / "meta.json").exists() else {}
    (d / "part.src").write_text(source, encoding="utf-8")
    (d / "part.stl").write_bytes(data)
    meta = {"id": d.name, "name": name, "description": description[:500], "engine": engine.name,
            "size_mm": size, "version": old.get("version", 0) + 1, "created": old.get("created", time.time()),
            "updated": time.time(), "stl_bytes": len(data)}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def delete(part_id: str) -> dict:
    d = _dir(part_id)
    meta = _meta(d)
    for f in d.iterdir():
        f.unlink()
    d.rmdir()
    return meta
