# Futures-Bot: welche Daten welches Signal liefern

Stand 2026-10-13. Entscheidungsgrundlage, bevor etwas gebaut oder gekauft
wird. **Alle Preise sind Groessenordnungen aus oeffentlichen Seiten und
Vergleichsartikeln -- vor dem Abschluss beim Anbieter selbst nachsehen.**
Gebuehren aendern sich, und Broker schlagen eigene Pauschalen drauf.

## Der Kern in einem Satz

Was DeepCharts, Bookmap und aehnliche Plattformen teuer macht, ist nicht
ihre Software, sondern die **Datenlizenzen**. Ein Nachbau spart die
Lizenzen nicht. Er spart die Abo-Marge -- und bringt dafuer Arbeit.

Und: ein Bot braucht keine Bilder. Eine Heatmap ist eine Darstellung fuer
menschliche Augen. Derselbe Datenstrom liefert einem Algorithmus direkt
Zahlen. Wer nur den Bot bauen will, braucht die Darstellung nie.

## Signal fuer Signal

| Signal | Woraus es entsteht | Datenart | Groessenordnung |
|---|---|---|---|
| Deep DOM, Liquiditaets-Heatmap | ruhende Groesse je Preis und Zeit | CME Markttiefe (L2), echte Heatmap braucht MBO | ~45-48 $/Monat nicht-professionell, CME-Buendel |
| Aggressive Trades, Delta | Trades, klassifiziert nach "am Bid" / "am Ask" | dieselbe L2/Tick-Quelle | im Obigen enthalten |
| Absorption | grosse ruhende Groesse wird mehrfach getroffen, Preis weicht nicht | dieselbe Quelle, nur andere Rechnung | 0 zusaetzlich |
| Imbalance / Footprint | Volumen je Preisniveau, Kauf gegen Verkauf | dieselbe Quelle | 0 zusaetzlich |
| Options-Whale-Trades ("Bubbles") | gemeldete Optionsabschluesse | **OPRA** (US-Aktien/Index-Optionen) | ~99 $/Monat verzoegert, ~249 $/Monat in Echtzeit |
| Gamma-Exposure (GEX) | Optionskette + Open Interest + Greeks, selbst gerechnet | OPRA oder Tagesendstaende | Tagesendstand reicht oft |

**Wichtig zur Unterscheidung:** Orderflow fuer ES/NQ kommt von der **CME**.
Options-Flow und Gamma auf SPX/SPY kommen von **OPRA** -- ein anderer
Markt, eine andere Lizenz. Das sind zwei Abos, nicht eins.

## Anbieter

| Anbieter | Wofuer | Anmerkung |
|---|---|---|
| **Rithmic** | CME L2, sehr niedrige Latenz, eigene API | Broker verlangt Verbindungsgebuehr (~25 $/Monat) plus Routing je Kontrakt |
| **CQG** | dasselbe, etwas teurer ueber NinjaTrader | NinjaTrader berechnet ~0,25 $ mehr je Kontrakt beim Routing |
| **Databento** | CME **Market-by-Order**, historisch und live | nutzungsbasiert, Lizenz ab ~32,65 $/Monat nicht-professionell. Die Wahl, wenn echte Heatmap oder Backtests auf Orderbuchebene gebraucht werden |
| **Polygon / Massive** | OPRA-Optionsdaten | Preise widerspruechlich, teils "custom" -- anfragen |
| **DXFeed** | breite Abdeckung, Unternehmenskundschaft | fuer ein Einzelprojekt meist zu gross dimensioniert |

## NinjaTrader oder Tradovate

Beide gehoeren heute zur selben Gruppe, und die **Marktdatengebuehren sind
identisch** -- die Wahl entscheidet nicht ueber die Kosten, sondern ueber
den Weg, auf dem der Bot handelt.

- **NinjaTrader**: Automatisierung in C# (NinjaScript), laeuft in der
  Plattform. Order Flow+ als kostenpflichtiges Zusatzmodul (~59 $/Monat).
  Fuer Strategien, die eng am Chart haengen, der kuerzere Weg.
- **Tradovate**: Web und REST/WebSocket-API, kein lokales Programm noetig.
  Fuer einen Bot, der ohnehin als eigener Dienst laeuft -- so wie AURON --
  der sauberere Weg: keine Plattform, die offen sein muss.

Fuer AURON spricht mehr fuer **Tradovate**, weil der Bot dann nicht an ein
laufendes Windows-Programm gebunden ist. Das ist dieselbe Ueberlegung, die
schon beim Lightroom-Weg den Ausschlag gab: was auf einen offenen Rechner
wartet, faellt aus, sobald der Rechner aus ist.

## Was ich empfehle, in dieser Reihenfolge

1. **Ein Markt, eine Quelle, ein Signal.** CME-L2 fuer den Kontrakt, den
   Brano wirklich handelt. Daraus Delta und Imbalance rechnen. Das kostet
   rund 16-17 $/Monat und beantwortet die Frage, ob die Signale ueberhaupt
   tragen.
2. **Erst danach** Market-by-Order (Databento), falls echte Absorption auf
   Orderebene gebraucht wird.
3. **Optionen und Gamma zuletzt.** Sie sind die teuerste Zutat und helfen
   nur, wenn die Strategie sie wirklich benutzt -- nicht, weil sie auf
   Screenshots gut aussehen.
4. **Nichts nachbauen, was nur anzeigt.** Keine Heatmap, solange kein
   Mensch sie ansieht.

## Was ausdruecklich nicht hilft

REA (Reverse Engineer Anything) und aehnliche Werkzeuge zerlegen
kompilierte Programme. Sie wuerden zeigen, wie DeepCharts seine Blasen
zeichnet -- nicht, woher die Trades kommen. Der Engpass ist die Lizenz,
nicht das Wissen. Dazu kaeme ein Verstoss gegen die Nutzungsbedingungen,
den Brano ausdruecklich nicht will.
