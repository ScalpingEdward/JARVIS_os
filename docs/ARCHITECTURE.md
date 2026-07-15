# JARVIS OS — Architecture

## Architectural style
JARVIS OS is a modular service-oriented application with explicit interfaces between the user interface, orchestration, models, tools, memory, approvals, and specialist modules.

## Core layers

### 1. Interfaces
- Web control panel
- Desktop client
- Mobile-friendly control surface
- Voice input/output
- Optional Telegram control channel

### 2. Core API
- Authentication and sessions
- Configuration
- Task submission
- Status and reporting
- Approval requests
- Audit access

### 3. Orchestrator
- Reads the master plan and active roadmap
- Converts approved goals into bounded tasks
- Tracks dependencies and task state
- Assigns work to eligible agents
- Stops on unresolved ambiguity, risk, or missing approval

### 4. Model Router
Provider-neutral interface for Claude, OpenAI, Gemini, and optional local models. Routing considers capability, cost, latency, privacy, and task risk.

### 5. Tool Gateway
All tools are registered with explicit schemas, permissions, timeouts, and audit events. Agents never receive unrestricted operating-system access by default.

### 6. Memory
- Conversation/session memory
- Project knowledge
- User-approved long-term memory
- Retrieval index
- Structured records for tasks, approvals, and decisions

### 7. Approval and Audit
- Risk classification for every action
- Human approval gates for critical operations
- Immutable event history where practical
- Traceability from goal to task, code change, test, and result

### 8. Specialist modules
Trading, Telegram, productivity, business automation, health, research, smart home, and future modules integrate only through stable core interfaces.

## Initial technology direction
- Backend: Python 3.12+ and FastAPI
- Database: PostgreSQL
- Vector search: pgvector when required
- Queue: begin with database-backed jobs; add Redis only when justified
- Frontend: web-first; framework selected by ADR
- Packaging: Docker plus documented native Windows setup
- Source control and workflow: GitHub issues, branches, pull requests, and Actions

## Portability rules
- Configuration through environment variables and versioned example files
- No absolute machine-specific paths
- No credentials in repository or portable package
- Database export/import documented
- Data directories configurable
- External SSD/USB may carry encrypted project data and configuration, but cloud model access still requires internet and credentials

## Repository target structure
```text
app/
  api/
  core/
  models/
  orchestration/
  tools/
  memory/
  approvals/
modules/
  trading/
  telegram/
  productivity/
frontend/
docs/
tests/
scripts/
tasks/
```

## Change control
Significant technology or boundary changes require an ADR under `docs/adr/` before implementation.
