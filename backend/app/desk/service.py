"""AURON at Brano's laptop (Brano, 2026-10-23): open and close programs, files and folders, windows
bigger, smaller, full screen, onto monitor 1/2/3, scroll. Typing, keys and clicks are not part of it
(yet) -- the narrow version Brano chose.

AURON runs in Docker and cannot touch the desktop. The desk runner (tools/desk_runner.py) runs on the
laptop, picks the commands up here and carries them out -- only the actions in ACTIONS, no command line.

Sensitive steps wait for Brano's click. The runner says when one is: a program file or script that is
not an installed app (an .exe, .bat, .ps1 ... from a folder). And the assistant's watchdog makes any
step sensitive that comes after AURON read a mail or a web page in the same answer (assistant/tools.py).
Such a command stops at "needs_approval", every open dashboard asks him, and only his click
(/approve) lets it run. AURON cannot approve -- there is no tool for it.
"""
from __future__ import annotations

import itertools
import threading
import time

ACTIONS = {
    "windows": "list the open windows",
    "monitors": "list the monitors",
    "open": "open a program, file or folder by name or path",
    "close": "close a window, like its ✕ (the program may ask to save)",
    "minimize": "", "maximize": "", "restore": "", "focus": "bring to the front",
    "fullscreen": "F11 in that window",
    "move_monitor": "move a window onto monitor n (Windows' numbering) and maximize it there",
    "scroll": "scroll the window up or down",
}
KEEP_S = 600
_seq = itertools.count(1)
_lock = threading.Lock()
_cmds: dict[int, dict] = {}
_runner_seen = 0.0


class DeskError(ValueError):
    pass


def create(action: str, args: dict | None = None, hold: str = "") -> dict:
    """hold: a reason this step must wait for Brano's click before the runner even sees it (the watchdog)."""
    if action not in ACTIONS:
        raise DeskError(f"unknown action {action!r}; there are {list(ACTIONS)}")
    with _lock:
        now = time.time()
        for k in [k for k, c in _cmds.items() if now - c["created"] > KEEP_S]:
            del _cmds[k]
        c = {"id": next(_seq), "action": action, "args": args or {}, "status": "needs_approval" if hold else "pending",
             "created": now, "approved": False, "result": None, "reason": hold[:300]}
        _cmds[c["id"]] = c
        return dict(c)


def get(cmd_id: int) -> dict:
    c = _cmds.get(cmd_id)
    if c is None:
        raise DeskError(f"no command {cmd_id}")
    return dict(c)


def wait(cmd_id: int, timeout: float = 20, poll: float = 0.15) -> dict:
    """Until the runner answered, asked for approval, or the time is up."""
    end = time.time() + timeout
    while time.time() < end:
        c = get(cmd_id)
        if c["status"] in ("done", "failed", "needs_approval", "rejected"):
            return c
        time.sleep(poll)
    return get(cmd_id)


def runner_alive() -> bool:
    return time.time() - _runner_seen < 10


def claim() -> list[dict]:
    """The runner takes what is pending (approved ones included)."""
    global _runner_seen
    _runner_seen = time.time()
    with _lock:
        out = [c for c in _cmds.values() if c["status"] == "pending"]
        for c in out:
            c["status"] = "claimed"
        return [dict(c) for c in out]


def report(cmd_id: int, result: dict | None = None, error: str | None = None, approve: str | None = None) -> dict:
    with _lock:
        c = _cmds.get(cmd_id)
        if c is None:
            raise DeskError(f"no command {cmd_id}")
        if approve and not c["approved"]:
            c.update(status="needs_approval", reason=approve[:300])
        elif error:
            c.update(status="failed", result={"error": error[:2000]})
        else:
            c.update(status="done", result=result or {})
        return dict(c)


def approve(cmd_id: int, ok: bool) -> dict:
    """Brano's click on the dashboard -- the only way a sensitive step runs."""
    with _lock:
        c = _cmds.get(cmd_id)
        if c is None or c["status"] != "needs_approval":
            raise DeskError(f"command {cmd_id} waits for no approval")
        c.update(status="pending", approved=True) if ok else c.update(status="rejected")
        return dict(c)


def waiting() -> list[dict]:
    return [dict(c) for c in _cmds.values() if c["status"] == "needs_approval"]
