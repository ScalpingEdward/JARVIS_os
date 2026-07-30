# AURON v21.249 — Goal-Aware Planning

AURON now converts the active mission state from v21.248 into a persistent ordered working plan.

## Operator commands

- `Plane unser Ziel`
- `Zeig Plan`
- `Was ist der nächste Planschritt?`
- `Planschritt erledigt`
- `Plan löschen`

## Behavior

A plan requires an active goal. When created, AURON uses the current goal, current focus and existing next step to derive up to five ordered steps. The first pending plan step becomes the mission state's next step.

Completing a plan step marks it done and automatically advances the next-step pointer. Plan state is scoped by session, workspace and operator and persists through the existing SQL-backed memory layer.

## API

- `POST /auron/demo1/v21.249/dialogue`
- `GET /auron/demo1/v21.249/plan`
- `GET /auron/demo1/v21.249/command-center`

## Safety

Planning metadata never grants execution authority. Existing approval gates remain authoritative for financial and other high-risk actions.
