# AURON v21.248

AURON v21.248 adds explicit conversation/mission state so the operator and assistant can maintain a shared current goal, active task and next step.

## Added
- Session/workspace/operator-scoped current goal.
- Current task/focus.
- Next step.
- Natural commands such as `Unser Ziel ist ...`, `Wir arbeiten an ...`, and `Nächster Schritt ist ...`.
- Natural reads such as `Woran arbeiten wir?`, `Was ist unser Ziel?`, and `Was kommt als Nächstes?`.
- State-specific completion commands such as `Aufgabe erledigt` without deleting the goal.
- `GET /auron/demo1/v21.248/state` for inspecting the active mission state.
- Command center surfaces active goal and current focus/next step.
- v21.247 governed memory candidates remain active underneath.
- Financial/high-risk execution remains approval-gated.

## Runtime
Checkpoint URL:
`http://127.0.0.1:8000/auron/demo1/v21.248/command-center`
