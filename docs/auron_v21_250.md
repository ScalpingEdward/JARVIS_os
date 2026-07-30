# AURON v21.250 — Plan Execution Coordinator

AURON can now inspect the current goal-aware plan step and map it into the existing governed Demo 1 capability router before anything is executed.

## Commands

- `Bereite nächsten Planschritt vor`
- `Zeige Execution Preview`
- `Führe nächsten Planschritt aus`

## Execution classes

- `safe-capability`: supported low-risk capability; can execute through the governed orchestrator.
- `approval-required`: financial/high-risk capability; never executed autonomously.
- `blocked`: Risk Brain prevents execution.
- `conversation/manual`: no supported tool route; step stays open for human/conversational work.

## Plan advancement

A plan step is marked done only after a low-risk capability returns `completed`. Failed, unsupported, blocked, or approval-required steps remain open.

## Endpoint

- `GET /auron/demo1/v21.250/execution-preview`
- `POST /auron/demo1/v21.250/dialogue`
- `GET /auron/demo1/v21.250/command-center`

## Safety

The coordinator uses the existing v21.238 intent planner and executor. Financial execution keeps its mandatory human approval gate, and Risk Brain hard-block remains authoritative.
