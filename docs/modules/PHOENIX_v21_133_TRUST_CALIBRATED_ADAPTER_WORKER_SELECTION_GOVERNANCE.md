# PHOENIX v21.133 — Trust-Calibrated Adapter & Worker Selection Governance

## Purpose
Use approved v21.132 execution-outcome feedback to rank already-eligible adapter/worker pairs without weakening capability, permission, sandbox, policy, human-approval or Risk Brain controls.

## Selection inputs
- capability match
- permission match
- sandbox match
- connector/policy match
- execution trust
- reliability
- latency quality
- evidence freshness
- confidence

Mandatory control mismatches are fail-closed. Trust never compensates for a missing permission, capability, sandbox or policy requirement.

## Lifecycle
`blocked`, `evidence-ready`, `review-required`, `approved`, `ready`, `revoked`, `archived`.

## Safety boundary
Selection governance only. No autonomous routing mutation, no permission expansion, no connector/network execution, no credential mutation, no fund movement, no order submission and no trading execution. Human approval is required before `ready`; Risk Brain remains authoritative.

## Integration
v21.132 produces bounded approved reliability feedback. v21.133 uses that feedback to rank execution candidates while preserving the complete v21.116–v21.131 safety chain.

## Next
v21.134 should add Trust-Calibrated Dispatch Planning & Failover Governance, producing an approved primary/standby dispatch plan with deterministic failover criteria while keeping actual execution behind the existing one-time permit and gateway controls.
