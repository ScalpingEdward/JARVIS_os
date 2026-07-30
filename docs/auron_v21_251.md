# AURON v21.251 — Execution Queue & Dependency Handling

## Purpose
Adds a persistent execution queue above the governed plan executor. Pending plan steps can be staged in order, with explicit dependencies between queue items.

## Commands
- `Baue Execution Queue`
- `Zeig Queue`
- `Was ist bereit?`
- `Queue Schritt erledigt`
- `Queue löschen`

## Endpoints
- `POST /auron/demo1/v21.251/dialogue`
- `GET /auron/demo1/v21.251/execution-queue`
- `GET /auron/demo1/v21.251/command-center`

## Dependency model
Queue item 1 is initially ready. Each later item depends on the previous queue index and becomes ready only after its dependency is marked completed.

## Safety
Queueing is scheduling/state metadata only. It does not create execution authority. Financial/high-risk execution remains approval-gated by the existing governed executor and Risk Brain.
