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

## Bildbearbeitung: zwei Wege, nicht einer
- Zwei Drittel der Fotos im Pool kamen schon aus Lightroom Mobile (EXIF
  Software = "Adobe Lightroom ... (iOS)"). Die trugen Brano's Look bereits in
  den Pixeln und bekamen ihn durch INSTA.cube ein zweites Mal -- sie sahen
  knallig aus, waehrend rohe Kameradateien daneben wie unbearbeitet wirkten.
  Brano hat das an zwei Bildern gesehen, bevor eine Messung es sagte.
  Seitdem: `developed_by()` liest EXIF Software, und es gibt zwei Ketten.
  * schon entwickelt -> kein LUT, keine Kurve, nur eq=saturation=1.05 und
    halbe Schaerfe.
  * Kameradatei oder kein EXIF -> LUT + Kurve + Angleichung + Schaerfe.
- Die Angleichung wurde gemessen, nicht geschaetzt: dasselbe Foto dreimal
  (roh / AURON / Lightroom), ueber drei Szenen (Himmel, Innenpool, graues
  Autocockpit). Blau war das Einzige, das in allen dreien in dieselbe
  Richtung fehlte, und zwar proportional zum Blauanteil (+11,6 / +11,8 /
  +2,3) -- deshalb `colorchannelmixer=bb=1.06`, ein Faktor, kein Zuschlag.
  `eq=brightness=0.015`, weil kleinere Werte die YUV-Rundung nicht
  ueberleben (0.008 kam dunkler heraus als gar nichts).
- Saettigung und Kontrast bleiben absichtlich ungeregelt. Sie wichen ueber
  dieselben drei Bilder zwischen -9 und +17,6 ab, in beide Richtungen:
  Lightroom entscheidet sie pro Bild (Dynamik gewichtet nach vorhandener
  Farbe). Jeder feste Wert waere fuer ein Bild richtig und fuer zwei falsch.
  Wer das "nachbessert", macht es schlechter.
- Was eine .cube grundsaetzlich nicht kann: Weissabgleich pro Bild, Klarheit,
  Textur, Dunst, Objektivkorrektur. Masken spielen keine Rolle -- die gibt es
  in Lightroom Mobile nur mit Premium, und Brano hat das nicht.
- Richtiger Weg fuer neue Fotos: Brano entwickelt in LR, laedt den Export
  hoch, AURON fasst die Farbe nicht an. Videos kommen als Original und werden
  bearbeitet. Verworfen: LR Classic ueber einen ueberwachten Ordner
  fernsteuern -- PC und LR muessten laufen, der Export braucht trotzdem einen
  Klick, und Brano's Vorgabe liegt in LR Mobile, das keinen solchen Ordner hat.

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
- Captions: der Schreiber kannte seine eigenen letzten Captions nicht --
  jede entstand allein aus derselben Stimme, also kam fuenfmal hintereinander
  dieselbe Predigt ("some rewards are quiet enough to need no audience").
  Brano hat es am Feed gemerkt, nicht an einer Pruefung. Seitdem: die letzten
  acht Captions gehen in den Prompt, und der ruhige Disziplin-Ton ist
  **erlaubt, aber nicht zweimal hintereinander** (_sermon_problem prueft gegen
  die vorige Caption, nicht gegen eine Quote). Loeschen wollte er ihn
  ausdruecklich nicht -- er gehoert zu ihm, er darf nur kein Tic werden.
- Brano ueber sich (2026-10-05, fuer die Caption-Stimme): ein bisschen
  verrueckt, bescheiden, gutes Herz, diszipliniert, hart gegen sich, trotzdem
  witzig. Der Humor fehlte am meisten. Sprache: Englisch.
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
  * Reels: **ebenfalls halbautomatisch** (korrigiert 2026-10-05). Der erste
    echte Reel-Post lief technisch durch (media_id 17909762832554719), aber
    Brano hat danach geprueft: ein per API gepostetes Reel bietet im
    Bearbeiten-Fenster **gar keine Musikauswahl**. Nachlegen geht nur bei
    Fotos. Damit faellt die Grundlage der Vollautomatik weg -- sie kommt
    zurueck, wenn AURON die audio_id selbst setzen kann (Instagram Audio API,
    nur Reels, nur "Instagram API with Facebook Login"; wir laufen ueber
    Instagram Login). Bis dahin verweigert publish_mode.auto_publish_refusal
    jedes automatische Posten mit Begruendung -- der Schalter allein reicht
    nicht mehr -- **nur fuer Reels**. Fotos und Karussells posten sich
    weiter selbst, Brano legt die Musik danach im Bearbeiten-Fenster nach
    (das geht dort, er hat es im September geprueft). Sie mit
    zurueckzuhalten waere Mehraufwand fuer ihn statt weniger.
    Spricht Brano im Video: Musik leise darunter oder keine.
  * Zeiten: **ein Post pro Tag**, und WELCHER entscheidet die Warteschlange,
    nicht der Kalender: aeltester Aufnahmetag zuerst, ein Tag wird
    abgearbeitet bevor der naechste beginnt. Die Sorte bestimmt nur die
    Uhrzeit -- Reel 19:00, Foto/Carousel 12:00 (schedule.py). Zwei Versionen
    davor waren falsch: zwei Karten taeglich (verbrennt den Vorrat) und
    Wechsel nach Kalender/letztem Post (liess ein Reel vom 3. die Fotos vom
    1. ueberholen). Nach 4 Wochen gegen eigene Insights pruefen.
  * Verworfen (2026-09-23): Instagram-Oberflaeche lokal per Browser
    fernsteuern, um Musik zu setzen. Brano hat im Web geprueft -- **die
    Web-Oberflaeche bietet bei Foto-Posts gar keine Musikauswahl**, und
    UI-Automatisierung verstoesst gegen Instagrams Nutzungsbedingungen
    (Account-Sperre). Der halbautomatische Weg bleibt.

## Trading-Seite: viel Code, noch kein Strom
- Stand 2026-10-05: rund 250 Module, 47 Trading-Testdateien -- und
  `/v1/accounts` ist leer, kein MT5-Terminal laeuft,
  `bridge/mt5_bridge_state.json` zuletzt am 4. September angefasst. Alles
  Gruene dort ist pytest-gruen, nicht betriebsgruen. Wer hier weiterbaut,
  baut auf etwas, das noch nie echte Daten gesehen hat.
- Die MT5-Bruecke ist absichtlich **nur lesend** (`read_only=True`, sonst
  verweigert `mt5_bridge` die Registrierung). Order-Ausfuehrung ist ein
  eigener Baustein, nicht ein Flag.
- Brano hat ein MT5-Konto, handelt aber aktuell eine **Challenge auf MT4**
  (2026-10-05). Das Python-Paket `MetaTrader5` spricht ausschliesslich mit
  MT5-Terminals -- fuer MT4 braeuchte es einen eigenen Weg (MQL4-EA, der
  Daten herausschreibt). Diese Arbeit faellt weg, sobald die Challenge auf
  MT5 laeuft: also nicht bauen, solange die MT4-Challenge laeuft.
- Erster sinnvoller Schritt, wenn es soweit ist: MT5-Demokonto anschliessen
  und pruefen, dass `/v1/accounts` denselben Kontostand zeigt wie das
  Terminal. Nachweisbar wahr oder nachweisbar falsch, an einem Abend.
- Geplant, extern im Bau: ein Futures-Bot auf **DXFeed**-Daten, der spaeter
  Teil von AURON werden soll (Daten verarbeiten, analysieren, handeln).
  Eigener Baustein -- erst anfassen, wenn Instagram wirklich laeuft.

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
