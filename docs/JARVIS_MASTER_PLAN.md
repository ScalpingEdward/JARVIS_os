# JARVIS OS — Master Plan

## Vision
Create a portable, provider-independent personal AI operating system owned by Branislav Gombos. JARVIS OS must coordinate specialist AI agents, remember long-term context, use approved tools, and support modular capabilities such as trading, business automation, research, productivity, voice, and vision.

## Non-negotiable principles
1. The owner controls the repository, data, credentials, deployment, and backups.
2. No single AI provider, coding agent, platform, or VPS may become mandatory.
3. Models are accessed through replaceable adapters and a model router.
4. Critical actions require explicit approval and complete audit logs.
5. Every module is independently testable and removable.
6. Secrets never enter source control.
7. The system must be portable to a new Windows computer or VPS.
8. Open-source dependencies must be reviewed for license, maintenance, and security.

## Target operating model
The owner defines goals and approvals. A Master Agent decomposes approved goals into bounded tasks. Worker agents implement, test, review, and document changes through GitHub branches and pull requests.

## Initial modules
- Core API and configuration
- Model Router
- Agent task queue and orchestration
- Approval and audit system
- Memory interfaces
- Web control interface
- Voice interface
- Telegram signal module
- MT5 bridge and risk controls

## Explicitly out of scope for the first core release
- Autonomous real-money trading
- Autonomous purchases or subscriptions
- Unsupervised production deployment
- Sending external messages without approval
- Full control of the owner's Windows system

## Success criteria for JARVIS Core v1
- Starts reproducibly on a clean Windows machine or Docker host.
- Supports at least two interchangeable model providers.
- Can create, queue, assign, and track bounded tasks.
- Records all tool calls and approvals.
- Rejects critical actions without authorization.
- Has automated tests and clear setup documentation.
- Can be backed up and moved without Polsia, Cursor, Claude Code, or Codex.

## Governance
Architecture changes require an Architecture Decision Record (ADR). Security boundaries may only be weakened with explicit owner approval. Each completed phase ends with a documented review and backup.
