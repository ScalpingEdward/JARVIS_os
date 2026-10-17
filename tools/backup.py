"""AURON backup: everything that cannot be rebuilt from GitHub, encrypted, in three places.

    python tools/backup.py              # make one now
    python tools/backup.py --keep 14    # how many to keep per place (default 14)

What goes in (not the code -- GitHub has it -- and not the photos -- Google Drive has them):
  db.dump          Postgres (pg_dump -Fc): trades, mails, Instagram, insiders, watchlist ...
  n8n/             workflows + credentials (export, still encrypted with n8n's key) + n8n's config (that key)
  data.tgz         the API's /data volume without the image folders
  host/.env        all keys          host/secrets/      Docker secrets
  host/profiles/   copier profiles incl. Telegram logins (logs left out)
  host/lut/        the colour LUT

The bundle is a zip, encrypted with AES-256-GCM; the key comes from BACKUP_PASSPHRASE in .env
via scrypt. Without that passphrase a backup cannot be opened -- keep it in a password manager.
Written to C:\\Users\\brani\\AURON-Backups, copied to OneDrive\\AURON-Backups and uploaded to
Google Drive (folder AURON-Backups, scope drive.file: AURON only sees what it created there).
The result goes to the API (/v1/backup/status): status bar, and a Telegram alert on failure.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = Path.home() / "AURON-Backups"
ONEDRIVE = Path(os.getenv("OneDrive", str(Path.home() / "OneDrive"))) / "AURON-Backups"
LUT = Path(r"C:\JARVIS_Images\lut")
API = os.getenv("AURON_API", "http://127.0.0.1:8000")
MAGIC = b"AURONBK1"
DRIVE_FOLDER = "AURON-Backups"


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def run(cmd: list[str], **kw) -> bytes:
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:4])}...: {r.stderr.decode(errors='replace')[:300]}")
    return r.stdout


# ---------------------------------------------------------------- collect
def collect(z: zipfile.ZipFile, e: dict) -> dict:
    sizes = {}
    user, db = e.get("POSTGRES_USER", "jarvis"), e.get("POSTGRES_DB", "jarvis")
    dump = run(["docker", "exec", "jarvis_os-postgres-1", "pg_dump", "-U", user, "-d", db, "-Fc"])
    z.writestr("db.dump", dump)
    sizes["db"] = len(dump)

    run(["docker", "exec", "n8n", "sh", "-c",
         "rm -rf /tmp/auronbk && mkdir -p /tmp/auronbk && n8n export:workflow --all --output=/tmp/auronbk/workflows.json"
         " && n8n export:credentials --all --output=/tmp/auronbk/credentials.json && cp /home/node/.n8n/config /tmp/auronbk/config"])
    with tempfile.TemporaryDirectory() as td:
        run(["docker", "cp", "n8n:/tmp/auronbk/.", td])
        for f in Path(td).iterdir():
            z.write(f, f"n8n/{f.name}")
            sizes[f"n8n/{f.name}"] = f.stat().st_size
    run(["docker", "exec", "n8n", "rm", "-rf", "/tmp/auronbk"])

    data = run(["docker", "exec", "jarvis_os-api-1", "tar", "czf", "-", "-C", "/data", "--exclude=./images", "."])
    z.writestr("data.tgz", data)
    sizes["data"] = len(data)

    host = [(ROOT / ".env", "host/.env")]
    host += [(p, f"host/secrets/{p.name}") for p in (ROOT / "secrets").glob("*") if p.is_file()]
    for p in (ROOT / "signal_copier" / "profiles").rglob("*"):
        if p.is_file() and not p.name.endswith((".log", ".tmp")):
            host.append((p, "host/profiles/" + p.relative_to(ROOT / "signal_copier" / "profiles").as_posix()))
    if LUT.exists():
        host += [(p, f"host/lut/{p.name}") for p in LUT.glob("*") if p.is_file()]
    for src, arc in host:
        z.write(src, arc)
    sizes["host_files"] = len(host)
    z.writestr("MANIFEST.json", json.dumps({"made": datetime.now(timezone.utc).isoformat(), "sizes": sizes,
                                            "restore": "python tools/restore.py <file> -- see docs/UMZUG.md"}, indent=1))
    return sizes


# ---------------------------------------------------------------- encrypt
def key_from(passphrase: str, salt: bytes) -> bytes:
    import hashlib
    return hashlib.scrypt(passphrase.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)


def encrypt(blob: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    return MAGIC + salt + nonce + AESGCM(key_from(passphrase, salt)).encrypt(nonce, blob, MAGIC)


def decrypt(data: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not data.startswith(MAGIC):
        raise ValueError("not an AURON backup")
    salt, nonce = data[8:24], data[24:36]
    return AESGCM(key_from(passphrase, salt)).decrypt(nonce, data[36:], MAGIC)


# ---------------------------------------------------------------- places
def prune(folder: Path, keep: int) -> None:
    files = sorted(folder.glob("auron-*.bak"))
    for f in files[:-keep]:
        f.unlink()


def google_drive(path: Path, e: dict, keep: int) -> str:
    """Upload with the Gmail app's refresh token (scope drive.file); keeps the newest `keep`."""
    body = urllib.parse.urlencode({"client_id": e["GMAIL_CLIENT_ID"], "client_secret": e["GMAIL_CLIENT_SECRET"],
                                   "refresh_token": e["GMAIL_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    tok = json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", body, timeout=30).read())
    if "drive.file" not in tok.get("scope", ""):
        raise RuntimeError("Google login has no Drive right yet -- run python tools/gmail_auth.py once")
    auth = {"Authorization": f"Bearer {tok['access_token']}"}

    def call(url, data=None, headers=None, method=None):
        req = urllib.request.Request(url, data=data, headers={**auth, **(headers or {})}, method=method)
        return json.loads(urllib.request.urlopen(req, timeout=300).read() or b"{}")

    q = urllib.parse.quote(f"name='{DRIVE_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false")
    found = call(f"https://www.googleapis.com/drive/v3/files?q={q}&fields=files(id)").get("files", [])
    folder = found[0]["id"] if found else call("https://www.googleapis.com/drive/v3/files", json.dumps(
        {"name": DRIVE_FOLDER, "mimeType": "application/vnd.google-apps.folder"}).encode(), {"Content-Type": "application/json"})["id"]
    boundary = "auron" + secrets.token_hex(8)
    meta = json.dumps({"name": path.name, "parents": [folder]}).encode()
    payload = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + meta
               + f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + path.read_bytes()
               + f"\r\n--{boundary}--".encode())
    call("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart", payload,
         {"Content-Type": f"multipart/related; boundary={boundary}"})
    q = urllib.parse.quote(f"'{folder}' in parents and name contains 'auron-' and trashed=false")
    files = call(f"https://www.googleapis.com/drive/v3/files?q={q}&orderBy=name&fields=files(id,name)&pageSize=200").get("files", [])
    for f in files[:-keep]:
        call(f"https://www.googleapis.com/drive/v3/files/{f['id']}", method="DELETE")
    return "ok"


