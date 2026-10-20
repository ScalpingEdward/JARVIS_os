"""Code wishes, from Brano's word to AURON, done by Claude Code -- live only with his click.

AURON (assistant tool code_request) can only file a task. The code runner on the laptop
(tools/code_runner.py, outside Docker -- Claude Code, git and docker live there) claims it, lets
Claude Code do it on a branch in a separate worktree, runs the tests and reports back. Nothing
reaches the real code until Brano presses "Freigeben" in the dashboard; then the runner merges,
rebuilds and restarts the AURON window. "Rückgängig" reverts an applied change the same way.

    queued -> running -> ready | failed
    ready -> approved (Brano) -> applying -> applied | apply_failed
    ready -> rejected (Brano) -> discarding -> discarded
    applied -> revert_requested (Brano) -> reverting -> reverted | revert_failed
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone

from app.db import SessionLocal
from app.db_models import AppSettingRow

KEY = "code.tasks"
KEEP = 50
_lock = threading.Lock()

# what the runner picks up, and what it becomes while it works on it
CLAIM = {"queued": "running", "approved": "applying", "rejected": "discarding", "revert_requested": "reverting"}
# Brano's buttons: from -> to
# (an approve that could not be merged -- e.g. the checkout had changes of its own -- may be tried again)
DECIDE = {"approve": (("ready", "apply_failed"), "approved"), "reject": (("ready", "apply_failed"), "rejected"),
          "revert": (("applied",), "revert_requested")}
# what the runner may report after each step
FINISH = {"running": {"ready", "failed"}, "applying": {"applied", "apply_failed"},
          "discarding": {"discarded"}, "reverting": {"reverted", "revert_failed"}}


class CodeTaskError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    with SessionLocal() as s:
        row = s.get(AppSettingRow, KEY)
    try:
        return json.loads(row.value) if row else []
    except ValueError:
        return []


def _save(tasks: list[dict]) -> None:
    with SessionLocal() as s:
        s.merge(AppSettingRow(key=KEY, value=json.dumps(tasks[-KEEP:], ensure_ascii=False), updated_at=datetime.now(timezone.utc)))
        s.commit()


def tasks() -> list[dict]:
    return list(reversed(_load()))   # newest first


def create(text: str, by: str = "auron") -> dict:
    text = (text or "").strip()
    if len(text) < 8:
        raise CodeTaskError("describe the change in a sentence")
    t = {"id": uuid.uuid4().hex[:10], "text": text[:4000], "by": by, "status": "queued",
         "created_at": _now(), "updated_at": _now(), "summary": "", "diff": "", "tests": "", "branch": "", "error": ""}
    with _lock:
        _save(_load() + [t])
    return t


def _update(task_id: str, fn) -> dict:
    with _lock:
        ts = _load()
        t = next((x for x in ts if x["id"] == task_id), None)
        if t is None:
            raise CodeTaskError(f"no task {task_id}")
        fn(t)
        t["updated_at"] = _now()
        _save(ts)
        return t


def decide(task_id: str, action: str) -> dict:
    """Brano's buttons in the dashboard. AURON's tool never calls this."""
    if action not in DECIDE:
        raise CodeTaskError(f"unknown decision {action}")
    want, to = DECIDE[action]

    def go(t):
        if t["status"] not in want:
            raise CodeTaskError(f"task is {t['status']}, not {' or '.join(want)}")
        t["status"] = to
        t["error"] = ""          # a second try starts clean; the old failure would read as the new one
    return _update(task_id, go)


def claim() -> dict | None:
    """The runner: the oldest task with something to do, now marked as in work."""
    with _lock:
        ts = _load()
        t = next((x for x in ts if x["status"] in CLAIM), None)
        if t is None:
            return None
        t["status"], t["updated_at"] = CLAIM[t["status"]], _now()
        _save(ts)
        return t


def report(task_id: str, status: str, **fields) -> dict:
    def go(t):
        if status not in FINISH.get(t["status"], set()):
            raise CodeTaskError(f"cannot go from {t['status']} to {status}")
        t["status"] = status
        for k in ("summary", "diff", "tests", "branch", "error", "commit"):
            if k in fields and fields[k] is not None:
                t[k] = str(fields[k])[:20000]
    return _update(task_id, go)
