# PHOENIX v21.151 — Quarantine Resolution Authorization & Controlled Consumer Reintegration Governance

v21.151 converts human-approved `resolution-ready` evidence from v21.150 into a separately governed reintegration authorization for the quarantined consumer.

## Flow

`Resolution Ready → Reintegration Review → Human Approval → Authorized → Human-Approved Stages → Reintegrated`

## Binding guarantees

- workspace identity must match
- quarantined consumer identity must match
- baseline ID, version and digest must match the pinned quarantine evidence
- Risk Brain hard blocks propagate
- every re-entry stage requires explicit human approval
- replay and duplicate record protection are enforced
- deterministic readiness and authorization digests preserve auditability

## Safety boundary

This module does not remove quarantine automatically, mutate routes or policies, expand permissions, alter credentials, move funds, submit orders, or execute trades. It only governs the authorization state and staged re-entry evidence.

## Next

v21.152 should add Reintegration Stability Observation & Post-Quarantine Confidence Governance, observing the newly reintegrated consumer across a bounded window and requiring human-reviewed confidence before the quarantine episode is finally closed.