def report(status: dict) -> None:
    try:
        req = urllib.request.Request(f"{API}/v1/backup/status", json.dumps(status).encode(),
                                     {"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=20)
    except Exception as exc:  # noqa: BLE001 -- the backup itself is what counts
        print("  status not reported:", exc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=14)
    args = ap.parse_args()
    e = env()
    status = {"at": datetime.now(timezone.utc).isoformat(), "ok": False, "places": {}, "size": 0, "error": ""}
    try:
        passphrase = e.get("BACKUP_PASSPHRASE", "")
        if len(passphrase) < 12:
            raise RuntimeError("BACKUP_PASSPHRASE in .env missing or shorter than 12 characters")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            sizes = collect(z, e)
        blob = encrypt(buf.getvalue(), passphrase)
        assert decrypt(blob, passphrase) == buf.getvalue()  # never store a backup that would not open
        name = f"auron-{datetime.now():%Y%m%d-%H%M}.bak"
        status["size"], status["file"], status["contents"] = len(blob), name, sizes
        for place, folder in (("laptop", LOCAL), ("onedrive", ONEDRIVE)):
            try:
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_bytes(blob)
                prune(folder, args.keep)
                status["places"][place] = "ok"
            except Exception as exc:  # noqa: BLE001
                status["places"][place] = f"Fehler: {exc}"
        try:
            status["places"]["google_drive"] = google_drive(LOCAL / name, e, args.keep)
        except Exception as exc:  # noqa: BLE001
            status["places"]["google_drive"] = f"Fehler: {exc}"
        status["ok"] = status["places"].get("laptop") == "ok" and any(v == "ok" for k, v in status["places"].items() if k != "laptop")
    except Exception as exc:  # noqa: BLE001
        status["error"] = str(exc)
    print(json.dumps(status, indent=1))
    report(status)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
