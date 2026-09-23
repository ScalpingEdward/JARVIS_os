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
- Phase 1 (ab 2026-09-23, Brano): sichtbares Thema ist **Lifestyle** --
  Travel, Portrait, Gym, Essen. **Trading-BILDER duerfen rein** (Screens,
  Setup, Schreibtisch): sie werden nicht aussortiert. Was nicht passiert,
  ist, dass die **Caption** darueber redet -- keine Maerkte, keine Charts
  als Thema, keine Zahlen, keine Gewinne, keine Ergebnisse, und nicht
  zweimal hintereinander dieselbe Trading-Anspielung. Grund: Brano handelt
  noch nicht hauptberuflich und will weder als Ratgeber angesprochen werden
  ("was soll ich investieren?") noch Neid ernten, bevor er es beherrscht.
  Man darf ahnen, dass ein Handwerk dahintersteckt -- mehr nicht.
- Phase 2, spaeter und erst auf Brano's Ansage: Charts und Zahlen duerfen
  dazukommen. Bis dahin gilt Phase 1 auch fuer Captions (siehe
  DEFAULT_BRAND_VOICE in caption_writer.py).
- Reels sind der Reichweiten-Hebel, Carousels erreichen fast nur Follower.
- Hashtags sind Themenlabel, kein Reichweiten-Hebel: max 5, eng und real,
  keine erfundenen Tags.
- Kein Pillar zweimal hintereinander, kein gleiches visuelles Muster in
  benachbarten Grid-Plaetzen. Bild 1 eines Carousels ist der Hook.
- Musik ist Pflicht-Atmosphaere (Brano, 2026-09-22). Daraus folgt der
  Veroeffentlichungsweg:
  * Carousels + Einzelfotos: halbautomatisch. Karte mit Vorschau in
    Reihenfolge -> Freigabe -> Bot schickt Dateien in voller Qualitaet +
    Caption/Hashtags zum Kopieren -> Brano postet in der App mit Musik ->
    Button "Gepostet". Grund: keine API (auch nicht Meta) kann Musik an
    Fotos/Carousels haengen.
  * Reels: vollautomatisch. AURON waehlt Musik ueber die Instagram Audio API
    (audio_id, nur Reels, nur "Instagram API with Facebook Login" -- wir
    laufen aktuell ueber Instagram Login, Umstellung noetig), Brano gibt frei,
    AURON postet. Spricht Brano im Video: Musik leise darunter
    (audio_volume/video_volume) oder keine.
  * Zeiten: Reels 19:00, Fotos/Carousels 12:00, Di-Do bevorzugt. Nach
    4 Wochen gegen eigene Insights pruefen.

## Aktueller Stand und offene Punkte
- Reel-Pfad (media_type=REELS, Status-Polling bis FINISHED, mvhd-Duration-Parsing)
  ist in n8n importiert, aber noch ungetestet -- kein Testlauf gegen die echte
  Graph API bisher.
- Schedule-Trigger im Drive-Ingest-Workflow steht auf 20 Minuten statt taeglich 09:00.
- Pillar-Feld (Trading/Portrait/Gym/Essen/Travel) fehlt noch im Datenmodell.
- Secrets rotieren.
- Docker Desktop RAM: Laptop hat nur 7,4 GB, Docker-VM ~3,5 GB -- anheben geht
  kaum. Deshalb: Ingest-Loop verarbeitet 1 Datei pro Runde, ffmpeg auf 2
  Threads, Videos werden auf max. 1920 px Kante verkleinert (4K HDR lief sonst
  in OOMKilled).
- Content-Status rejected ist reversibel, post_failed ist retry-faehig.
- Geplant: Kennzeichen-Engine -- Auto-Kennzeichen in Fotos/Videos erkennen und
  unkenntlich machen, beim Ingest (gleiche Stelle wie Schnitt/Grading, solange
  die Datei noch existiert). Eigener Baustein, nicht nebenbei.
- Geplant: Tagesregel + Duplikat-Filter (ein Shooting -> ein Post, fast gleiche
  Bilder raus), danach Score-Kriterien schaerfen (Hook, Themenbezug,
  Einzigartigkeit, Technik, Grid-Nachbarn). Starke Videos als Reel, gute
  Videos duerfen ins gemischte Carousel.
- Offen: Publish-Webhook nimmt immer das Drive-Original, nie processed_media_ref
  -> gegradete Videos werden nicht gepostet, HEIC wuerde bei Instagram
  scheitern (nur JPG). Fix: HEIC beim Ingest -> JPG (pillow-heif), Publish auf
  processed_media_ref umstellen. Bis dahin HEIC vor dem Upload lokal umwandeln,
  Live-Photo-MOVs (gleicher Name wie HEIC, <3 s) nicht hochladen.
  Dazu gehoert: Fotos beim Ingest ebenfalls graden (process_image existiert,
  wird nicht aufgerufen) und nach "AURON fertig" hochladen. Erst danach
  duerfen Originale im Drive-Upload-Ordner geloescht werden -- vorher zeigen
  alle Pool-Eintraege auf sie.
- Offen: 34 Videos ohne bearbeitete Fassung (30 alte von vor der
  Ingest-Bearbeitung, 4 wo ffmpeg vor dem Speicher-Fix starb) nachholen;
  3 bearbeitete Videos noch nicht in Drive (naechster Lauf nimmt sie mit).
- Offen: Curation laeuft nach jeder einzelnen Datei statt einmal am Ende.
- Offen: n8n-SQLite ~1,5 GB, "Database connection timed out" -- verliert
  gelegentlich einzelne Requests (API-Nodes haben deshalb 3 Retries).
- Drive: Google One 100 GB seit 2026-09-22 (15 GB waren voll -> 403 beim Upload).
