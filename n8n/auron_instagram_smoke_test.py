#!/usr/bin/env python3
"""
AURON Instagram - Trockentest vor dem echten Lauf
====================================================
Testet die komplette Kette EINMAL durch, mit einem winzigen echten
Testbild (ein 1x1-Pixel PNG als Platzhalter) -- nicht um ein echtes Foto
zu bewerten, sondern um zu beweisen, dass jeder Schritt der Kette
tatsaechlich erreichbar ist, BEVOR die ersten echten Fotos aus Google
Drive kommen.

Prueft in dieser Reihenfolge, bricht sofort ab und sagt klar, WAS fehlt:
  1. Ist der AURON Server ueberhaupt erreichbar?
  2. Ist ANTHROPIC_API_KEY gesetzt? (sonst schlaegt Schritt 3 erwartungsgemaess fehl)
  3. Funktioniert die echte Bildanalyse (Vision)?
  4. Funktioniert die Kuration?
  5. Kann ein Entwurf zu einem echten Kandidaten werden (Caption-Erstellung)?
  6. Steht der Kandidat korrekt "zur Freigabe" -- NICHT automatisch veroeffentlicht.

Aufruf:
    python3 auron_instagram_smoke_test.py --base-url http://localhost:8000
"""

import argparse
import base64
import sys

import httpx

# Ein echtes, gueltiges 1x1 rotes PNG-Pixel -- klein genug fuer eine
# Kommandozeile, aber ein echtes Bild, kein Fake-Text.
TINY_RED_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA"
    "hKmMIQAAAABJRU5ErkJggg=="
)


def step(n: int, title: str) -> None:
    print(f"\n=== Schritt {n}: {title} ===")


def fail(message: str) -> None:
    print(f"\n[FEHLGESCHLAGEN] {message}")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--operator-token", default=None, help="X-Auron-Operator-Token, falls konfiguriert")
    args = parser.parse_args()

    headers = {}
    if args.operator_token:
        headers["X-Auron-Operator-Token"] = args.operator_token

    client = httpx.Client(base_url=args.base_url, timeout=60.0, headers=headers)

    step(1, "Ist AURON erreichbar?")
    try:
        resp = client.get("/v1/instagram/dashboard")
        resp.raise_for_status()
        print(f"  OK -- AURON antwortet. Status {resp.status_code}")
    except httpx.HTTPError as exc:
        fail(f"AURON ist unter {args.base_url} nicht erreichbar: {exc}")

    step(2, "Bildanalyse + Ingest (echter Anthropic-Vision-Aufruf)")
    resp = client.post("/v1/instagram/media-pool/analyze-and-ingest", json={
        "items": [{
            "media_ref": "smoke-test-pixel",
            "media_type": "image",
            "image_base64": TINY_RED_PNG_BASE64,
            "image_media_type": "image/png",
        }]
    })
    if resp.status_code != 200:
        fail(f"Status {resp.status_code}: {resp.text[:300]}")
    result = resp.json()["results"][0]
    if not result["success"]:
        error = result.get("error", "")
        if "ANTHROPIC_API_KEY" in error:
            fail(
                "ANTHROPIC_API_KEY ist nicht gesetzt. In der .env-Datei auf dem "
                "Server setzen, dann Server neu starten. Ohne das laeuft heute "
                "kein einziger Analyse-Schritt."
            )
        fail(f"Analyse fehlgeschlagen: {error}")
    print(f"  OK -- Thema erkannt: '{result['theme']}', Aesthetik-Score: {result['aesthetic_score']}")

    step(3, "Kuration anstossen")
    resp = client.post("/v1/instagram/curate")
    if resp.status_code != 200:
        fail(f"Status {resp.status_code}: {resp.text[:300]}")
    drafts = resp.json()["items"]
    if not drafts:
        fail("Kuration hat keinen Entwurf erzeugt -- unerwartet bei einem frisch eingespeisten Bild.")
    draft_id = drafts[0]["id"]
    print(f"  OK -- Entwurf erzeugt: {draft_id}")

    step(4, "Entwurf zu echtem Kandidaten machen (Caption via Anthropic)")
    resp = client.post(f"/v1/instagram/curate/drafts/{draft_id}/finalize")
    if resp.status_code != 200:
        fail(f"Status {resp.status_code}: {resp.text[:300]}")
    candidate = resp.json()
    print(f"  OK -- Kandidat {candidate['id']}, Status: {candidate['status']}")
    print(f"  Caption: {candidate['caption_draft'][:150]}")

    step(5, "Bestaetigen: Kandidat wartet auf Freigabe, ist NICHT veroeffentlicht")
    if candidate["status"] not in ("proposed", "moderation_rejected"):
        fail(f"Unerwarteter Status '{candidate['status']}' -- sollte auf Freigabe warten.")
    print(f"  OK -- Status ist korrekt '{candidate['status']}'. Nichts wurde veroeffentlicht.")

    print("\n" + "=" * 60)
    print("ALLE SCHRITTE ERFOLGREICH. Die Kette funktioniert Ende-zu-Ende.")
    print("Der Testkandidat wartet jetzt auf Freigabe/Ablehnung wie jeder echte Post.")
    print(f"  Kandidat-ID: {candidate['id']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
