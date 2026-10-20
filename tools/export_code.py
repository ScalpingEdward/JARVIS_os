"""AURON's code as one ZIP for ChatGPT or a reviewer -- without anything personal.

    python tools/export_code.py   ->  export/auron-code.zip

Takes only what git tracks (so .env, the database, logs and media never come along), leaves out
documents about Brano and his business, the n8n backups and every picture, and replaces what is left
that points at a person or an account: name, e-mail, town, GitHub user, Drive folder ids, n8n
credential ids, broker logins, the Telegram groups he follows. Prints what it replaced and checks
the result once more -- the ZIP is not written if anything is still found.
"""
import io
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "export" / "auron-code.zip"

SKIP_DIRS = ("docs/", "n8n/backups/", "backend/data/", "backend/.phoenix/", "bridge/", ".github/")
SKIP_FILES = {"CLAUDE.md", "AGENTS.md", "JARVIS_MASTER_PLAN.md", "JARVIS_MASTER_PLAN.pdf", "JARVIS_MASTER_PLAN.docx",
              ".abacus.donotdelete", "dead_auron_modules_report.txt", "n8n/README_HEUTE_ABEND.md"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif", ".pdf", ".docx", ".db", ".sqlite", ".onnx", ".mp4", ".mov"}

# order matters: the long forms first
REPLACE = [
    (r"[A-Za-z0-9._%+-]+@gmail\.com", "owner@example.com"),
    (r"Branislav Gombos", "The Owner"),
    (r"Branislav", "Owner"),
    (r"Gombos", "Owner"),
    (r"Brano's", "the owner's"),
    (r"Brano", "the owner"),
    (r"Bad Kissingen", "Your City"),
    (r"ScalpingEdward", "your-github-user"),
    (r"tail[0-9a-f]{6}\.ts\.net", "your-tailnet.ts.net"),
    (r"desktop-b33ntab", "your-pc"),
    (r"17909762832554719", "1234567890"),
    (r"\b700167790\b", "12345678"),
    (r"@Auronsignalbot", "@YourSignalBot"),
    (r"VIP SIGNALS Ninja Inner Circle", "Signal Group A"),
    (r"VIP SIGNALS", "Signal Group"),
    (r"ICT CRT PREMIUM", "Signal Group B"),
    (r"Ninja Inner Circle", "Signal Group A"),
]
# n8n: Drive folder ids and credential ids
N8N = [
    (r'"1[A-Za-z0-9_-]{24,40}"', '"YOUR_DRIVE_FOLDER_ID"'),
    (r'("credentials":\s*\{[^{}]*?\{[^{}]*?"id":\s*)"[^"]+"', r'\1"YOUR_CREDENTIAL_ID"'),
]
STILL = re.compile(r"gmail\.com|Gombos|Branislav|\bBrano\b|Kissingen|ScalpingEdward|tail2b4344|b33ntab|11puO-")


def main() -> None:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    keep = [f for f in files if not f.startswith(SKIP_DIRS) and f not in SKIP_FILES and Path(f).suffix.lower() not in SKIP_EXT]
    counts: dict[str, int] = {}
    left: list[str] = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in keep:
            raw = (ROOT / f).read_bytes()
            try:
                s = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue                       # binary we did not expect: better left out
            for pat, rep in REPLACE + (N8N if f.startswith("n8n/") and f.endswith(".json") else []):
                s, n = re.subn(pat, rep, s, flags=re.S)
                if n:
                    counts[pat] = counts.get(pat, 0) + n
            if STILL.search(s):
                left.append(f)
            z.writestr(f"auron/{f}", s)
        z.writestr("auron/README_EXPORT.md", "# AURON -- code export\n\nPersonal data removed: names, e-mail, place, account ids, "
                   "Drive folders, credentials. No .env, no database, no media. Secrets are never in the repository.\n")
    if left:
        raise SystemExit(f"still personal in: {left} -- not written")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(buf.getvalue())
    print(f"{len(keep)} files -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    for pat, n in counts.items():
        print(f"  {n:5d}x {pat}")


if __name__ == "__main__":
    main()
