# PHOENIX v21.142 — Recovery Stability Observation & Primary Route Confidence Governance

v21.142 adds a bounded post-recovery observation window after an attested v21.141 recovery.

## Flow

`Recovery Attested → Stability Samples → Confidence Scoring → Human Review → Stable Episode Closure`

## Signals

- primary availability
- latency quality
- receipt reconciliation quality
- worker heartbeat
- gateway health
- adapter health
- confidence and freshness weighting

## Governance

- only attested recoveries may enter observation
- protected operations and upstream Risk Brain blocks fail closed
- degraded confidence cannot be approved
- human approval is required before the failover/recovery episode may be closed as stable
- replay protection, workspace isolation and deterministic evidence/confidence digests remain active

## Safety boundary

The module observes and scores only. It performs no external execution, route mutation, permission expansion, fund movement, order submission or trading execution.

## Next

v21.143 should add Incident Episode Closure & Reliability Baseline Update Governance, converting an approved stable recovery observation into a human-approved incident closure record and bounded reliability baseline feedback without autonomous routing or policy mutation.
