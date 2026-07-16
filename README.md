# PHOENIX OS

## Live Integrations Hub — v5.4

PHOENIX exposes a read-only integration layer for MT5, TradingView, Telegram and research feeds.

Core endpoints:

```text
GET  /v1/live-integrations/status
POST /v1/live-integrations
GET  /v1/live-integrations
POST /v1/live-integrations/{id}/heartbeat
POST /v1/live-integrations/events
GET  /v1/live-integrations/events/recent
```

All live connectors are read-only. v5.4 accepts normalized market events, connector heartbeats, latency, data-quality metadata and record counters, but it cannot place or modify orders.

Typical flow:

1. Register an MT5, TradingView, Telegram or research connector.
2. Send periodic heartbeats from the local bridge.
3. Normalize incoming alerts, quotes or research events.
4. Read recent events from the Command Center and downstream analysis modules.

## Full Local Launch — v5.2

PHOENIX can run locally as one coordinated stack:

- FastAPI Core Runtime
- PostgreSQL
- Redis
- Sandbox Runner
- Holographic Command Center
- persistent data and logs
- container health checks and automatic restart

### Windows

1. Install Docker Desktop and Python 3.
2. Download or clone this repository.
3. Double-click `START_PHOENIX.bat`.
4. Wait for `PHOENIX ONLINE — Welcome, MASTER Brano`.
5. The Command Center opens at `http://127.0.0.1:8080`.

Stop the system with `STOP_PHOENIX.bat`.

### Linux / macOS

```bash
chmod +x start_phoenix.sh
./start_phoenix.sh
```

### Service manager

```bash
python scripts/phoenix_launcher.py start
python scripts/phoenix_launcher.py status
python scripts/phoenix_launcher.py logs
python scripts/phoenix_launcher.py stop
```

On first start, the launcher:

- creates `.env` from `.env.example`
- generates `secrets/postgres_password.txt`
- synchronizes the local database password
- builds all containers
- waits for API and UI health checks
- opens the Command Center in the default browser

Real provider credentials remain optional and must be added manually to `.env`. Never commit `.env` or the generated secrets directory.

## Safety

PHOENIX starts in advisory mode. Automatic order execution, critical action execution and automatic merges remain disabled. Human approval is required for gated actions.
