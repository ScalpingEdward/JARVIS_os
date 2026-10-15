"""Builds a zip to hand to someone else -- without anything of mine in it.

    python -m signal_copier.pack            -> dist/SignalCopier_<date>.zip

Only listed files go in. A whitelist, not a blacklist: .env holds my keys,
each profile folder holds state, log and Telegram login -- a new file
next to them must stay out unless it is added here on purpose.
"""
from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
SHIP = ["__init__.py", "book.py", "chat_id.py", "copier.py", "execution.py", "parser.py", "risk.py",
        "sizing.py", "symbols.py", "telegram_check.py", "profiles.py", "profile_template.json", "report.py",
        "requirements.txt", ".env.example", "setup.bat", "start.bat", "neues_profil.bat", "chat_id.bat",
        "ANLEITUNG.md"]
# profiles/ holds every account's state, log and Telegram login -- it never ships.
NEVER = {".env", "copier.session", "copier.session-journal", "profiles"}


def build(out_dir: Path) -> Path:
    assert not NEVER & set(SHIP), "a private file is on the ship list"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"SignalCopier_{date.today():%Y-%m-%d}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in SHIP:
            if name.endswith(".bat"):  # cmd misreads if/else blocks with bare LF line ends
                text = (HERE / name).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
                z.writestr(f"SignalCopier/signal_copier/{name}", text)
            else:
                z.write(HERE / name, f"SignalCopier/signal_copier/{name}")
    return out


if __name__ == "__main__":
    print(build(HERE.parent / "dist"))
