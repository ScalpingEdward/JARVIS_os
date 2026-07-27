# PHOENIX v21.134 — Trust-Calibrated Dispatch Planning & Failover Governance

## Purpose
v21.134 converts the approved trust-calibrated execution selection from v21.133 into a governed primary/standby dispatch plan. It preserves all mandatory capability, permission, sandbox, adapter, gateway, worker, authorization-chain and one-time-permit controls.

## Core controls
- Rank already-eligible adapter/worker pairs using approved trust signals.
- Select one primary and one standby candidate.
- Require deterministic failover criteria for primary failure, latency degradation, receipt-reconciliation failure, worker heartbeat loss and gateway health loss.
- Fail closed when fewer than two eligible candidates are available.
- Require human approval before a plan becomes `ready`.
- Never execute a dispatch or autonomous failover inside this module.

## Safety boundary
Selection and failover planning only. No network call, no automatic route mutation, no permission expansion, no credential mutation, no fund movement, no order submission and no trading execution. Risk Brain remains authoritative.

## Integration
v21.133 answers which eligible adapter/worker pairs are most trustworthy. v21.134 turns that ranked set into a primary/standby dispatch plan. The downstream one-time permit, gateway, worker and receipt controls remain mandatory and cannot be bypassed.

## Next
v21.135 should add Dispatch Health Evaluation & Governed Failover Trigger Verification, evaluating runtime health evidence against the approved v21.134 failover policy and producing a non-executing failover authorization decision.
