# n8n Container — Baseline-Dokumentation (Stand 2026-09-16)

Aufgenommen aus `docker inspect n8n` **vor** jeder Aenderung. Dieser Stand ist
die Referenz, gegen die jede Migration (z. B. nach docker compose) geprueft wird.

## Wichtig
- n8n laeuft **nicht** ueber `docker compose`, sondern als eigenstaendiger
  `docker run`-Container.
- Das Volume **`n8n_data`** enthaelt alle Workflows und Credentials
  (`database.sqlite`). Es darf unter keinen Umstaenden geloescht oder
  ueberschrieben werden. Mountpoint (in der Docker-VM):
  `/var/lib/docker/volumes/n8n_data/_data`, angelegt 2026-06-08.

## Ist-Zustand

| Feld | Wert |
|---|---|
| Name | `n8n` |
| Image | `n8nio/n8n` (laufende Version im Container: **2.13.2**, Node 24.13.1) |
| Container erstellt | 2026-09-13T17:28:03Z |
| Restart-Policy | `unless-stopped` |
| Memory-Limit | keines (`Memory=0`) |
| Netzwerk | `bridge` (Default) — **nicht** an `jarvis_shared` angeschlossen |
| Port-Mapping | `0.0.0.0:5678 -> 5678/tcp` |
| Entrypoint / Cmd | `tini -- /docker-entrypoint.sh` / kein CMD (Image-Default) |
| WorkingDir / User | `/home/node` / `node` |

### Mounts
| Typ | Quelle | Ziel | RW |
|---|---|---|---|
| volume | `n8n_data` | `/home/node/.n8n` | rw |
| bind | `C:\JARVIS_Images` | `/data/images` | rw |

### Environment (explizit gesetzt, ohne Image-Defaults)
```
AURON_IG_ACCESS_TOKEN=<REDACTED — Wert steckt im laufenden Container, gehoert in .env>
AURON_IG_USER_ID=27471261452547997
N8N_RUNNERS_HEARTBEAT_INTERVAL=120
N8N_RUNNERS_MAX_OLD_SPACE_SIZE=2048
N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```
Vom Image gesetzt (nicht beim Start uebergeben): `NODE_VERSION`, `NODE_PATH`,
`NODE_ENV=production`, `N8N_RELEASE_TYPE=stable`, `NPM_CONFIG_UPDATE_NOTIFIER`,
`PATH`, `SHELL`.

Es sind **keine** Pruning-Variablen gesetzt — daher waechst die Execution-History
unbegrenzt.

## Rekonstruierter urspruenglicher Startbefehl
```powershell
docker run -d `
  --name n8n `
  --restart unless-stopped `
  -p 5678:5678 `
  -v n8n_data:/home/node/.n8n `
  -v C:\JARVIS_Images:/data/images `
  -e AURON_IG_ACCESS_TOKEN=<token> `
  -e AURON_IG_USER_ID=27471261452547997 `
  -e N8N_RUNNERS_HEARTBEAT_INTERVAL=120 `
  -e N8N_RUNNERS_MAX_OLD_SPACE_SIZE=2048 `
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false `
  n8nio/n8n
