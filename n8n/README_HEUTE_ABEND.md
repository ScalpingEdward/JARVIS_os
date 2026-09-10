# AURON Instagram-Testlauf -- heute Abend, Schritt für Schritt

## 1. Google Drive vorbereiten

Erstelle einen Ordner, z.B. **"AURON Instagram Pool"**. Lade dort direkt
deine Fotos/Videos vom Training hoch (nicht iCloud -- das System spricht
nur mit Google Drive). Keine Unterordner nötig, AURON gruppiert selbst
nach Thema.

Merk dir die Ordner-ID aus der Drive-URL:
`https://drive.google.com/drive/folders/DIESE_ID_HIER`

## 2. n8n-Workflow importieren

Zwei fertige Workflow-Dateien liegen in `n8n/` in deinem Repo:

- `auron-instagram-drive-ingest.json` -- der Hauptlauf: liest neue Dateien
  aus Drive, schickt sie an AURON zur Analyse, stösst Kuration an.
- `auron-notification-escalation.json` -- erinnert dich, falls eine
  Freigabe-Benachrichtigung 10+ Minuten unbeantwortet bleibt.

In n8n: **Workflows -> Import from File** -> jeweilige Datei wählen.

Danach in `auron-instagram-drive-ingest.json` zwei Platzhalter ersetzen:
- Im Node "Google Drive: List New Files": deine echte Ordner-ID aus Schritt 1
- Google-Drive-Zugangsdaten (OAuth2) einmalig in n8n hinterlegen, falls
  noch nicht geschehen

Und den Hostnamen `auron-api` in beiden HTTP-Request-Nodes an deinen
echten Container-/Servernamen anpassen, falls er anders heisst. Beide
Container müssen im selben Docker-Netzwerk (`jarvis_shared`) hängen --
Details dazu stehen in `docs/n8n-instagram-setup.md`.

## 3. ANTHROPIC_API_KEY setzen (der wichtigste Schritt)

In der `.env`-Datei auf deinem echten Server:
```
ANTHROPIC_API_KEY=sk-ant-...
```
Server danach neu starten. Ohne das verweigert AURON die Analyse korrekt
-- sie erfindet nichts, aber sie kann auch nichts.

## 4. Trockentest laufen lassen -- BEVOR du n8n scharf schaltest

```
python3 n8n/auron_instagram_smoke_test.py --base-url http://DEIN-SERVER:8000
```

Das schickt ein winziges echtes Testbild durch die komplette Kette:
Analyse -> Kuration -> Caption -> Freigabe-Status. Wenn das grün durchläuft,
weisst du sicher, dass die Kette steht, bevor deine echten Fotos dran sind.
Falls dein Server ein `X-Auron-Operator-Token` verlangt, häng
`--operator-token DEIN_TOKEN` an.

## 5. n8n-Workflow aktivieren

Sobald Schritt 4 grün ist: Workflow in n8n auf "Active" stellen. Er läuft
dann automatisch täglich 09:00 Uhr -- für den Test heute kannst du ihn
auch manuell per "Execute Workflow" anstossen, statt auf 09:00 zu warten.

## 6. Ergebnis ansehen

`GET /v1/instagram/dashboard` zeigt dir die entstandenen Kandidaten. Jeder
wartet im Status `proposed` -- also fertig kuratiert, Caption geschrieben,
aber **nicht veröffentlicht**. Genau wie beim Trading: die Freigabe zum
Posten bleibt bei dir, über
`POST /v1/instagram/candidates/{id}/decision`.

## 7. Meta Graph API + professioneller Account -- der letzte Schritt zum echten Posten

Das ist der einzige Teil, der ausserhalb von AURON und ausserhalb dieser
Anleitung liegt -- er läuft komplett in n8n, nicht im AURON-Code, laut
Konzept ("kein Meta-Credential lebt jemals in AURON").

Was dafür nötig ist, aus dem, was schon mal angefangen wurde (App "JARVIS
INST" existiert bereits im Meta Developer Portal, aber die Instagram
Business Account ID fehlte beim letzten Stand):

1. Dein Instagram-Account muss ein **Business- oder Creator-Konto** sein
   (nicht privat) und mit einer **Facebook-Seite** verknüpft sein -- ohne
   Facebook-Seite gibt es keine Instagram Business Account ID.
2. In der Meta Business Suite (business.facebook.com) prüfen, dass die
   Facebook-Seite mit deinem Instagram-Account verbunden ist.
3. Im Graph API Explorer (developers.facebook.com/tools/explorer), App
   "JARVIS INST" auswählen, Token mit den Berechtigungen
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`
   generieren.
4. Abfrage `GET /me/accounts` liefert deine Facebook-Seiten-ID zurück.
5. Abfrage `GET /{seiten-id}?fields=instagram_business_account` liefert
   dann endlich die Instagram Business Account ID -- das, was letztes Mal
   leer zurückkam, meist weil Schritt 1 oder 2 noch nicht stand.
6. Diese ID + ein langlebiger Token gehören dann in den n8n-Node, der am
   Ende tatsächlich an die Graph API postet (in
   `docs/n8n-instagram-setup.md` als "posts as the right Instagram
   object... via the Meta Graph API" beschrieben, dort aber noch nicht
   als fertiger Node ausformuliert).

Das ist heute wahrscheinlich der Teil, der am ehesten noch Zeit kostet --
alles davor (Schritt 1-6 oben) kann heute Abend tatsächlich laufen und dir
einen fertigen, freigegebenen Kandidaten zeigen, auch wenn der letzte
Klick zum echten Posten noch nicht verdrahtet ist.
