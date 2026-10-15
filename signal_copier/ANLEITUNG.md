# Signal-Kopierer – Anleitung

Das Programm liest die Signale von Telegram-Gruppen und eröffnet sie auf
**deinen eigenen** MT5-Konten. Dazu gehören Einstieg, SL, TPs, „close half“,
Breakeven und „close all“. Jede Aktion und jede Ablehnung meldet dir dein
eigener Telegram-Bot.

Es ist **kein EA**, sondern ein eigenes Fenster neben MT5, das MT5 von außen
steuert. Von Haus aus handelt es **nur auf Demo-Konten**.

**Ein Profil = ein MT5-Konto.** Jedes Profil hat ein eigenes MT5, ein
eigenes Fenster, eigene Gruppen und ein eigenes Risiko. Es laufen so viele
gleichzeitig, wie der Rechner Speicher hat (pro MT5 etwa 300–500 MB).

---

## Was du brauchst

- Windows-Rechner, der läuft, während gehandelt wird.
- **MetaTrader 5**, pro Konto eine eigene Installation. Im Installer unter
  „Einstellungen“ einen anderen Zielordner wählen, z. B.
  `C:\MT5\puprime_demo`.
- **Python** von https://www.python.org/downloads/. Beim Installieren das
  Häkchen **„Add python.exe to PATH“** setzen.
- Dein **eigenes Telegram-Konto**, das Mitglied der Gruppen ist.

## Einrichtung (einmal)

### 1. Ordner entpacken
Zum Beispiel nach `C:\SignalCopier`. Alles Weitere liegt in
`signal_copier`.

### 2. Telegram-API-Zugang
https://my.telegram.org → **API development tools** → App anlegen.
Notier dir **api_id** und **api_hash**.

### 3. Benachrichtigungs-Bot
In Telegram an **@BotFather**: `/newbot`. Notier dir das **Token**.
Dann deinem neuen Bot irgendetwas schreiben, z. B. „hi“.

### 4. setup.bat
Doppelklick auf `signal_copier\setup.bat`.
- Es installiert die Pakete.
- Es öffnet `.env` in Notepad. Trag `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` und
  `TELEGRAM_BOT_TOKEN` ein, speichern.
- Doppelklick auf `chat_id.bat`, die Zahl als `TELEGRAM_NOTIFY_CHAT_ID` in
  `.env` eintragen, speichern.
- Danach legt `setup.bat` dein erstes Profil an (siehe unten).

## Neues Konto = neues Profil

1. MT5 für dieses Konto in einen **eigenen Ordner** installieren und einmal
   mit dem Konto anmelden. Algo Trading einschalten.
2. Doppelklick auf `signal_copier\neues_profil.bat`, dann einen Namen
   eingeben, z. B. `roboforex_cent`.
3. Notepad öffnet die Einstellungen. Eintragen:
   - `"terminal"`: Pfad zur `terminal64.exe` dieses MT5, mit **doppelten**
     Backslashes, z. B. `"C:\\MT5\\roboforex_cent\\terminal64.exe"`
   - `"login"`: die Kontonummer, z. B. `12345678`. Ist in MT5 ein anderes
     Konto angemeldet, startet er nicht.
   - `"channels"`: die Gruppen für dieses Konto
   - Risiko (siehe Tabelle)
4. Speichern. Auf dem Desktop liegen jetzt **„Copier roboforex_cent“** und
   **„Copier roboforex_cent Einstellungen“**.
5. Erster Start über „Copier roboforex_cent“: Er fragt im Fenster nach deiner
   Telefonnummer und dem Code, den Telegram dir schickt. Ab dann nicht mehr.

## Täglicher Betrieb

- Doppelklick auf **„Copier <name>“**, für jedes Profil einmal.
- Der Bot meldet `[name] copier started on <konto>`. Jede Meldung beginnt mit
  dem Profilnamen.
- **Stoppen:** Fenster schließen. Offene Trades bleiben in MT5, und nach dem
  Neustart findet er sie wieder.
- **Einstellungen ändern:** „Copier <name> Einstellungen“ öffnen, speichern,
  das Fenster des Profils schließen und neu starten.
- **Probelauf ohne Orders:** in einer Eingabeaufforderung
  `signal_copier\start.bat <name> --dry` aufrufen.
- In MT5 erkennst du seine Trades am Kommentar `sig:<Nachricht>:<Leg>`.

## Einstellungen eines Profils

