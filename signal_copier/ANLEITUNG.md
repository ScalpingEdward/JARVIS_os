# Signal-Kopierer – Anleitung

Das Programm liest die Signale einer Telegram-Gruppe und eröffnet sie
auf **deinem eigenen** MT5-Konto. Dazu gehören Einstieg, SL, TPs,
„close half“, Breakeven und „close all“. Jede Aktion und jede Ablehnung
meldet dir dein eigener Telegram-Bot.

Es ist **kein EA**. Es läuft als eigenes Fenster neben MT5 und steuert MT5 von
außen. Ein EA könnte die Gruppe gar nicht lesen.

Von Haus aus handelt es **nur auf einem Demo-Konto**. Auf einem Echtgeld-Konto
verweigert es den Start, bis du das selbst umschaltest (siehe unten).

---

## Was du brauchst

- Windows-Laptop, der läuft, während gehandelt wird. Schläft er, liest der
  Kopierer nichts.
- **MetaTrader 5** mit einem Konto bei deinem Broker, zuerst als Demo.
- **Python** von https://www.python.org/downloads/. Setz im Installer unbedingt
  das Häkchen bei **„Add python.exe to PATH“**.
- Dein **eigenes Telegram-Konto**, das Mitglied der Signal-Gruppe ist.

## Einrichtung (einmal, ca. 20 Minuten)

### 1. Ordner entpacken
Entpack die ZIP zum Beispiel nach `C:\SignalCopier`. Darin liegt der Ordner
`signal_copier`, und dort ist alles Weitere.

### 2. Telegram-API-Zugang holen
1. Öffne https://my.telegram.org und melde dich mit deiner Telefonnummer an.
2. Klick auf **API development tools** und leg eine App an. Name und
   Kurzname sind egal.
3. Notier dir **api_id** (eine Zahl) und **api_hash** (eine lange
   Buchstabenfolge).

### 3. Eigenen Benachrichtigungs-Bot anlegen
1. Schreib in Telegram an **@BotFather**: `/newbot`, dann Name und
   Benutzername (muss auf `bot` enden).
2. Er antwortet mit einem **Token** (`123456:ABC...`). Notier es dir.
3. Öffne deinen neuen Bot und schick ihm irgendeine Nachricht, z. B. „hi“.

### 4. setup.bat starten
Doppelklick auf `signal_copier\setup.bat`.
- Es installiert die Python-Pakete.
- Es öffnet Notepad mit der Datei `.env`. Trag dort ein:
  - `TELEGRAM_API_ID` und `TELEGRAM_API_HASH` aus Schritt 2
  - `TELEGRAM_CHANNEL`: ein Teil des Gruppennamens, wie Telegram ihn zeigt
  - `TELEGRAM_BOT_TOKEN` aus Schritt 3
  - `TELEGRAM_NOTIFY_CHAT_ID` bleibt vorerst leer, das kommt in Schritt 5
- Speichern, Notepad schließen.
- Dann folgt der Telegram-Login: Telefonnummer (mit `+49…` bzw. `+420…`),
  den Code, den Telegram dir schickt, und dein 2FA-Passwort, falls gesetzt.
- Am Ende stehen die letzten Nachrichten der Gruppe auf dem Bildschirm, mit
  `->` darunter, wie das Programm sie versteht. Dann passt alles.

### 5. Chat-ID eintragen
Doppelklick auf `signal_copier\chat_id.bat`. Es zeigt eine Zeile
`TELEGRAM_NOTIFY_CHAT_ID=...`. Trag die Zahl in `.env` ein und speichere.

### 6. MT5 vorbereiten
- MT5 öffnen und beim **Demo-Konto** anmelden.
- Oben in der Leiste **„Algo Trading“** einschalten (grün).
- Unter Extras → Optionen → Expert Advisors muss „Algo Trading erlauben“ an sein.

## Täglicher Betrieb

1. MT5 öffnen, Algo Trading an.
2. Doppelklick auf `signal_copier\start.bat`.
3. Dein Bot schreibt dir „copier started …“. Ab jetzt läuft er.

