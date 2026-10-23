"""AURON's hands at the laptop -- runs on Windows, outside Docker, where the windows are.

    python tools/desk_runner.py          (start_desk_runner.bat keeps it running; it starts with Windows)

Twice a second it asks AURON (/api/v1/desk/runner/claim) for commands and carries out only these:
windows, monitors, open, close, minimize, maximize, restore, focus, fullscreen, move_monitor, scroll.
No command line, no typing, no clicks (the narrow version Brano chose, 2026-10-23).

'open' starts an installed app (Start menu, the same list Windows search uses), opens a folder or a file
with its normal program. A program file or script that is not an installed app (.exe, .bat, .ps1 ... in
some folder) is sent back as "needs approval" -- it runs only after Brano's click on the dashboard.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8080/api/v1/desk"
EVERY_S = 0.5
RISKY = {".exe", ".com", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".msi",
         ".msp", ".scr", ".pif", ".reg", ".hta", ".cpl", ".jar", ".py", ".pyw"}
HOME = Path.home()
PLACES = {"desktop": [HOME / "OneDrive" / "Plocha", HOME / "Desktop", HOME / "OneDrive" / "Desktop"],
          "dokumente": [HOME / "OneDrive" / "Dokumenty", HOME / "Documents", HOME / "OneDrive" / "Documents"],
          "downloads": [HOME / "Downloads"], "bilder": [HOME / "Pictures", HOME / "OneDrive" / "Obrázky"],
          "musik": [HOME / "Music"], "videos": [HOME / "Videos"]}
PLACES["dokumenty"], PLACES["documents"], PLACES["plocha"] = PLACES["dokumente"], PLACES["dokumente"], PLACES["desktop"]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # real pixels on every monitor
except Exception:  # noqa: BLE001
    user32.SetProcessDPIAware()

SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
WM_CLOSE = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
VK_F11 = 0x7A


# ---------------------------------------------------------------- windows
def _title(h) -> str:
    n = user32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, b, n + 1)
    return b.value


def _exe(h) -> str:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    hp = kernel32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not hp:
        return ""
    try:
        b, n = ctypes.create_unicode_buffer(520), wt.DWORD(520)
        return Path(b.value).stem if kernel32.QueryFullProcessImageNameW(hp, 0, b, ctypes.byref(n)) else ""
    finally:
        kernel32.CloseHandle(hp)


def windows() -> list[dict]:
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def each(h, _):
        if user32.IsWindowVisible(h) and not user32.GetWindow(h, 4) and _title(h).strip():   # GW_OWNER: no tool windows
            out.append({"hwnd": h, "title": _title(h), "program": _exe(h), "minimized": bool(user32.IsIconic(h))})
        return True
    user32.EnumWindows(each, 0)
    return [w for w in out if w["title"] not in ("Program Manager",) and w["program"].lower() not in ("textinputhost", "applicationframehost")]


def find(target: str | None) -> dict:
    ws = windows()
    if not target:
        fg = user32.GetForegroundWindow()
        hit = [w for w in ws if w["hwnd"] == fg]
        if hit:
            return hit[0]
        raise RuntimeError("kein Fenster im Vordergrund")
    t = target.lower().strip()
    hit = ([w for w in ws if w["title"].lower() == t or w["program"].lower() == t]
           or [w for w in ws if t in w["title"].lower() or t in w["program"].lower()])
    if not hit:
        raise RuntimeError(f"kein offenes Fenster passt zu {target!r}")
    return hit[0]


def focus(h) -> None:
    if user32.IsIconic(h):
        user32.ShowWindow(h, SW_RESTORE)
    # Windows only lets the foreground app hand on the focus: a tap on Alt first unlocks it
    user32.keybd_event(0x12, 0, 0, 0); user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(h)


# ---------------------------------------------------------------- monitors
def monitors() -> list[dict]:
    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD),
                    ("szDevice", wt.WCHAR * 32)]
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)
    def each(hm, _dc, _r, _):
        mi = MONITORINFOEX(); mi.cbSize = ctypes.sizeof(MONITORINFOEX)
        user32.GetMonitorInfoW(hm, ctypes.byref(mi))
        dev = mi.szDevice                                   # \\.\DISPLAY2 -> Windows calls it monitor 2
        num = int("".join(c for c in dev if c.isdigit()) or 0)
        w = mi.rcWork
        out.append({"number": num, "primary": bool(mi.dwFlags & 1), "width": mi.rcMonitor.right - mi.rcMonitor.left,
                    "height": mi.rcMonitor.bottom - mi.rcMonitor.top, "work": [w.left, w.top, w.right, w.bottom]})
        return True
    user32.EnumDisplayMonitors(0, 0, each, 0)
    return sorted(out, key=lambda m: m["number"])


def move_monitor(h, n: int) -> dict:
    ms = monitors()
    m = next((m for m in ms if m["number"] == n), None)
    if m is None:
        raise RuntimeError(f"keinen Monitor {n}; es gibt {[x['number'] for x in ms]}")
    l, t, r, b = m["work"]
    user32.ShowWindow(h, SW_RESTORE)                        # a maximized window does not move
    user32.SetWindowPos(h, 0, l + 40, t + 40, (r - l) - 80, (b - t) - 80, 0x0004 | 0x0040)   # NOZORDER | SHOWWINDOW
    user32.ShowWindow(h, SW_MAXIMIZE)
    return {"monitor": n}


# ---------------------------------------------------------------- open
_apps: list[dict] | None = None


def start_apps() -> list[dict]:
    """Every installed app the way Windows search knows it (Start menu, Store apps)."""
    global _apps
    if _apps is None:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        data = json.loads(r.stdout or "[]")
        _apps = data if isinstance(data, list) else [data]
    return _apps


def open_target(target: str, approved: bool) -> dict:
    t = target.strip().strip('"')
    key = t.lower()
    for k, cands in PLACES.items():
        if key == k:
            p = next((c for c in cands if c.exists()), None)
            if p:
                os.startfile(p)
                return {"opened": str(p)}
    p = Path(os.path.expandvars(t))
    if not p.is_absolute():
        p = next((Path(c) / t for cs in PLACES.values() for c in cs if (Path(c) / t).exists()), p)
    if p.exists():
        if p.suffix.lower() in RISKY and not approved:
            return {"_approve": f"Programmdatei öffnen: {p}"}
        os.startfile(p)
        return {"opened": str(p)}
    apps = start_apps()
    hit = ([a for a in apps if a["Name"].lower() == key] or [a for a in apps if a["Name"].lower().startswith(key)]
           or [a for a in apps if key in a["Name"].lower()])
    if hit:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{hit[0]['AppID']}"])
        return {"opened": hit[0]["Name"]}
    # a file somewhere in his own folders, by (part of) its name -- the first match, not deeper than 4 levels
    for root in [c for cs in PLACES.values() for c in cs if c.exists()]:
        for dirpath, dirs, files in os.walk(root):
            if dirpath[len(str(root)):].count(os.sep) >= 4:
                dirs[:] = []
            for f in files + dirs:
                if key in f.lower():
                    q = Path(dirpath) / f
                    if q.suffix.lower() in RISKY and not approved:
                        return {"_approve": f"Programmdatei öffnen: {q}"}
                    os.startfile(q)
                    return {"opened": str(q)}
    raise RuntimeError(f"nichts gefunden zu {target!r} -- weder installiertes Programm noch Datei/Ordner")


# ---------------------------------------------------------------- one command
def do(cmd: dict) -> dict:
    a, args = cmd["action"], cmd.get("args") or {}
    if a == "windows":
        return {"windows": [{k: w[k] for k in ("title", "program", "minimized")} for w in windows()]}
    if a == "monitors":
        return {"monitors": [{k: m[k] for k in ("number", "primary", "width", "height")} for m in monitors()]}
    if a == "open":
        return open_target(args.get("target") or "", cmd.get("approved", False))
    w = find(args.get("target"))
    h = w["hwnd"]
    if a == "close":
        user32.PostMessageW(h, WM_CLOSE, 0, 0)
    elif a == "minimize":
        user32.ShowWindow(h, SW_MINIMIZE)
    elif a == "maximize":
        user32.ShowWindow(h, SW_MAXIMIZE)
    elif a == "restore":
        user32.ShowWindow(h, SW_RESTORE)
    elif a == "focus":
        focus(h)
    elif a == "fullscreen":
        focus(h); time.sleep(0.15)
        user32.keybd_event(VK_F11, 0, 0, 0); user32.keybd_event(VK_F11, 0, 2, 0)
    elif a == "move_monitor":
        return {"window": w["title"], **move_monitor(h, int(args.get("monitor") or 1))}
    elif a == "scroll":
        focus(h); time.sleep(0.1)
        r = wt.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
        user32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        steps = int(args.get("amount") or 5) * (1 if args.get("direction") == "up" else -1)
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, ctypes.c_uint32(120 * steps).value, 0)
    else:
        raise RuntimeError(f"unbekannte Aktion {a}")
    return {"window": w["title"]}


def call(path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, json.dumps(body or {}).encode(), {"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=10).read() or b"null")


def main() -> None:
    print("desk runner: waiting for AURON's commands", flush=True)
    while True:
        try:
            for cmd in call("/runner/claim") or []:
                try:
                    res = do(cmd)
                    if "_approve" in res:
                        call(f"/runner/{cmd['id']}", {"approve": res["_approve"]})
                    else:
                        call(f"/runner/{cmd['id']}", {"result": res})
                except Exception as exc:  # noqa: BLE001 -- AURON gets the reason and says it
                    call(f"/runner/{cmd['id']}", {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 -- AURON down or restarting: try again
            print(f"desk runner: {exc}", file=sys.stderr, flush=True)
            time.sleep(3)
        time.sleep(EVERY_S)


if __name__ == "__main__":
    main()
