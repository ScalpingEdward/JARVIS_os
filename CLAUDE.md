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
- Solo-Latte steht auf **0,62** (ab 2026-10-05, vorher 0,75). Bei 0,75
  schaffte sie **kein einziges** von 79 Videos und acht von 270 Fotos --
  Reels, der Reichweiten-Hebel, waeren nie entstanden. Dazu `never_solo`
  als Gegenpol zu `favorite`: Brano's Auge schlaegt die Zahl in beide
  Richtungen. Noetig, weil eine Standbild-Analyse Tempo, Schwenk und
  Enthuellung eines Clips nicht sehen kann -- er hat 11 Videos angesehen
  und 3 davon als "kein Reel" aussortiert.
- Die Bewertung sortiert nichts aus: ein schwaches Foto landet im Karussell,
  nicht im Muell. Die Latte entscheidet nur solo oder Gruppe. Und ein
  strenger Massstab ordnet trotzdem richtig -- nur die Zahlen sind niedrig.
  Offene Frage von Brano (2026-10-05): ob der Analyse-Prompt statt
  "high-end, curated" auf Reichweite umgestellt werden soll (Hook, Bewegung,
  Gesichter). Das aendert die Rangfolge wirklich, kostet aber 349 neue
  Analysen. Entschieden wird es nach 4 Wochen anhand seiner eigenen
  Insights, nicht vorher nach Theorie.
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
- Geplant, extern im Bau (eigener Chat): ein Futures-Bot fuer
  **NinjaTrader + Python** (Stand 2026-10-13), der spaeter Teil von AURON
  werden soll. Orderflow, Delta, Absorption. Eigener Baustein -- hier erst
  anfassen, wenn Instagram wirklich laeuft.
- Datenquellen dazu: siehe `docs/futures-bot-datenquellen.md`. Kurz: CME-L2
  (~16-17 $/Monat je Boerse) traegt Delta, Absorption und Imbalance; eine
  echte Heatmap braucht Market-by-Order (Databento); Options-Flow und Gamma
  sind **OPRA**, ein zweiter Markt und ein zweites Abo. Reihenfolge: ein
  Kontrakt, eine Quelle, ein Signal -- Optionen zuletzt.
- Verworfen: DeepCharts/Bookmap mit REA (Reverse Engineer Anything) oder
  aehnlichem nachbauen. Der Decompiler zeigt, wie sie zeichnen, nicht woher
  die Trades kommen -- der Engpass ist die Lizenz. Brano will ausdruecklich
  keinen Verstoss gegen Nutzungsbedingungen. Ausserdem braucht ein Bot die
  Darstellung nie, nur die Zahlen darunter.

## AURON auf dem LG-TV (tv_app/, tools/tv_gate/)
- TV: LG 65NANO806NA, webOS 5.6 = **Chromium 68** (2018), Magic Remote, IP 192.168.0.175.
  Laptop im WLAN: 192.168.0.105. Beide per DHCP -- feste IPs im Router, sonst stimmt
  `GATE` in tv_app/index.html bzw. `TV_IPS` nicht mehr.
- Die App ist nur eine Tuer: sie oeffnet `http://<laptop>:8090`. Dort sitzt
  `tools/tv_gate/gate.mjs` vor dem Dashboard (127.0.0.1:8080) und schreibt es fuer
  Chromium 68 um (esbuild fuer `?.`/`??`, color-mix -> rgba(var(--accent-rgb)), clamp/min/max
  bei fester 1920x1080 ausgerechnet, translate:/rotate:/scale: -> transform). Was CSS nicht
  kann (Flex-gap, aspect-ratio, Akzent aus dem Look-Panel), macht `shim.js` zur Laufzeit.
  Das Dashboard selbst bleibt unveraendert. Neue moderne CSS/JS-Syntax im Dashboard kann
  den TV wieder brechen -- gate.mjs loggt uebrig gebliebene color-mix/clamp.
