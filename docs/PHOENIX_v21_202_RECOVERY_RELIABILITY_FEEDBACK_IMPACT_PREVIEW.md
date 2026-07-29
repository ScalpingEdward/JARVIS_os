# PHOENIX v21.202 — Recovery Reliability Feedback Impact Simulation & Baseline Change Preview Governance

## Purpose
Consumes human-approved `approved-feedback` evidence from v21.201 and produces a bounded, auditable baseline-change preview before any versioned baseline proposal is allowed.

## Governance
- exact workspace and baseline ID/version/digest lineage is preserved;
- feedback adjustment is bounded to ±0.05;
- candidate value is computed deterministically and must remain in `[0.0, 1.0]`;
- score, rank, failover-tendency and recovery-readiness impacts are bound into the preview;
- blast radius and residual risk are checked against configured ceilings;
- Risk Brain hard blocks fail closed;
- duplicate approved sources are rejected;
- `approved-preview` requires explicit human approval;
- deterministic preview and audit digests provide replay-verifiable evidence.

## State machine
`approved-feedback` → `review-required` → human approval → `approved-preview`

Candidate-range violations, invalid admission, duplicate approved evidence or Risk Brain hard block → `blocked`.
Risk-limit exceedance remains `review-required`.

## Boundary
Simulation/governance only. This module does not mutate, activate, commit, roll back or distribute a baseline and performs no runtime consumer mutation or execution.

## Next
v21.203 — Versioned Recovery Reliability Baseline Proposal & Controlled Commit Governance.
