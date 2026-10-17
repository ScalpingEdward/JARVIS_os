"""Open an AURON backup: decrypt and unpack it into a folder -- nothing is overwritten.

    python tools/restore.py C:\\Users\\brani\\AURON-Backups\\auron-20261017-0300.bak
    python tools/restore.py <file> --to C:\\restore-test

Asks for the passphrase if BACKUP_PASSPHRASE is not in .env (on a new PC it is not).
What to do with the unpacked parts: docs/UMZUG.md.
"""
from __future__ import annotations

import argparse
import getpass
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup import decrypt, env  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--to", default=None)
    args = ap.parse_args()
    src = Path(args.file)
    try:
        passphrase = env().get("BACKUP_PASSPHRASE", "")
    except FileNotFoundError:
        passphrase = ""
    passphrase = passphrase or getpass.getpass("Backup-Passwort: ")
    blob = decrypt(src.read_bytes(), passphrase)
    target = Path(args.to or src.with_suffix(""))
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        z.extractall(target)
        names = z.namelist()
    print(f"{len(names)} files unpacked to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
