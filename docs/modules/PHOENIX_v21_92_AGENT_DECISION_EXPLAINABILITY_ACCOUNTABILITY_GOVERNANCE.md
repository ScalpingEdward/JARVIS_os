# PHOENIX v21.92 — Agent Decision Explainability & Accountability Governance

## Purpose

PHOENIX v21.92 governs whether agent decisions are explainable, evidence-backed, traceable, reviewable and attributable to accountable human ownership. It is an assurance layer only and cannot rewrite decisions, override agents, mutate portfolios or execute trades.

## Core controls

- rationale completeness
- evidence coverage
- source traceability
- counterfactual quality
- uncertainty disclosure
- policy-reference coverage
- human-owner coverage
- reviewability
- override traceability
- reproducibility
- missing-evidence detection
- untraceable-source detection
- undocumented-override detection
- unresolved-challenge detection
- critical-decision Risk Brain hard blocks

## Lifecycle

- blocked
- draft
- evidence-ready
- assessed
- review-required
- approved
- active
- monitoring
- explainable
- rationale-gap
- evidence-gap
- traceability-alert
- accountability-alert
- override-alert
- escalated
- suspended
- revoked
- archived

## Endpoints

- `GET /v1/agent-decision-accountability/status`
- `POST /v1/agent-decision-accountability/records`
- `GET /v1/agent-decision-accountability/records`
- `GET /v1/agent-decision-accountability/records/{record_id}`
- `POST /v1/agent-decision-accountability/records/{record_id}/actions`
- `GET /v1/agent-decision-accountability/audit`

## Approval rules

Records with unresolved rationale, evidence, traceability, accountability, override or residual-risk findings cannot be approved. Activation requires prior human approval. Critical decisions with untraceable evidence, undocumented overrides or extreme residual risk receive a Risk Brain hard block.

## Safety boundary

The module explicitly reports:

- `decision_mutation_enabled=false`
- `automatic_override_enabled=false`
- `agent_execution_enabled=false`
- `portfolio_mutation_enabled=false`
- `execution_enabled=false`

It cannot rewrite decisions, alter rationale, execute overrides, mutate agent authority, move funds, change portfolio state, route orders or execute trades.

## Integration

v21.92 extends v21.91 Objective & Intent Alignment Governance. An aligned objective is insufficient when the resulting decision cannot be reconstructed, challenged, attributed or explained. Decision accountability cannot override Agent Authorization, Runtime Supervision, Memory/Context Provenance, Multi-Agent Coordination, Objective/Intent Alignment, Risk Brain, compliance, cybersecurity, model-risk or data-governance hard blocks.

## Auditability

Every governed action records workspace, record, actor, operation ID, timestamp and optional reason metadata. Duplicate source keys are blocked per workspace and operation receipts are replay-protected.