- Das Gate ist auch das Schloss: die API hat keinen Login, also kommen nur TV_IPS und der
  Laptop selbst rein, alle anderen bekommen 403. Tailscale gibt es fuer webOS nicht, Funnel
  waere oeffentlich -- deshalb Heimnetz.
- Gemessen 2026-10-29: ~6 s pro Bild -- das war der geteilte 3D-Raum (.stage perspective +
  preserve-3d), nicht die Animationen. Flache Szene (jede Kachel traegt ihre Perspektive selbst)
  -> ~0,25 s ohne, ~0,45 s mit allen CSS-Animationen. Die echte Traegheit kam danach per Profiler
  (DevTools-Protokoll, Profiler + Performance.getMetrics): im Leerlauf 82 % Hauptthread, davon
  2,4 s/6 s Skript -- der Globus projizierte jedes Bild die ganze Weltkarte neu, obwohl er still
  steht (jetzt nur bei Aenderung, globe.js), das Tab-Icon 4x/s (ringicon.js, bei reduced-motion
  einmal), die Trading-Kachel jede Sekunde komplett neu inkl. Neuvermessung **aller** Karten
  (jetzt nur bei geaendertem Inhalt und nur die geaenderte Karte, cardview.js), ein neuer
  Intl.NumberFormat pro Zahl (jetzt einer pro Nachkommastellen). Auf dem TV kommen die
  Live-Kurse alle 3 s statt 1 s (shim.js biegt setInterval(refreshLive) um).
  Animationen: alle an ausser Filter/Blur (Energie, Strahl, Sonnenpuls -- TV_OFF). Schwebende
  Karten allein druecken den TV auf 5 fps (alles still: 56, Ringe: 34-42) -- Brano will sie
  trotzdem ("Schwebend", 2026-10-29). Waehrend der
  Bedienung halten die animierten Elemente einzeln an (bis 2 s nach dem letzten Druck) -- eine
  Klasse an <html> mit `*`-Selektor liess den Chip die ganze Seite neu berechnen (0,8 s).
  Gemessen Taste bis Bild: erster Druck ~0,25-0,35 s, danach ~0,04 s.
  Die Skripte sehen reduced-motion (Partikelfeld ist eine O(n^2)-Canvas-Schleife). Flach hiess auch: Klicks landen richtig, Detailansichten
  dunkler hinterlegt (kein backdrop-filter vor Chrome 76). Die Ringe liegen im Design etwas unter
  dem Planeten -- in 3D-Perspektive wirkt das "drumherum", flach nicht: shim.js zentriert sie.
  translate:/rotate:/scale: werden zu transform -- eine Animation auf transform wuerde damit die
  Position loeschen (Ringe rutschten weg); shim.js baut solche Keyframes pro Element mit beiden
  Teilen nach (config.keyframes/transforms aus gate.mjs). `zoom: 1.1` auf `.detail .view`: Chromium 68 malt gezoomt,
  meldet getBoundingClientRect aber ungezoomt -- shim.js rechnet das fuer die Pfeiltasten um.
- Karten auf dem TV gerade statt schraeg (Brano, 2026-10-29) -- gelbe Taste schaltet um, der TV
  merkt es sich (localStorage auron_tv_straight). Erst nur am TV; spaeter evtl. als Einstellung.
- Fernbedienung: Zeiger = Maus. Pfeile springen zum naechsten Bedienelement, OK klickt,
  Zurueck = Escape. Textfelder werden per Pfeil nur ausgewaehlt (read-only geparkt, damit die
  TV-Tastatur nicht aufspringt); OK oeffnet sie zum Tippen, Zurueck parkt sie wieder.
  `confirm()` liefert in der webOS-App sofort "nein", ohne Dialog. shim.js ersetzt es:
  erster Druck zeigt die Frage und sagt nein, derselbe Knopf nochmal binnen 5 s sagt ja.
