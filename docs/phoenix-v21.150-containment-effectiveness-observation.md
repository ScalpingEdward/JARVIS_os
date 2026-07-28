# PHOENIX v21.150 — Containment Effectiveness Observation & Quarantine Resolution Readiness Governance

v21.150 observes whether a human-approved v21.149 containment plan actually preserves required downstream capabilities while the affected consumer remains quarantined.

## Flow

`Quarantined Consumer → Fallback Ready → Observation Window → Effectiveness Scoring → Human Review → Resolution Ready`

## Observation inputs

- required capability availability
- fallback health
- dependency satisfaction
- latency
- confidence
- freshness

The service derives deterministic effectiveness and residual-risk scores. A record remains `degraded` whenever availability, fallback health, dependency satisfaction, confidence, freshness or residual-risk thresholds are violated.

## Safety boundary

`resolution-ready` is governance evidence only. It does not remove quarantine, activate a fallback, mutate routing, change policy, expand permissions/credentials, move funds, submit orders, or execute trades. Explicit human approval and Risk Brain authority remain mandatory.

## Fail-closed controls

- admission only from human-approved `fallback-ready` containment evidence
- workspace binding
- Risk Brain hard-block propagation
- no-sample rejection
- replay and duplicate record protection
- deterministic containment/readiness/audit digests

## Next

v21.151 should add Quarantine Resolution Authorization & Controlled Consumer Reintegration Governance, turning approved `resolution-ready` evidence into a separately human-approved reintegration authorization with exact consumer/baseline binding and staged re-entry, without autonomous routing or policy mutation.
