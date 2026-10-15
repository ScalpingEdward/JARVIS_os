"""Builds a zip to hand to someone else -- without anything of mine in it.

    python -m signal_copier.pack            -> dist/SignalCopier_<date>.zip

Only listed files go in. A whitelist, not a blacklist: .env holds my keys,
copier.session IS my Telegram login, state.json my open trades -- a new file
next to them must stay out unless it is added here on purpose.
"""
from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
SHIP = ["__init__.py", "book.py", "chat_id.py", "copier.py", "execution.py", "parser.py", "risk.py",
        "sizing.py", "symbols.py", "telegram_check.py",
        "requirements.txt", ".env.example", "setup.bat", "start.bat", "chat_id.bat", "ANLEITUNG.md"]
NEVER = {".env", "copier.session", "copier.session-journal", "state.json", "copier.log"}


def build(out_dir: Path) -> Path:
    assert not NEVER & set(SHIP), "a private file is on the ship list"
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    config["allow_live"] = False      # the receiver switches to live himself, deliberately
    config["initial_balance"] = None  # his account, his starting balance

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"SignalCopier_{date.today():%Y-%m-%d}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in SHIP:
            if name.endswith(".bat"):  # cmd misreads if/else blocks with bare LF line ends
                text = (HERE / name).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
                z.writestr(f"SignalCopier/signal_copier/{name}", text)
            else:
                z.write(HERE / name, f"SignalCopier/signal_copier/{name}")
        z.writestr("SignalCopier/signal_copier/config.json", json.dumps(config, indent=2))
    return out


if __name__ == "__main__":
    print(build(HERE.parent / "dist"))
