# PHOENIX v21.154 — Reintegration Reliability Baseline Proposal & Impact Preview Governance

v21.154 converts a human-approved closed quarantine episode into a bounded reliability baseline candidate and simulation-only downstream impact preview.

## Flow

`Quarantine Closed → Reliability Candidate → Impact Simulation → Human Review → Approved Preview`

## Simulation dimensions

- candidate reliability score delta
- simulated candidate-rank movement
- simulated failover tendency change
- simulated recovery-readiness change
- blast radius
- residual risk

## Fail-closed controls

The preview is blocked when the source episode is not closed and human approved, workspace or consumer/baseline bindings are missing, Risk Brain is blocked, the proposed score delta exceeds the configured limit, blast radius exceeds its ceiling, or residual risk exceeds its ceiling.

## Safety boundary

This module is proposal and simulation only. It does not activate a baseline, mutate routing, change policies, alter permissions or credentials, perform network execution, move funds, submit orders, or execute trades.

## Roadmap note

Issue #413 remains the deferred end-stage Interaction/Presence roadmap: availability/DND, deferred approvals, dependency-aware work continuation, presentation routing, desktop/mobile/voice surfaces, avatar/hologram runtime, and finally the hardware-specific hologram bridge.

## Next

v21.155 should add Reintegration Reliability Baseline Commit & Controlled Consumer Rollout Governance, converting an approved preview into a separately human-approved versioned baseline record and staged consumer eligibility without autonomous runtime mutation.
