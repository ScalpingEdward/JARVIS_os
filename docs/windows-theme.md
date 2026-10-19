# AURON als Windows-Theme (3 Monitore)

Gebaut mit `python tools/windows_theme.py` (Frontend muss auf :8080 laufen). Ergebnis in `windows-theme/`
(nicht im Repo, wird neu erzeugt):

- `AURON.deskthemepack`: Doppelklick installiert es. Setzt ein Bild über alle drei Monitore
  (Modus „Strecken über Bildschirme“), Dunkelmodus und AURON-Cyan als Akzentfarbe.
  - Unten links (Hauptmonitor): Lounge mit Planet
  - Unten rechts: „Über der Erde“
  - Oben: „Orbit“
- `auron-main.jpg`, `auron-right.jpg`, `auron-top.jpg`: dieselben Bilder einzeln, falls du sie pro Monitor
  selbst setzen willst (Rechtsklick in Einstellungen → Personalisierung → Hintergrund → „Für Monitor N festlegen“).

Ändert sich die Anordnung der Monitore, passt das gestreckte Bild nicht mehr. Dann `SHOTS` im Skript anpassen.

## Live-Desktop auf dem Hauptmonitor (Lively Wallpaper)

Damit wird das Dashboard selbst zum Hintergrund: Uhr und Wetter oben, darunter der Planet groß auf dem Podest,
alle Karten unten in einer Reihe.

1. **Lively Wallpaper** aus dem Microsoft Store installieren. Es ist kostenlos und Open Source.
2. Lively → „+“ → URL `http://127.0.0.1:8080/?desk` → als Hintergrund für **Monitor 2 (Hauptmonitor)** setzen.
3. Lively → Einstellungen → Hintergrund → **Eingabe: Maus**, damit Klicks auf dem Desktop bei den Karten ankommen.
4. Optional: „Bei Vollbild-Apps pausieren“ anlassen, das spart Leistung beim Spielen und Arbeiten.

Bedienung:
- Karte **ziehen** (halten und bewegen) verschiebt sie. Die Position wird gespeichert.
- **Kurz klicken** öffnet die Karte wie im Dashboard.
- **Doppelklick auf eine freie Stelle** holt alle Karten zurück in die Reihe.

Der Hintergrund spricht nie. Durchsagen kommen weiter nur aus dem AURON-Fenster, damit nichts doppelt kommt.
