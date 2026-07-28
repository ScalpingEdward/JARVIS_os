# PHOENIX v21.148 — Drift Escalation, Consumer Quarantine & Re-Adoption Governance

v21.148 converts a human-reviewed v21.147 drift event into an explicitly approved quarantine for the affected governance consumer. The consumer remains quarantined until a fresh adoption receipt exactly matches the expected baseline ID, version and digest and a human approves re-adoption.

## Flow

`Drift Detected → Human Drift Review → Quarantine Review → Human Approval → Quarantined → Fresh Adoption Receipt → Exact-Version Reconciliation → Human Approval → Re-Adopted`

## Controls

- drift must already be `drift-reviewed`
- workspace and consumer identity are preserved
- expected baseline ID/version/digest are pinned from the reviewed drift evidence
- quarantine requires explicit human approval
- re-adoption requires an `adopted` receipt with exact baseline identity, version and digest
- mismatches keep the consumer quarantined
- Risk Brain hard blocks propagate
- source replay and duplicate record protection are enforced
- deterministic evidence digests preserve auditability

## Safety boundary

This module changes governance state only. It performs no network execution, autonomous drift correction, route mutation, policy mutation, credential/permission expansion, fund movement, order submission or trading execution.

## Next

v21.149 should add Quarantine Fleet Impact & Dependency Containment Governance, determining whether quarantining one baseline consumer creates downstream dependency gaps and requiring human-approved containment/fallback plans without autonomous routing or policy mutation.
