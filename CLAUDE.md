## Arbeitsweise
- Antworte auf Deutsch, direkt, eine Aktion pro Antwort.
- Keine zwei Baustellen gleichzeitig.
- Vor groesseren Aenderungen erst Plan zeigen, dann umsetzen.
- Bei Unsicherheit stoppen und fragen statt raten.

## Projekt
Kurzbeschreibung AURON/JARVIS_os: FastAPI-Backend in Docker, Trading-Pipeline
(SMC, MT5) und Instagram-Content-Automation via n8n + Meta Graph API.
Ziel der Instagram-Seite: Reichweite aufbauen fuer den Weg zum hauptberuflichen Trader.

## Konventionen
- curl.exe statt curl (Windows/PowerShell)
- Rebuild: docker compose up -d --build api (nicht --force-recreate)
- n8n haengt: docker restart n8n
- n8n-Workflows NIE ueber offenes Canvas importieren -> Namen/Verbindungen kaputt.
  Import ausschliesslich per CLI: docker cp + n8n import:workflow, mit gesetztem
  id-Feld, damit ueberschrieben statt dupliziert wird.
- CLI-Import deaktiviert Workflows automatisch -> Aktivierungsstatus danach
  gegen Baseline pruefen und wiederherstellen; publish/unpublish wirkt erst
  nach docker restart n8n.
- Das Repo ist die Wahrheit. Wenn Live-Workflows weiter sind als das Repo,
  erst Live-Stand ins Repo syncen, dann darauf aufbauen.

## Content-Strategie Instagram
- Kernthema Trading traegt den Account (ca. die Haelfte der Posts).
- Portrait, Gym, Essen, Travel sind Stuetzsaeulen und muessen einen Bezug
  zum Kernthema haben.
- Reels sind der Reichweiten-Hebel, Carousels erreichen fast nur Follower.
- Hashtags sind Themenlabel, kein Reichweiten-Hebel: max 5, eng und real,
  keine erfundenen Tags.
- Kein Pillar zweimal hintereinander, kein gleiches visuelles Muster in
  benachbarten Grid-Plaetzen. Bild 1 eines Carousels ist der Hook.

## Signal-Kopierer (signal_copier/)
- Telegram-Gruppe -> MT5, nur Brano's eigenes Konto (PU Prime Demo, spaeter
  RoboForex Cent). Ein Python-Prozess (`python -m signal_copier.copier`),
  kein EA: er spricht ueber das Paket MetaTrader5 mit dem laufenden Terminal.
  Im Terminal erkennt man seine Positionen an Magic 26101400 und Kommentar
  `sig:<msg_id>:<leg>`. Laeuft seit 2026-10-15 scharf auf Demo.
- **Signale kommen verspaetet** (Brano, 2026-10-15): #4909 Sell Gold @ 4144
  kam bei 4140,57 an -- 34 Pips weg, abgelehnt bei damals 30 Pips Grenze.
  Gold steht jetzt auf 60 Pips (6 $). Offen: die Verspaetung messen
  (Nachrichtenzeit gegen Empfang und gegen den Kurs zur Nachrichtenzeit),
  bevor die Grenze weiter wandert -- eine weitere Grenze heisst schlechteres
  Chance-Risiko-Verhaeltnis, nicht mehr Risiko.

## Aktueller Stand und offene Punkte
- Reel-Pfad (media_type=REELS, Status-Polling bis FINISHED, mvhd-Duration-Parsing)
  ist in n8n importiert, aber noch ungetestet -- kein Testlauf gegen die echte
  Graph API bisher.
- Schedule-Trigger im Drive-Ingest-Workflow steht auf 20 Minuten statt taeglich 09:00.
- Pillar-Feld (Trading/Portrait/Gym/Essen/Travel) fehlt noch im Datenmodell.
- Secrets rotieren.
- Docker Desktop RAM anheben.
- Content-Status rejected ist reversibel, post_failed ist retry-faehig.
