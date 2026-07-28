# PHOENIX v21.143 — Incident Episode Closure & Reliability Baseline Update Governance

v21.143 converts a human-approved `stable` v21.142 observation into a governed incident closure record and a bounded reliability-baseline feedback proposal.

## Flow

`Recovery Attested → Stability Observation → Stable → Incident Closure Review → Human Approval → Closed`

## Reliability feedback

The module derives observed reliability from aggregate confidence and residual risk. Any proposed baseline movement is bounded by `max_adjustment` (default 0.05). The proposal is evidence only: it does not autonomously modify adapter/worker routing weights, policies, permissions, credentials, or execution settings.

## Fail-closed controls

Closure is blocked when stable evidence is not human approved, workspace binding fails, confidence is below the closure floor, residual risk exceeds the ceiling, or Risk Brain is blocked. Replay protection and deterministic digests preserve auditability.

## Safety boundary

No network call, route mutation, policy mutation, credential change, fund movement, order submission, or trading execution is performed.

## Next

v21.144 should add Human-Approved Reliability Baseline Commit & Versioned Rollback Governance, turning the bounded proposal into a separately approved versioned baseline record with rollback metadata, while still preventing autonomous routing or policy changes.
