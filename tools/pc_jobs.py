"""PC jobs: AURON's hands on the laptop -- narrow on purpose (Brano, 2026-10-21).

Claude Code only LOOKS (read-only file tools, no shell) inside three folders -- Desktop, Documents,
Downloads -- and writes a plan: a short German summary and a fixed list of steps. This module, not
the AI, checks every step and, after Brano's "Freigeben", carries it out:

    mkdir  {"op": "mkdir", "path": ...}
    move   {"op": "move",  "from": ..., "to": ...}     (to an existing folder, or a full new path)
    copy   {"op": "copy",  "from": ..., "to": ...}
    write  {"op": "write", "path": ..., "text": ...}   (a new text file; never overwrites)
    trash  {"op": "trash", "path": ...}                (into Dokumente/AURON-Papierkorb -- nothing is deleted)

Every path has to lie inside the three folders; nothing that looks like a key, token, password or
.env is touched; nothing is overwritten. A plan with one bad step is refused as a whole.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

HOME = Path.home()
ROOTS = {
    "Desktop": HOME / "OneDrive" / "Plocha",
    "Dokumente": HOME / "OneDrive" / "Dokumenty",
    "Downloads": HOME / "Downloads",
}
TRASH = ROOTS["Dokumente"] / "AURON-Papierkorb"
LOG = ROOTS["Dokumente"] / "AURON-Protokoll.txt"
SECRET = re.compile(r"(^|[\\/])(\.env|secrets?)([\\/.]|$)|token|secret|passwor|kennwort|\.pem$|\.key$|\.kdbx$|"
                    r"gmail_client|telegram\.session|id_rsa|\.ssh", re.I)
OPS = {"mkdir": ("path",), "move": ("from", "to"), "copy": ("from", "to"), "write": ("path", "text"), "trash": ("path",)}


class PlanError(ValueError):
    pass


def inside(p: str) -> Path:
    """The real path, which must lie inside one of the three folders and must not hold secrets."""
    q = Path(p).expanduser()
    q = (q if q.is_absolute() else ROOTS["Desktop"] / q).resolve()
    if not any(q == r.resolve() or r.resolve() in q.parents for r in ROOTS.values()):
        raise PlanError(f"{p}: outside Desktop, Dokumente and Downloads")
    if SECRET.search(str(q)):
        raise PlanError(f"{p}: looks like a key, token or password -- off limits")
    return q


def parse(text: str) -> tuple[str, list[dict]]:
    """Claude Code's answer -> (summary, steps). The steps are the last ```json block."""
    blocks = re.findall(r"```json\s*(.*?)```", text, re.S)
    if not blocks:
        raise PlanError("no ```json step list in the plan")
    try:
        steps = json.loads(blocks[-1])
    except ValueError as exc:
        raise PlanError(f"step list is not valid JSON: {exc}") from exc
    summary = text[:text.rfind("```json")].strip()
    return summary, steps


def check(steps: list[dict]) -> list[str]:
    """Every step valid, or PlanError. Returns the steps as Brano reads them."""
    if not isinstance(steps, list) or not steps:
        raise PlanError("the plan has no steps")
    if len(steps) > 500:
        raise PlanError("more than 500 steps -- split the job")
    out = []
    for i, s in enumerate(steps, 1):
        op = s.get("op") if isinstance(s, dict) else None
        if op not in OPS or any(k not in s for k in OPS[op]):
            raise PlanError(f"step {i}: unknown or incomplete {s!r}")
        if op == "mkdir":
            out.append(f"{i}. Ordner anlegen: {inside(s['path'])}")
        elif op in ("move", "copy"):
            out.append(f"{i}. {'Verschieben' if op == 'move' else 'Kopieren'}: {inside(s['from'])} → {inside(s['to'])}")
        elif op == "write":
            if len(s["text"]) > 200_000:
                raise PlanError(f"step {i}: text too long")
            out.append(f"{i}. Textdatei schreiben: {inside(s['path'])}")
        else:
            out.append(f"{i}. In den Papierkorb: {inside(s['path'])}")
    return out


def _target(src: Path, to: Path) -> Path:
    t = to / src.name if to.is_dir() else to
    if t.exists():
        raise PlanError(f"{t} exists already -- not overwritten")
    return t


def run(steps: list[dict], job: str) -> str:
    """Carry out a checked plan. A step that fails stops the rest; done steps stay done."""
    check(steps)
    done = []
    for i, s in enumerate(steps, 1):
        try:
            op = s["op"]
            if op == "mkdir":
                inside(s["path"]).mkdir(parents=True, exist_ok=True)
                done.append(f"{i}. Ordner da: {s['path']}")
            elif op in ("move", "copy"):
                src, to = inside(s["from"]), inside(s["to"])
                if not src.exists():
                    done.append(f"{i}. übersprungen, gibt es nicht mehr: {src}")
                    continue
                t = _target(src, to)
                t.parent.mkdir(parents=True, exist_ok=True)
                if op == "move":
                    shutil.move(str(src), str(t))
                elif src.is_dir():
                    shutil.copytree(src, t)
                else:
                    shutil.copy2(src, t)
                done.append(f"{i}. {'verschoben' if op == 'move' else 'kopiert'}: {src} → {t}")
            elif op == "write":
                p = inside(s["path"])
                if p.exists():
                    raise PlanError(f"{p} exists already -- not overwritten")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(s["text"], encoding="utf-8")
                done.append(f"{i}. geschrieben: {p}")
            else:
                src = inside(s["path"])
                if not src.exists():
                    done.append(f"{i}. übersprungen, gibt es nicht mehr: {src}")
                    continue
                TRASH.mkdir(parents=True, exist_ok=True)
                t = TRASH / f"{time.strftime('%Y%m%d-%H%M%S')}_{src.name}"
                shutil.move(str(src), str(t))
                done.append(f"{i}. in den Papierkorb: {src} → {t}")
        except Exception as exc:  # noqa: BLE001 -- the log says where it stopped
            done.append(f"{i}. ABGEBROCHEN: {type(exc).__name__}: {exc}")
            break
    report = "\n".join(done)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M')} -- {job}\n{report}\n")
    return report