**Stoppen:** Fenster schließen oder Strg+C. Offene Trades bleiben in MT5. Nach
einem Neustart findet der Kopierer sie wieder.

**Nur ein Fenster:** Zwei gleichzeitig gehen nicht, weil beide denselben
Telegram-Login benutzen.

**Probelauf ohne Orders:** `start.bat --dry` in einer Eingabeaufforderung im
Ordner `signal_copier` aufrufen. Dann meldet er nur, was er tun würde.

In MT5 erkennst du seine Trades am Kommentar `sig:<Nachrichtennummer>:<Leg>`.

## Einstellungen – `config.json`

| Feld | Bedeutung |
|---|---|
| `channels` | Name(n) der Gruppe(n) |
| `allow_live` | `false` = nur Demo. Erst auf `true` stellen, wenn du ihn wochenlang auf Demo beobachtet hast. |
| `initial_balance` | leer = Kontostand beim ersten Start **dieses Kontos**. Daran hängen die Verlustgrenzen. Ein Wert hier gilt für jedes Konto – bei mehreren Konten leer lassen. |
| `risk_per_position_pct` | Risiko **je TP-Position** in % (0,5 = bei 2 TPs insgesamt 1 %) |
| `daily_loss_stop_pct` | Tagesverlust in % → alles schließen, bis Mitternacht (Prag) keine neuen Trades |
| `overall_loss_stop_pct` | Gesamtverlust in % → alles schließen, dauerhaft Schluss |
| `max_entry_deviation_pips` | wie weit der Preis schon vom Einstieg weg sein darf (Gold: 60 Pips = 6 $). Ist er weiter weg, wird das Signal ausgelassen. |
| `legs_without_tp` | wie viele Positionen bei einem Signal ohne TP (TPs kommen später) |

Nach einer Änderung den Kopierer neu starten.

## Konto wechseln

Der Kopierer handelt auf dem Konto, das gerade in MT5 angemeldet ist. Jedes
Konto bekommt eine eigene Datei `state_<Kontonummer>_<Server>.json`. Darin
stehen das Startkapital, die Verlustsperre und welche Trades zu welchem Signal
gehören. Wechselst du zurück, ist der alte Stand wieder da.

So wechselst du:
1. Kopierer schließen.
2. In MT5 beim anderen Konto anmelden.
3. Kopierer starten. Die Startmeldung nennt das Konto.

Wechselst du in MT5 das Konto, **während** der Kopierer läuft, meldet er
„ACCOUNT CHANGED“. Er handelt dann nichts mehr und prüft keine Verlustgrenze,
bis MT5 wieder auf dem alten Konto ist oder du ihn neu startest. Sonst würde
er das neue Konto mit den Grenzen des alten handeln.

**Dauerhafter Stopp aufheben:** Kopierer schließen, die Datei `state_<Konto>.json` mit
Notepad öffnen, `halt_reason` auf `""` setzen, speichern, neu starten. Das
ist absichtlich Handarbeit.

## Was du nie weitergibst

- `.env`: deine Schlüssel.
- `copier.session`: **das ist dein Telegram-Login.** Wer die Datei hat, ist
  in Telegram du.
- `state_*.json`: deine Konten und offenen Trades.

## Wenn etwas nicht geht

| Meldung | Lösung |
|---|---|
| `Python is missing` | Python installieren, Häkchen „Add to PATH“ |
| `MT5 initialize failed` | MT5 ist nicht offen, oder es sind mehrere MT5 installiert. Nur eines offen haben. |
| `is not a demo account` | Gewollt, siehe `allow_live` |
| `Algo Trading is switched off` | Den Knopf in MT5 einschalten |
| `0 chats match` / `2 chats match` | `TELEGRAM_CHANNEL` bzw. `channels` in `config.json` genauer schreiben |
| `no tradable broker symbol` | Dein Broker nennt das Symbol anders. In `config.json` unter `symbol_overrides` eintragen, z. B. `{"XAUUSD": "GOLD.pro"}` |
| `ran too far from entry` | Das Signal kam zu spät, der Preis war schon weg. Das ist Absicht. |
