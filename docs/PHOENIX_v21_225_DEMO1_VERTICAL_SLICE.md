# PHOENIX v21.225 — Demo 1 Vertical Slice Integration & Operator Experience Governance

## Milestone
This release is the first bounded PHOENIX vertical slice intended to behave as one operator-facing system rather than as a sequence of isolated governance modules.

## Demo 1 capabilities
- operator command intake through one Demo 1 orchestration path;
- voice-first interaction with text fallback;
- memory/context availability surfaced into the orchestration decision;
- tool-health awareness;
- read-only and non-gated work may continue immediately;
- high-risk or explicitly gated actions are converted into approval requests;
- focus/sleep/quiet windows suppress noncritical interruptions while preserving queued work;
- critical approval requests remain visible in governance state even while presentation stays silent;
- Risk Brain remains authoritative and fails closed;
- deterministic audit digest for every Demo 1 orchestration result.

## Operator experience
Typical interaction:

1. Operator speaks or submits a command.
2. PHOENIX checks context, mode, tool availability and risk class.
3. Safe work is allowed to continue without unnecessary interruption.
4. Approval-gated work is collected and surfaced as an explicit approval request.
5. In focus/sleep mode, noncritical gated items are deferred rather than repeatedly interrupting the operator.
6. When interaction is available, PHOENIX may surface the approval request using the operator message: `Sir? I need your approval before I can continue with this action.`

## API
- `GET /phoenix/demo1/v21.225/status`
- `POST /phoenix/demo1/v21.225/run`

## Safety boundary
Demo 1 is intentionally bounded. It demonstrates orchestration, operator interaction, quiet-mode behavior, approval governance and context/tool awareness. It does **not** claim that every historical PHOENIX subsystem is wired into a production runtime, and it does not enable autonomous high-risk execution.

`autonomous_high_risk_execution_enabled = false`

## Acceptance criteria
- read-only work proceeds without approval;
- high-risk work cannot proceed without approval;
- approval-gated tools remain gated regardless of action label;
- sleep/focus modes defer noncritical interruptions;
- Risk Brain hard block always wins;
- voice falls back to text when voice is unavailable;
- deterministic audit evidence is returned for every request.

## After Demo 1
The next phase should be integration hardening: actual application-router registration, real voice/STT/TTS adapters, persistent approval inbox, memory provider binding, operator UI/dashboard, tool adapters and end-to-end demo scripts against live local services.
