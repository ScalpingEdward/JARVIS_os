# PHOENIX v21.161 — Remediation Outcome Reliability Learning & Baseline Feedback Governance

v21.161 converts a human-approved `closed` remediation episode into bounded reliability-learning evidence and a separately reviewed baseline-feedback proposal.

## Flow

`Remediation Closed → Outcome Evidence → Reliability Learning → Bounded Baseline Feedback → Human Review → Approved Feedback`

## Learning inputs

- stability score
- aggregate confidence
- residual risk
- reconciliation quality
- exact baseline ID / version / digest lineage
- Risk Brain state

## Controls

- admission only from human-approved `closed` remediation episodes
- workspace and baseline lineage must match exactly
- confidence, stability and residual-risk thresholds fail closed
- proposed baseline movement is bounded by `max_adjustment` (default 0.05)
- explicit human approval required before `approved-feedback`
- replay protection and deterministic digests preserve auditability

## Safety boundary

The approved feedback is evidence only. This module performs no baseline activation, route mutation, policy mutation, permission or credential expansion, fund movement, order submission, or trading execution.

## Next

v21.162 should add Reliability Feedback Impact Simulation & Baseline Change Preview Governance, taking approved learning feedback and simulating downstream score/rank/failover/recovery impact before any versioned baseline proposal can advance.
