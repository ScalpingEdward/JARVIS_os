# PHOENIX v21.84 — Third-Party & Supply-Chain Risk Governance

## Purpose

PHOENIX v21.84 adds an institutional governance layer for external providers, vendors, cloud services, data suppliers, connectivity providers and other supply-chain dependencies used by PHOENIX.

It consumes the governed security context introduced in v21.83 and evaluates whether a third-party dependency is sufficiently controlled, resilient, substitutable and contractually governed before it can be treated as an approved dependency.

The module is advisory and governance-only. It cannot onboard or terminate vendors, edit contracts, rotate credentials, change access rights, alter infrastructure, move funds or execute trades.

## Core dimensions

Each provider/service-domain observation is assessed across:

- due-diligence coverage
- security assurance
- privacy assurance
- operational resilience
- financial health
- subcontractor transparency
- concentration dependency
- contractual control coverage
- exit-plan readiness
- incident history
- jurisdiction risk
- freshness and confidence
- business criticality

## Aggregate intelligence

The service calculates:

- Due Diligence Strength
- Security & Privacy Strength
- Resilience Strength
- Commercial Strength
- Supply-Chain Transparency
- Exit Readiness
- Concentration Resilience
- Aggregate Assurance
- Aggregate Residual Risk
- Confidence

## Governed lifecycle signals

Provider-level signals include:

- `acceptable`
- `due-diligence-gap`
- `concentration-alert`
- `security-alert`
- `resilience-alert`
- `contract-alert`
- `exit-risk`

The record lifecycle additionally supports:

- blocked
- draft
- evidence-ready
- assessed
- review-required
- approved
- active
- monitoring
- acceptable
- due-diligence-gap
- concentration-alert
- security-alert
- resilience-alert
- contract-alert
- exit-risk
- escalated
- suspended
- revoked
- archived

## Required actions

The engine can require one or more of the following governed actions:

- independent third-party due diligence
- concentration and substitutability review
- security and privacy remediation review
- business continuity and recovery review
- contractual controls and audit-rights review
- exit and transition plan review
- third-party risk committee escalation
- Risk Brain hard block

## Hard-block rule

A provider can trigger a `risk-brain-hard-block` when both conditions are met:

1. provider criticality is at least 0.90; and
2. calculated residual risk is at least 0.60.

The hard block is authoritative and cannot be overridden by vendor, compliance, cyber, model-risk, committee or portfolio layers.

## Approval controls

Human approval is mandatory before activation.

Approval is refused while unresolved third-party risk flags are present. Operation IDs are recorded and replay-protected. Source keys are unique per workspace and all records are workspace-isolated.

## API

- `GET /v1/third-party-supply-chain-risk/status`
- `POST /v1/third-party-supply-chain-risk/records`
- `GET /v1/third-party-supply-chain-risk/records`
- `GET /v1/third-party-supply-chain-risk/records/{record_id}`
- `POST /v1/third-party-supply-chain-risk/records/{record_id}/actions`
- `GET /v1/third-party-supply-chain-risk/audit`

## Safety boundary

The status endpoint explicitly reports:

```text
vendor_mutation_enabled=false
contract_mutation_enabled=false
access_mutation_enabled=false
execution_enabled=false
```

The module performs no vendor onboarding/offboarding, procurement mutation, contract editing, credential rotation, privilege mutation, infrastructure change, portfolio mutation, routing mutation, fund movement, order submission or execution.

## Integration

v21.83 establishes identity, privileged-access and cyber-control assurance. v21.84 extends that trust boundary outside PHOENIX to material external dependencies and their supply chains.

A provider cannot be considered safe solely because internal cybersecurity controls are healthy. Third-party concentration, contract gaps, poor exit readiness, weak resilience or unresolved due-diligence findings remain independent governance blockers.
