# JARVIS always-on deployment

## First start
1. Install Docker Desktop or Docker Engine with Compose.
2. Copy `.env.example` to `.env` and set strong unique credentials.
3. Create `secrets/postgres_password.txt` with the same PostgreSQL password and keep it out of Git.
4. Run `docker compose up -d --build`.
5. Verify with `docker compose ps` and `curl http://127.0.0.1:8000/health`.

All services use `restart: unless-stopped`, so they return after a host reboot when Docker starts automatically.

## Mobile access
Keep the API bound to `127.0.0.1`. Install Tailscale on the host and phone, then publish HTTPS only inside your tailnet:

```bash
tailscale serve --bg https+insecure://localhost:8000
```

Use the generated `https://<machine>.<tailnet>.ts.net` address on the phone. Do not expose port 8000 directly to the public internet.

## Persistence
PostgreSQL, application data, and logs use named Docker volumes. Rebuilding containers does not remove them. Never run `docker compose down -v` unless you intentionally want to delete all persistent data.

## Backup and restore
Run `sh scripts/backup.sh`. Restore with `sh scripts/restore.sh backups/<timestamp>` while no workflows are mutating data. Copy backups to an encrypted second location.

## Secrets
Never commit `.env`, token files, Telegram sessions, API keys, database passwords, or backups. Prefer fine-grained GitHub tokens and provider keys restricted to the minimum permissions.

## Sandbox runner
The runner is a separate unprivileged service with a read-only filesystem, dropped Linux capabilities, and no access to the Docker socket. Phase 22 provides its durable lifecycle and heartbeat; actual job execution remains governed by the Phase 20 allowlist, network-off default, timeouts, and resource limits.
