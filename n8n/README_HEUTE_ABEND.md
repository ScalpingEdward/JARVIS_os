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

**Korrektur gegenüber der ursprünglichen Version dieser Anleitung:** Meta
bietet inzwischen einen eigenen, leichteren Weg für genau diesen Fall --
ein Business/Creator-Konto ohne verknüpfte Facebook-Seite. Keine Seite
nötig, kein Page-ID-Umweg.

1. developers.facebook.com -> App "JARVIS INST" -> Produkt "Instagram"
   hinzufügen -> Variante **"API setup with Instagram login"** wählen
   (nicht "with Facebook login").
2. Dort unter "Business login settings": eine Redirect-URI eintragen
   (z.B. `https://localhost/auron-callback`, muss nicht real erreichbar
   sein). Instagram App ID + Instagram App Secret dort notieren -- andere
   Werte als die normale Facebook App ID.
3. Im Browser öffnen (echte App ID einsetzen):
   `https://api.instagram.com/oauth/authorize?client_id=DEINE_IG_APP_ID&redirect_uri=https://localhost/auron-callback&scope=instagram_business_basic,instagram_business_content_publish,instagram_business_manage_comments&response_type=code`
   Einloggen, bestätigen.
4. Browser leitet weiter, auch wenn die Seite nicht existiert -- der Code
   steht in der Adresszeile hinter `?code=`.
5. Lokal im Terminal (App Secret nie in den Chat einfügen):
   ```
   curl -X POST https://api.instagram.com/oauth/access_token \
     -F client_id=DEINE_IG_APP_ID -F client_secret=DEIN_IG_APP_SECRET \
     -F grant_type=authorization_code \
     -F redirect_uri=https://localhost/auron-callback -F code=DEIN_CODE
   ```
   Antwort enthält `access_token` und `user_id` -- die `user_id` IST
   direkt die Instagram Business Account ID, kein Page-Lookup nötig.
6. Auf einen langlebigen Token (60 Tage) umtauschen:
   ```
   curl -X GET "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=DEIN_IG_APP_SECRET&access_token=DEIN_KURZLEBIGER_TOKEN"
   ```
7. Langlebiger Token + user_id in den n8n-Node eintragen, der tatsächlich
   postet. Vor Ablauf per `GET /refresh_access_token?grant_type=ig_refresh_token`
   erneuerbar, ohne neu einzuloggen -- aber nur wenn der Token noch mindestens
   24h alt und nicht abgelaufen ist; danach hilft nur der komplette Neustart
   ab Schritt 3.

