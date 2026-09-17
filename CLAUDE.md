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
- Faehigkeiten dort pruefen, wo sie im Betrieb gebraucht werden, nicht daneben.
  Ein `touch` aus der Container-Shell belegt Dateisystemrechte -- nicht, dass
  ein n8n-Node schreiben darf: n8n prueft zusaetzlich selbst gegen
  N8N_RESTRICT_FILE_ACCESS_TO und scheitert mit "is not writable", obwohl
  Mount, UID und Rechte stimmen. Gegen die echte Funktion, den echten Pfad und
  die echte Schicht testen, sonst belegt der Test etwas anderes als die Aussage.
- Ein Ausweichpfad, der fuer eine Uebergangszeit gedacht war, ueberlebt die
  Uebergangszeit, weil er funktioniert. Er meldet Erfolg, wo etwas Unmoegliches
  passiert ist. Wer einen Platzhalter- oder Fallback-Zweig einbaut, schreibt in
  denselben Commit, wodurch er wieder verschwindet -- sonst wird er zum
  Normalfall. Beispiele: Platzhalter-Analyse fuer Videos (elf Tage, 30 kaputte
  Pool-Eintraege), Prefilter der "im Pool" mit "fertig analysiert" gleichsetzte,
  abgeschnittene Datei die ffprobe mit voller Dauer passierte.

## Content-Strategie Instagram
- Kernthema Trading traegt den Account (ca. die Haelfte der Posts).
- Portrait, Gym, Essen, Travel sind Stuetzsaeulen und muessen einen Bezug
  zum Kernthema haben.
- Reels sind der Reichweiten-Hebel, Carousels erreichen fast nur Follower.
- Hashtags sind Themenlabel, kein Reichweiten-Hebel: max 5, eng und real,
  keine erfundenen Tags.
- Kein Pillar zweimal hintereinander, kein gleiches visuelles Muster in
  benachbarten Grid-Plaetzen. Bild 1 eines Carousels ist der Hook.

## Aktueller Stand und offene Punkte
- Reel-Pfad (media_type=REELS, Status-Polling bis FINISHED, mvhd-Duration-Parsing)
  ist in n8n importiert, aber noch ungetestet -- kein Testlauf gegen die echte
  Graph API bisher.
- Schedule-Trigger im Drive-Ingest-Workflow steht auf 20 Minuten statt taeglich 09:00.
- Pillar-Feld (Trading/Portrait/Gym/Essen/Travel) fehlt noch im Datenmodell.
- Secrets rotieren.
- Docker Desktop RAM anheben.
- Content-Status rejected ist reversibel, post_failed ist retry-faehig.