- Neu aufspielen: `ares-package tv_app -o <ordner>` und `ares-install -d lgtv <ipk>`.
  Debuggen: Web-Inspector des TVs auf 192.168.0.175:9998 (DevTools-Protokoll, auch
  Page.captureScreenshot). Die LG-App "Developer Mode" laeuft nach ~50 h ab -> dort "Extend".
- **Beim Testen nie OK/Klick auf echte Aktionsknoepfe** -- das Dashboard am TV ist die echte
  API. Am 2026-10-29 hat ein Testklick die Caption-Stimme gespeichert und einer "Freigeben"
  getroffen (nur weil confirm() nein sagte, ist nichts gepostet worden).

## Signal-Kopierer (signal_copier/)
- Mögliches Geschäft daraus (Abo, Partnerschaft mit Gruppen, offene Fragen
  an Steuerberater/Anwalt): `docs/signal-copier-business.md`. Nichts
  entschieden; erst 2–4 Wochen Demo.
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
- Reel-Pfad ist **gegen die echte Graph API gelaufen** (2026-10-05, media_id
  17909762832554719, danach von Brano geloescht). Upload, Status-Polling bis
  FINISHED und Veroeffentlichung halten. Was dabei auffiel, steht oben unter
  Musik: ein per API gepostetes Reel bekommt keine Musik mehr.
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
- Erledigt (geprueft 2026-10-08): der Publish-Webhook nimmt `post_ref`, also
  die bearbeitete Fassung, und `_post_refs()` verweigert den Post, wenn sie
  fehlt, statt auf das Original zurueckzufallen. Fotos werden beim Ingest
  gegradet (grade_photo_bytes -> process_image) und nach "AURON fertig"
  hochgeladen.
- Weiter offen: HEIC wuerde bei Instagram scheitern (nur JPG). Bis zum
  Ingest-Konverter (pillow-heif) HEIC vor dem Upload lokal umwandeln,
  Live-Photo-MOVs (gleicher Name wie HEIC, <3 s) nicht hochladen. Originale
  im Drive-Upload-Ordner erst loeschen, wenn klar ist, dass kein
  Pool-Eintrag mehr auf sie zeigt.
- Erledigt (geprueft 2026-10-08): 270 Fotos und 79 Videos haben alle eine
  bearbeitete Fassung, und alle liegen in Drive -- 0 offene Uploads.
- Erledigt 2026-10-08: Curation lief nach jeder einzelnen Datei und haengt
  jetzt am "fertig"-Ausgang der Schleife -- einmal pro Lauf. Vorher wurden
  die ersten zwei Fotos eines Tages schon zu einem Entwurf verheiratet,
  bevor das dritte ueberhaupt eingelesen war: Karussells zerfielen.
- Dabei gefunden und behoben: **jeder Ingest-Lauf schlug fehl**, seit alles
  eingelesen war. n8ns Google-Drive-Knoten gibt bei leerem Suchergebnis ein
  leeres Element aus statt gar keines; der Workflow machte daraus einen
  Eintrag ohne Felder, die API lehnte mit 422 ab, der Lauf starb. Jetzt
  verwirft der Ausdruck leere Eintraege, die API akzeptiert leere Listen,
  und eine IF-Weiche fuehrt "nichts Neues" an der Schleife vorbei direkt
  zur Kuration -- ein normaler Lauf mit Antwort 200 statt 500.
- Ein 422 an einen n8n-HTTP-Knoten zeigt sich dort nur als "Your request is
  invalid or could not be processed by the service". Deshalb loggt die API
  seit 2026-10-08 jede Validierungs-Ablehnung mit Feld und Grund
  (main.py, _log_validation_errors) -- die Suche danach hat eine Stunde
  gekostet.
- Offen: n8n-SQLite ~1,5 GB, "Database connection timed out" -- verliert
  gelegentlich einzelne Requests (API-Nodes haben deshalb 3 Retries).
- Drive: Google One 100 GB seit 2026-09-22 (15 GB waren voll -> 403 beim Upload).