```

## Groesse des Datenverzeichnisses (`/home/node/.n8n`, 2026-09-16)
```
database.sqlite        4.832.235.520 B  (~4,50 GiB / 4,83 GB)
database.sqlite-wal      378.187.192 B  (~361 MiB)
database.sqlite-shm           32.768 B
n8nEventLog-1.log         21.518.438 B
n8nEventLog-3.log         21.496.663 B
n8nEventLog-2.log             25.055 B
n8nEventLog.log                5.011 B
config                            56 B
```
Gesamt ca. **5,0 GB**. Ursache: vollstaendige Execution-History inklusive
Base64-Medien, da kein Pruning aktiv ist. Das ist die wahrscheinliche Ursache der
Abstuerze auf der 3,5-GB-VM — nicht zu wenig RAM.

## Abweichung zur Dokumentation
`docs/n8n-instagram-setup.md` / Master Plan gehen davon aus, dass n8n im Netzwerk
`jarvis_shared` haengt. Tatsaechlich haengt der Container nur am Default-`bridge`.
Beim Umzug in docker compose ist das zu beruecksichtigen.

---

# Migration nach docker compose (2026-09-16, durchgefuehrt)

n8n laeuft jetzt als Service `n8n` im Compose-Projekt `jarvis_os`.

## Was sich geaendert hat
- Image auf **`n8nio/n8n:2.13.2`** gepinnt (vorher `n8nio/n8n` ohne Tag).
- Pruning-Variablen gesetzt (siehe `docker-compose.yml`) — verhindert erneutes
  Zuwachsen der Execution-History.
- `mem_limit: 3g`. Bewusst nicht 2g: `N8N_RUNNERS_MAX_OLD_SPACE_SIZE=2048`
  erlaubt allein schon 2 GB Heap, ein 2g-Limit haette OOM-Kills provoziert.
- Netze: `jarvis_shared` **und** `bridge` (vorher nur `bridge`).

## Wichtig: das Netz `bridge` laesst sich nicht in Compose eintragen
Compose setzt fuer jeden Service automatisch einen netzwerk-scoped Alias, und den
akzeptiert nur ein user-defined Netz. Ein Eintrag von `bridge` als externes Netz
schlaegt beim Start fehl:
`invalid config for network bridge: network-scoped aliases are only supported for user-defined networks`

Daher nach jedem Neuanlegen des Containers zusaetzlich:
```powershell
docker network connect bridge n8n
```
Das ist nur noetig, wenn der Container **neu erstellt** wird (`compose up` nach
Config-Aenderung), nicht bei `docker restart n8n`. Netzwerkbereinigung ist eine
eigene Baustelle — sobald nichts mehr n8n ueber die Bridge-IP anspricht, kann
`bridge` entfallen und der Schritt mit ihm.

## Volume-Sicherheit
`n8n_data` ist in `docker-compose.yml` als `external: true` deklariert. Ohne das
wuerde Compose ein leeres `jarvis_os_n8n_data` anlegen und alle Workflows und
Credentials waeren scheinbar verloren. **Nie entfernen.**

## Secrets
`AURON_IG_ACCESS_TOKEN` / `AURON_IG_USER_ID` existierten nur in der Env des alten
Containers und waren in keiner Datei gesichert. Sie stehen jetzt in `.env`
(gitignored) und werden von Compose dorther gelesen. Der Token ist damit weiterhin
rotationsbeduerftig.

## Backup vor der Migration
`C:\JARVIS_Backups\n8n_data_2026-09-16.tar` (6,10 GB), `PRAGMA integrity_check` = ok.
Compose-Stand vorher: `C:\JARVIS_Backups\docker-compose.yml.bak-2026-09-16`.

## Offen: VACUUM
Die DB besteht zu 81 % aus freien Seiten (`freelist_count` 949.506 von
`page_count` 1.179.745 = 3,89 GB) bei nur 38 Executions. Pruning aendert daran
nichts, nur `VACUUM` gibt den Platz zurueck. Platz dafuer ist reichlich da
(Docker-VM: 943 GB frei). Eigener Schritt, eigene Fehlersuche.

## VACUUM durchgefuehrt (2026-09-16)
Bei gestopptem Container, `PRAGMA wal_checkpoint(TRUNCATE); VACUUM;`:

| | vorher | nachher |
|---|---|---|
| `database.sqlite` | 4.832.235.520 B (4,83 GB) | 943.198.208 B (943 MB) |
| `database.sqlite-wal` | 378.187.192 B | 0 B |
| Volume gesamt | 5,7 GB | 1,7 GB |

3,89 GB freigegeben, exakt der vorhergesagte `freelist`-Betrag.
`PRAGMA integrity_check` danach: ok. Workflows, Credentials und
Aktivierungsstatus unveraendert.

**Wichtig:** Laeuft VACUUM aus einem Root-Container, gehoeren neu angelegte
Dateien danach `root`. n8n laeuft als `node` (uid 1000) und startet dann nicht
mehr. Deshalb im selben Durchgang `chown -R 1000:1000` auf das Volume.

Offen geblieben: `n8nEventLog-1.log` und `-3.log` mit je ~21,5 MB. n8n rotiert
diese Dateien nicht selbst weg.