| Feld | Bedeutung |
|---|---|
| `channels` | Gruppen, z. B. `["ICT CRT PREMIUM", "Andere Gruppe"]`. Jeder Name muss genau eine Gruppe treffen. |
| `terminal` | Pfad zur `terminal64.exe` dieses Kontos. `null` = das MT5, das gerade offen ist (nur bei einem einzigen Konto) |
| `login` | Kontonummer. `null` = keine Prüfung |
| `allow_live` | `false` = nur Demo. Erst auf `true`, wenn du ihn wochenlang auf Demo beobachtet hast. |
| `initial_balance` | leer = Kontostand beim ersten Start. Daran hängen die Verlustgrenzen. |
| `strategy` | `"signals"` = normale Signale (Einstieg, SL, TPs). `"layers"` = Zonen-Setups, je Setup 4 Positionen (TP1, TP2, TP3, Runner), z. B. VIP SIGNALS Inner Circle (siehe unten). |
| `trail_pips` | Nach „TP3 … trail your SL“ zieht er den SL des Runners so weit hinter dem Preis nach. 100 Pips Gold = 10 $. |
| `sizing` | `"risk_pct"` = Lotgröße aus dem Risiko in %. `"fixed_lot"` = jede Position mit genau `fixed_lot`, für Layering-Gruppen und kleine Konten. |
| `fixed_lot` | Lotgröße bei `"fixed_lot"`, z. B. `0.01`. Die Verlustgrenzen gelten trotzdem, sofern sie an sind. |
| `risk_per_position_pct` | Risiko **je TP-Position** in % (0,5 bei 2 TPs = insgesamt 1 %). Nur bei `"risk_pct"`. |
| `daily_loss_stop_pct` | Tagesverlust in % vom Startkapital → alles schließen, bis Mitternacht (Prag) Pause. `null` = aus. Vorlage: 30. |
| `overall_loss_stop_pct` | Gesamtverlust in % vom Startkapital → alles schließen, dauerhaft Schluss. `null` = aus. Vorlage: 50. Für eine Prop-Firm unter deren Grenze setzen (z. B. 4 / 8). |
| `max_entry_deviation_pips` | wie weit der Preis vom Einstieg weg sein darf (Gold 60 Pips = 6 $). Ist er weiter weg, wird das Signal ausgelassen. |
| `legs_without_tp` | Anzahl Positionen bei einem Signal ohne TP (die TPs kommen später) |
| `symbol_overrides` | falls dein Broker ein Symbol anders nennt, z. B. `{"XAUUSD": "GOLD.pro"}` |

## Layering-Gruppen (`"strategy": "layers"`)

Für Gruppen wie „VIP SIGNALS Inner Circle“. **Jedes nummerierte Setup ist ein
Layer** („3. GOLD SELL SETUP“ = Layer 3), und jeder Layer eröffnet **4
Positionen** sofort, alle mit dem SL der Gruppe:

| Position | TP |
|---|---|
| 1 | TP1 |
| 2 | TP2 |
| 3 | TP3 |
| 4 | keiner – der Runner |

Eine Antwort der Gruppe gilt **nur für das Setup, auf das sie antwortet**:

| Nachricht der Gruppe | Was der Kopierer macht |
|---|---|
| „Trade is shakey … closing 20% … BreakEven“ | Position 1 schließen, SL der übrigen auf Einstieg |
| „TP1 HIT … closing 20% … BreakEven“ | Position 1 ist durch ihren TP zu (sonst schließt er sie), SL der übrigen auf Einstieg |
| „TP2 HIT …“ | genauso mit Position 2 |
| „TP3 HIT … trail your SL 100 pips“ | Position 3 zu, ab jetzt SL des Runners `trail_pips` hinter dem Preis |
| „Close all now“ / „CUT LOSS NOW“ | als Antwort: dieses Setup schließen. Ohne Antwort: alle Setups der Gruppe |
| „HIT SL“ | nichts, der SL hat es erledigt |
| Setup nachträglich bearbeitet („UPDATED“) | SL und TPs auf die neuen Werte (ein SL auf Einstieg bleibt dort) |
| Leistungsberichte („London performance …“) | nichts |

Andere Anweisungen ohne Antwort macht er nicht – er rät nicht, welches Setup
gemeint ist. Für so eine Gruppe meist: `"sizing": "fixed_lot"`, `"fixed_lot": 0.01`.

**Dauerhafter Stopp aufheben:** Fenster schließen. In
`profiles\<name>\state_<konto>.json` den Wert `halt_reason` auf `""` setzen,
speichern, neu starten. Das ist absichtlich Handarbeit.

**Konto im MT5 gewechselt, während er läuft:** Er meldet „ACCOUNT CHANGED“ und
handelt nicht mehr, bis das richtige Konto wieder angemeldet ist.

## Was du nie weitergibst

- `.env`: deine Schlüssel.
- Den Ordner `profiles`: Darin liegen pro Profil `telegram.session`
  (**das ist dein Telegram-Login**), deine Konten und deine offenen Trades.

## Wenn etwas nicht geht

| Meldung | Lösung |
|---|---|
| `Python is missing` | Python installieren, Häkchen „Add to PATH“ |
| `no profile yet` / `several profiles` | `neues_profil.bat` ausführen bzw. über die Verknüpfung des Profils starten |
| `MT5 initialize failed` | Der Pfad in `terminal` stimmt nicht (doppelte Backslashes?) |
| `logged in to …, this profile is for …` | Im MT5 dieses Profils beim richtigen Konto anmelden |
| `is not a demo account` | Gewollt, siehe `allow_live` |
| `Algo Trading is switched off` | Den Knopf in diesem MT5 einschalten |
| `0 chats match` / `2 chats match` | Gruppenname in `channels` genauer schreiben |
| `no tradable broker symbol` | Symbol unter `symbol_overrides` eintragen |
| `ran too far from entry` | Das Signal kam zu spät, der Preis war schon weg. Das ist Absicht. |
