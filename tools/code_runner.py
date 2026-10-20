"""AURON's code runner -- runs on the laptop, outside Docker, where Claude Code, git and docker are.

    python tools/code_runner.py          (start_code_runner.bat keeps it running)

Every few seconds it asks AURON (/api/v1/code/runner/claim) whether there is work:
  running     a new wish: a worktree on its own branch, Claude Code makes the change there,
              the changed files are checked, the result goes back for Brano to review
  applying    Brano pressed "Freigeben": merge into the checked-out branch, rebuild what the
              change touches (frontend / api), restart the AURON window
  discarding  Brano pressed "Verwerfen": worktree and branch go
  reverting   Brano pressed "Rückgängig": the merge is reverted and rebuilt
Nothing reaches the real code without Brano's click; AURON itself can only file a wish. The
copiers are never restarted from here -- that stays Brano's call, they may hold open trades.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT.parent / "auron-code-tasks"
API = "http://127.0.0.1:8080/api/v1/code"
EVERY_S = 5
CLAUDE_TIMEOUT_S = 25 * 60

PROMPT = """You are working on AURON, Brano's dashboard (FastAPI backend in backend/, dashboard in frontend/,
signal copier in signal_copier/). This folder is a separate copy on its own branch.

Brano asked AURON for this change:
\"\"\"{text}\"\"\"

