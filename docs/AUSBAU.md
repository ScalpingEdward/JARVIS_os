# AURON – Ausbau (Stand 2026-10-19)

Eine Liste statt fünf. Quelle: CLAUDE.md, docs/ROADMAP.md, docs/signal-copier-business.md,
docs/futures-bot-datenquellen.md und Brano's Ansagen. Reihenfolge = Bau-Reihenfolge.
`[ ]` offen · `[~]` in Arbeit · `[x]` erledigt · **Gerüst** = Struktur steht, Anbindung später.

## 1. Dashboard-Karten individualisieren  `[x]` (2026-10-19)
- [x] Anordnung in der Datenbank (`app_settings` `dashboard.layout`), nicht im Browser – gilt überall
- [x] Bearbeiten-Modus: Karte ein/aus, links/rechts, Reihenfolge, „＋ Karte“ aus dem Katalog
- [x] AURON-Befehl („Zeig mir Gold rechts oben“) – AURON fragt vorher
- [x] Neue Karten: Kurs (MT5-Symbol), Kopierer/Bots mit Pause/Weiter, Notizen/To-do

## 2. AURON baut mit Claude Code – mit Erlaubnis  `[ ]`
Ziel: Im Dashboard über eine Strategie reden (z. B. Opening Range Breakout), daraus entsteht
ein Bot für MT5, getestet an echten Kursen. AURON gibt keine Empfehlungen – er analysiert Daten.

Plan (vor dem Bau mit Brano abstimmen):
1. **Auftrag**: AURON-Tool `code_task(beschreibung)` legt einen Auftrag an – Status „wartet auf
   Erlaubnis“. Nichts läuft ohne Brano's Klick (Dashboard-Karte oder Telegram-Knopf).
2. **Ausführung**: ein kleiner Runner **auf Windows** (nicht im Docker – dort gibt es weder MT5 noch
   MetaEditor) holt freigegebene Aufträge und startet `claude -p` in einem eigenen Arbeitsordner
   `C:\Users\brani\AURON-Werkstatt\<auftrag>` – nur dieser Ordner, keine anderen Dateien.
3. **EA bauen**: Claude Code schreibt MQL5, kompiliert mit MetaEditor (`metaeditor64.exe /compile`),
   Fehler gehen zurück an Claude Code, bis es baut.
4. **Testen an echten Kursen**: MT5-Strategietester per Konfigurationsdatei (`terminal64.exe
   /config:`), Bericht wird eingelesen – Gewinn, Drawdown, Trades. Ehrliche Zahlen, nicht
   erfunden (siehe Backtesting-Lab, 2026-10-18). Läuft auf einem **eigenen Terminal**, nie auf dem
   des Kopierers (der Insider-Lauf am 2026-10-17 hat ihn schon einmal gestört).
5. **Live**: nur auf Brano's ausdrückliche Freigabe, erst Demo. Später auf dem VPS.
- Offene Frage an Brano: Claude Code mit seinem Abo oder per API-Key abrechnen?

## 3. Trading
- [ ] MT5-Demo anschließen: `/v1/accounts` zeigt denselben Kontostand wie das Terminal
- [ ] Kopierer: Signal-Verspätung messen (Nachrichtenzeit vs. Empfang vs. Kurs) bevor die Pip-Grenze weiter wächst
- [ ] Backtesting-Lab mit echten MT5-Kursen statt Verweigerung
- [ ] Insider-Shorts nur mit Marktfilter testen (S&P unter 200-Tage-Schnitt)
- [ ] Strategie aus der Beobachtungsliste (Einstieg, Haltedauer, Absicherung) – aus Daten
- [ ] **Gerüst**: eigenes Insider-Konto mit Signal-Feed (Anbindung später, VPS)
- [ ] **Gerüst**: Gold- + Bitcoin-Kopierer auf einem Konto (Anbindung später, VPS)
- Später/extern: Futures-Bot NinjaTrader (erst wenn Instagram läuft), Signal-Kopierer als Produkt

## 4. Instagram
- [x] Kennzeichen-Engine: Nummernschilder beim Ingest unkenntlich machen
- [x] Tagesregel + Duplikat-Filter (ein Shooting → ein Post, fast gleiche Bilder raus)
- [x] Pillar-Feld (Trading/Portrait/Gym/Essen/Travel) im Datenmodell
- [x] HEIC → JPG beim Ingest (pillow-heif), Live-Photo-MOVs (< 3 s, gleicher Name) nicht hochladen
- [x] Captions kurz und direkt (max. 160 Zeichen vor den Hashtags, geprüft) – Brano 2026-10-19
- Wartet auf Daten/Dritte: Analyse auf Reichweite (nach 4 Wochen Insights), Reels-Vollautomatik
  (Instagram Audio API, braucht „Instagram API with Facebook Login“)

## 5. Technik
- [ ] Secrets rotieren – **Brano** erneuert die Schlüssel in den Konsolen, AURON trägt sie in `.env` ein
- [x] n8n-SQLite 1,5 GB („Database connection timed out“) verkleinern
- [x] Tests schreiben `backend/data/workflows.json` um – abstellen
- [x] 7 alte rote Testdateien (Live-Order Telegram/MT5, End-to-End, Provider) reparieren oder ehrlich markieren
- [x] Profit-Faktor `999.0` als Platzhalter ersetzen (None, wenn es keinen Verlust gab)
- [ ] Drive-Ingest-Trigger 20 min → wieder täglich, wenn Instagram live geht

## 6. Produkt (vorbereiten, Verkauf erst nach einigen Monaten Eigennutzung)
- [ ] Website: Pakete Signal 29 / Trader 59 / Business 99 €, Insta-Manager-Add-on, 30 Tage Test,
      jährlich 2 Monate geschenkt, Founder Edition 690 € (100 Plätze), Einrichtung durch uns nach Aufwand
- [ ] Website: Systemvoraussetzungen (Docker, VPS empfohlen, RAM, Speicher)
- [ ] AURON als Chatbot auf der Website: Wünsche aufnehmen, Aufwand schätzen, Anfrage an Brano
- [ ] Lizenz/Module je Abo freischalten (Installationspaket, Add-ons zuschaltbar)
- [ ] iOS- und Android-App: das Dashboard mit Planet, quer gehalten wie am Bildschirm

## Später (ROADMAP.md)
E-Mail/Kalender/Dokumente, Chart-Analyse per Bild, Smart Home, tragbares verschlüsseltes
Installationspaket, Website veröffentlichen (Impressum/Datenschutz fertig machen).
