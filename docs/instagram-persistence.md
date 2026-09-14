# Instagram persistence and existing-container upgrade

## Cause and corrected behavior

Pool items, curated drafts and candidates already use SQLAlchemy tables.
The shipped Compose file supplied `DATABASE_URL`, but `Settings` only read
`JARVIS_DATABASE_URL`. Consequently, the API could silently use its native
SQLite fallback, `./jarvis.db` (`/app/jarvis.db` in the standard image),
outside both named data volumes. A process restart alone should retain
that file; replacing/removing the container loses its writable layer.

The fix makes `DATABASE_URL` work. `JARVIS_DATABASE_URL` remains supported
and takes precedence when both environment variables exist. Process
environment settings override `.env` settings. Native development with
neither variable still uses `./jarvis.db`.

New Compose installations therefore use the configured PostgreSQL service
and `postgres_data` volume. The override below allows an existing SQLite
installation to preserve its records on `jarvis_data` without converting
them or changing approval/publishing states.

## Preserve existing data before rebuilding

This is an operator procedure for the real deployment, not an action run by
the code change. Pause incoming n8n jobs and other API writers and allow
in-flight jobs to finish before taking the snapshot. Keep writers paused
until verification is complete. Do not remove the old container first.

1. On the **old, still-running container**, inspect the selected engine
   without printing credentials:

   ```bash
   docker compose exec -T api python -c "from app.db import engine; print(engine.url.get_backend_name()); print(engine.url.database)"
   ```

   If it is PostgreSQL, use the existing database backup procedure. If it
   is SQLite at another path, adapt the source path in the next command.
   The following commands assume the standard `/app/jarvis.db` fallback
   and the Compose-mounted `/data` volume. For a container started without
   Compose, first verify its actual volume mounts with
   `docker inspect --format '{{json .Mounts}}' CONTAINER_NAME`;
   a directory named `/data` alone is not evidence of durable storage.

2. Create a consistent SQLite snapshot directly on the existing data
   volume. The source is opened read-only and the target is created
   exclusively, so an existing snapshot is never overwritten:

   ```bash
   docker compose exec -T api python -c "import sqlite3; source=sqlite3.connect('file:/app/jarvis.db?mode=ro', uri=True); open('/data/jarvis-preserved.db', 'xb').close(); target=sqlite3.connect('/data/jarvis-preserved.db'); source.backup(target); assert target.execute('PRAGMA quick_check').fetchone()==('ok',); target.close(); source.close(); print('Snapshot verified: /data/jarvis-preserved.db')"
   ```

   Continue only if the command succeeds. On failure, keep the source and
   investigate; do not activate a partial snapshot. Copy the successful
   snapshot to a separate host backup directory as well, for example:

   ```bash
   docker compose cp api:/data/jarvis-preserved.db /absolute/path/to/private-backups/jarvis-preserved.db
   ```

   Create that host directory beforehand. Keep the backup outside Git and
   private: it includes application state and may include sensitive data.

3. In the deployment's private `.env`, select the preserved snapshot:

   ```dotenv
   JARVIS_DATABASE_URL=sqlite:////data/jarvis-preserved.db
   ```

   The four slashes select an absolute SQLite path. This override is read
   through the existing Compose `env_file` and takes precedence over its
   `DATABASE_URL`. The snapshot was created by the running API user, so it
   retains the appropriate ownership on the unchanged volume. Preserve
   the same Compose project name and volume mounts when recreating it.

4. Before and after the approved API rebuild, compare the IDs, counts and
   states returned by `/v1/instagram/media-pool`, `/v1/instagram/curate/drafts`
   (with `pending_only=false`), and `/v1/instagram/candidates`. Check engine
   selection again: it must now show `/data/jarvis-preserved.db` if that was
   the chosen preservation path. Resume jobs only after those checks.

The original file and separate snapshot remain available for recovery.
Do not switch an existing SQLite installation straight to empty PostgreSQL:
that would hide its history, not migrate it. A later PostgreSQL migration
requires a separate reviewed copy/verification procedure. Never use
`docker compose down -v` as part of this upgrade.

## Verification in this change

Regression tests start independent Python processes in different working
directories against the same explicit database path. They write through
the real Instagram services, then verify source groups, pool reservations,
finalized and pending drafts, approved/rejected/posted candidate states,
the published receipt, and duplicate `media_ref` detection after restart.
The publisher is a local test double and notifications are disabled.

This proves application persistence and URL selection. It does not certify
the owner's actual Docker mounts, migrate their live records, or make any
real Instagram call. Recovery of `publishing`/`rejected` candidates remains
a separate task; persisted states are deliberately left intact here.