Make exactly this change -- small, in the style and comment density of the code around it. Read CLAUDE.md
first. Do not commit, do not touch .env files, secrets, the database or anything the wish does not need.
Keep existing tests working; if you change behaviour that a test covers, adjust that test.
When you are done, answer in German, 2-4 short sentences: what you changed and where (file names), and
anything Brano should check after it goes live."""


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, json.dumps(body or {}).encode(), {"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 600, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          input=stdin)


def git(*args: str, cwd: Path = ROOT) -> str:
    r = run(["git", *args], cwd)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()[:500]}")
    return r.stdout.strip()


def checks(files: list[str], wt: Path) -> str:
    """What the change touches has to load: Python compiles, JavaScript parses, and the tests named
    after a changed backend module pass."""
    out = []
    py = [f for f in files if f.endswith(".py")]
    js = [f for f in files if f.endswith(".js")]
    for f in py:
        r = run([sys.executable, "-m", "py_compile", f], wt)
        out.append(f"{'ok' if r.returncode == 0 else 'FEHLER'} python {f}" + ("" if r.returncode == 0 else f": {r.stderr.strip()[:300]}"))
    for f in js:
        r = run(["node", "-e", f"new Function(require('fs').readFileSync({json.dumps(f)}, 'utf8'))"], wt)
        out.append(f"{'ok' if r.returncode == 0 else 'FEHLER'} js {f}" + ("" if r.returncode == 0 else f": {r.stderr.strip()[:300]}"))
    tests = sorted({f"tests/test_{Path(f).parts[2]}.py" for f in py if f.startswith("backend/app/") and len(Path(f).parts) > 3}
                   | {f.removeprefix("backend/") for f in py if f.startswith("backend/tests/")})
    tests = [t for t in tests if (wt / "backend" / t).exists()]
    if tests:
        r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:warnings", *tests], wt / "backend", timeout=900)
        out.append(f"pytest {' '.join(tests)}: {(r.stdout.strip().splitlines() or ['?'])[-1]}")
    if any(f.startswith(("signal_copier/", "tests/")) for f in py):
        r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:warnings", "tests"], wt, timeout=900)
        out.append(f"pytest tests: {(r.stdout.strip().splitlines() or ['?'])[-1]}")
    return "\n".join(out) or "keine prüfbaren Dateien"


def do_task(t: dict) -> None:
    tid, branch, wt = t["id"], f"auron/task-{t['id']}", WORK / t["id"]
    WORK.mkdir(exist_ok=True)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
        run(["git", "worktree", "prune"])
    git("worktree", "add", "-b", branch, str(wt), "HEAD")
    claude = shutil.which("claude") or "claude"
    # the wish goes in on stdin: on Windows `claude` is a .cmd, and a batch file cuts an argument at
    # its first line break -- Claude Code then got only the first line and asked what to do
    r = run([claude, "-p", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Edit,Write,Glob,Grep",
             "--max-turns", "60"], wt, timeout=CLAUDE_TIMEOUT_S, stdin=PROMPT.format(text=t["text"]))
    answer = (r.stdout or "").strip()
    if r.returncode or not answer:
        err = (r.stderr or r.stdout or "").strip()
        if "authenticate" in err.lower() or "login" in err.lower():
            err = "Claude Code ist nicht angemeldet: im Terminal `claude` starten und /login eingeben. " + err[:200]
        cleanup(wt, branch)
        call(f"/runner/report/{tid}", {"status": "failed", "error": err[:2000] or f"exit {r.returncode}"})
        return
    git("add", "-A", cwd=wt)
    files = [f for f in git("diff", "--cached", "--name-only", cwd=wt).splitlines() if f]
    if not files:
        cleanup(wt, branch)
        call(f"/runner/report/{tid}", {"status": "failed", "summary": answer, "error": "Claude Code hat nichts geändert."})
        return
    stat = git("diff", "--cached", "--stat", cwd=wt)
    diff = git("diff", "--cached", cwd=wt)
    result = checks(files, wt)
    git("commit", "-q", "-m", f"AURON-Auftrag {tid}: {t['text'][:70]}\n\n{t['text']}\n\nCo-Authored-By: Claude <noreply@anthropic.com>", cwd=wt)
    call(f"/runner/report/{tid}", {"status": "ready", "summary": answer, "diff": stat + "\n\n" + diff[:15000],
                                   "tests": result, "branch": branch})


def cleanup(wt: Path, branch: str) -> None:
    """A failed or discarded wish leaves nothing behind: no worktree, no branch."""
    run(["git", "worktree", "remove", "--force", str(wt)])
    run(["git", "worktree", "prune"])
    run(["git", "branch", "-D", branch])


def services(files: list[str]) -> list[str]:
    return sorted({"frontend" for f in files if f.startswith("frontend/")} | {"api" for f in files if f.startswith("backend/")})


def rebuild(files: list[str]) -> str:
    notes = []
    for svc in services(files):
        r = run(["docker", "compose", "up", "-d", "--build", "--no-deps", svc], timeout=1200)
        notes.append(f"{svc} neu gebaut" if r.returncode == 0 else f"{svc} FEHLER: {r.stderr.strip()[-300:]}")
    if any(f.startswith("signal_copier/") for f in files):
        notes.append("Kopierer-Code geändert: wirkt erst nach einem Neustart der Kopierer -- den entscheidest du (offene Trades?).")
    if any(f.startswith("frontend/") for f in files):
        restart_window()
        notes.append("AURON-Fenster neu gestartet")
    return "; ".join(notes)


def restart_window() -> None:
    ps = ("Add-Type -Name W -Namespace U -MemberDefinition '[DllImport(\"user32.dll\")] public static extern System.IntPtr FindWindow(string c,string t); "
          "[DllImport(\"user32.dll\")] public static extern bool PostMessage(System.IntPtr h,uint m,System.IntPtr w,System.IntPtr l);'; "
          "$h=[U.W]::FindWindow($null,'AURON'); if($h -ne [System.IntPtr]::Zero){[U.W]::PostMessage($h,0x10,[System.IntPtr]::Zero,[System.IntPtr]::Zero)|Out-Null}; "
          "Start-Sleep 2; Start-Process msedge.exe '--app=http://127.0.0.1:8080 --start-fullscreen --autoplay-policy=no-user-gesture-required'")
    run(["powershell.exe", "-NoProfile", "-Command", ps], timeout=60)


def apply(t: dict) -> None:
    tid, branch, wt = t["id"], t.get("branch") or f"auron/task-{t['id']}", WORK / t["id"]
    files = [f for f in git("diff", "--name-only", f"HEAD...{branch}").splitlines() if f]
    r = run(["git", "merge", "--no-ff", "-m", f"AURON-Auftrag {tid} freigegeben: {t['text'][:70]}", branch])
    if r.returncode:
        run(["git", "merge", "--abort"])
        call(f"/runner/report/{tid}", {"status": "apply_failed",
                                       "error": "Übernehmen ging nicht (Konflikt mit offenen Änderungen?): " + (r.stderr or r.stdout).strip()[:800]})
        return
    commit = git("rev-parse", "HEAD")
    notes = rebuild(files)
    cleanup(wt, branch)
    call(f"/runner/report/{tid}", {"status": "applied", "commit": commit, "tests": (t.get("tests") or "") + "\n\nLive: " + notes})


def discard(t: dict) -> None:
    cleanup(WORK / t["id"], t.get("branch") or f"auron/task-{t['id']}")
    call(f"/runner/report/{t['id']}", {"status": "discarded"})


def revert(t: dict) -> None:
    commit = t.get("commit", "")
    files = [f for f in git("diff", "--name-only", f"{commit}^1", commit).splitlines() if f] if commit else []
    r = run(["git", "revert", "-m", "1", "--no-edit", commit]) if commit else None
    if r is None or r.returncode:
        run(["git", "revert", "--abort"])
        call(f"/runner/report/{t['id']}", {"status": "revert_failed", "error": ((r.stderr or r.stdout).strip() if r else "kein Commit")[:800]})
        return
    notes = rebuild(files)
    call(f"/runner/report/{t['id']}", {"status": "reverted", "tests": "Zurückgenommen: " + notes})


STEPS = {"running": do_task, "applying": apply, "discarding": discard, "reverting": revert}


def main() -> None:
    print("AURON code runner: waiting for work (Ctrl+C stops)")
    while True:
        try:
            t = call("/runner/claim").get("task")
        except Exception as e:  # noqa: BLE001 -- AURON not up yet
            print("AURON not reachable:", e)
            time.sleep(30)
            continue
        if not t:
            time.sleep(EVERY_S)
            continue
        print(f"{t['status']}: {t['id']} {t['text'][:60]}")
        try:
            STEPS[t["status"]](t)
        except Exception as e:  # noqa: BLE001 -- the task says what went wrong, the runner goes on
            fail = {"running": "failed", "applying": "apply_failed", "reverting": "revert_failed", "discarding": "discarded"}[t["status"]]
            try:
                call(f"/runner/report/{t['id']}", {"status": fail, "error": f"{type(e).__name__}: {e}"[:2000]})
            except Exception:  # noqa: BLE001
                pass
            print("failed:", e)


if __name__ == "__main__":
    main()
