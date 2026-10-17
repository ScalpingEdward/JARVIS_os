# AURON sichern und umziehen

## Backup

- **Automatisch** jede Nacht um 3:00 (Windows-Aufgabe „AURON Backup“; lief der Laptop nicht,
  holt Windows es beim nächsten Start nach). Von Hand: `python tools/backup.py`.
- **Drei Orte**, je die letzten 14:
  - Laptop: `C:\Users\brani\AURON-Backups\`
  - OneDrive: `OneDrive\AURON-Backups\`
  - Google Drive: Ordner `AURON-Backups` (AURON darf dort nur seine eigenen Dateien sehen)
- **Verschlüsselt** (AES-256-GCM). Das Passwort steht als `BACKUP_PASSPHRASE` in `.env`
  und gehört zusätzlich in den Passwort-Manager -- ohne es ist kein Backup lesbar.
- **Inhalt:** Postgres (Trades, Mails, Instagram, Insider, Watchlist …), n8n-Workflows und
  -Zugänge mit n8n-Schlüssel, das `/data`-Volume der API, `.env`, `secrets/`, die
  Kopierer-Profile mit Telegram-Logins, die LUT. Nicht drin: der Code (GitHub) und die
  Fotos (Google Drive).
- **Status:** unten in der Leiste „Backup · vor X h“. Telegram meldet einen fehlgeschlagenen
  oder unvollständigen Lauf, und einmal täglich, wenn das letzte gute Backup älter als 48 h ist.

## Umzug auf einen neuen PC (oder Server)

1. Docker Desktop, Git, Python 3.12+ installieren; `git clone` des Repos.
2. Backup holen (OneDrive oder Google Drive) und öffnen -- fragt nach dem Passwort:
   `python tools/restore.py auron-JJJJMMTT-HHMM.bak --to C:\auron-restore`
3. Dateien zurücklegen:
   - `host/.env` → Repo-Wurzel `.env`; `host/secrets/*` → `secrets/`
   - `host/profiles/*` → `signal_copier/profiles/`
   - `host/lut/*` → `C:\JARVIS_Images\lut\`
4. `docker compose up -d --build` -- startet Postgres leer.
5. Datenbank einspielen:
   `docker cp C:\auron-restore\db.dump jarvis_os-postgres-1:/tmp/db.dump`
   `docker exec jarvis_os-postgres-1 pg_restore -U jarvis -d jarvis --clean --if-exists /tmp/db.dump`
6. API-Daten: `docker cp C:\auron-restore\data.tgz jarvis_os-api-1:/tmp/` und
   `docker exec jarvis_os-api-1 tar xzf /tmp/data.tgz -C /data`
7. n8n: `n8n/config` nach `/home/node/.n8n/config` (vor dem ersten Start -- darin steht der
   Schlüssel für die Zugänge), dann per CLI importieren (siehe CLAUDE.md, nie über das Canvas):
   `n8n import:credentials --input=credentials.json` und `n8n import:workflow --input=workflows.json`;
   danach Aktivierung prüfen.
8. MT5-Terminals installieren und anmelden, Kopierer-Autostart:
   `python -m signal_copier.profiles autostart <profil>`.
9. Gmail/Drive: `python tools/gmail_auth.py`; Backup-Aufgabe neu anlegen (siehe `tools/backup.py`).

Geprüft am 2026-10-17: Backup geöffnet, Datenbank in eine Test-DB zurückgespielt
(42 Mails, 154 Insider-Trades, 2 Kopierer), 10 n8n-Workflows lesbar.
