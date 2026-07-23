# PHOENIX v21.79 — Institutional Compliance Governance

## Purpose

PHOENIX v21.79 introduces an institutional compliance governance layer above the Autonomous Risk Committee. It evaluates policy coverage, evidence completeness, control effectiveness, disclosures, surveillance, recordkeeping, jurisdiction coverage and restriction integrity without mutating live policies, portfolios or execution systems.

## Core assessments

- Policy coverage
- Evidence integrity
- Control effectiveness
- Disclosure readiness
- Surveillance coverage
- Recordkeeping quality
- Restriction integrity
- Aggregate compliance
- Confidence and freshness
- Jurisdiction coverage
- Materiality-weighted severity

## Governed alerts

- Control gap
- Disclosure gap
- Restriction alert
- Surveillance alert
- Recordkeeping alert
- Missing jurisdiction evidence
- Restricted-domain legal review

## Lifecycle

`blocked`, `draft`, `evidence-ready`, `assessed`, `policy-ready`, `review-required`, `approved`, `active`, `monitoring`, `compliant`, `control-gap`, `disclosure-gap`, `restriction-alert`, `surveillance-alert`, `recordkeeping-alert`, `escalated`, `suspended`, `revoked`, `archived`.

## API

- `GET /v1/institutional-compliance/status`
- `POST /v1/institutional-compliance/records`
- `GET /v1/institutional-compliance/records`
- `GET /v1/institutional-compliance/records/{record_id}`
- `POST /v1/institutional-compliance/records/{record_id}/actions`
- `GET /v1/institutional-compliance/audit`

## Governance controls

- Human approval before activation
- Compliance flags block approval until remediation
- Operation replay protection
- Workspace isolation
- Duplicate source-key protection
- Full versioned audit trail
- Risk Brain authority remains final

## Safety boundary

This module is advisory and governance-only. It cannot:

- modify compliance policies
- remove trading restrictions
- modify risk limits
- alter portfolio positions
- activate strategies
- change routing
- move funds
- submit or execute orders

The status endpoint explicitly reports all mutation and execution capabilities as disabled.

## Integration

v21.79 consumes the governed decision context from v21.78 and adds the institutional controls required before any future operational layer may be considered. Committee approval does not override compliance restrictions or Risk Brain hard blocks.
