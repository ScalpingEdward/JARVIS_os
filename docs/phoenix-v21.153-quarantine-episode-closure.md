# PHOENIX v21.153 — Quarantine Episode Closure & Reintegration Reliability Feedback Governance

v21.153 closes a quarantine episode only after v21.152 has produced human-approved `stable` reintegration evidence.

## Flow

`Quarantine → Reintegration → Stability Observation → Stable → Closure Review → Human Approval → Closed`

## Reliability feedback

The module derives an observed reliability score from aggregate confidence and residual risk. Any proposed reliability movement is bounded by `max_adjustment` (default 0.05). The result is feedback evidence only and does not autonomously modify routing, policy, baseline, permissions, credentials, or execution settings.

## Fail-closed admission

Closure is blocked when stable evidence is missing human approval, workspace binding fails, required consumer/baseline identity is missing, confidence is below the closure floor, residual risk exceeds the ceiling, or Risk Brain is blocked.

## Safety boundary

No network execution, quarantine removal side effect, runtime mutation, routing mutation, policy mutation, baseline mutation, permission/credential expansion, fund movement, order submission, or trading execution is performed.

## Roadmap note

Issue #413 remains the deferred end-stage Presence roadmap covering user availability, deferred approvals, autonomous work continuation, presentation routing, desktop/mobile/voice presence, avatar/hologram runtime, and the final device bridge.

## Next

v21.154 should add Reintegration Reliability Baseline Proposal & Impact Preview Governance, taking a closed quarantine episode and producing a separately reviewed reliability-baseline candidate plus simulation-only impact preview before any baseline adoption path is considered.
