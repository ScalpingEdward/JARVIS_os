# PHOENIX v21.125 — Decision Synthesis & Uncertainty Governance

## Purpose
v21.125 converts an approved v21.124 reasoning packet into an explicit candidate decision before any execution proposal can exist. It records the preferred alternative, competing alternatives, assumptions, unresolved questions, confidence, uncertainty, downside risk and reversibility.

## Core governance
- Preferred decision candidate
- Alternative comparison
- Expected utility and confidence
- Evidence-confidence and freshness inheritance
- Assumption tracking
- Unresolved-question tracking
- Uncertainty scoring
- Downside-risk scoring
- Reversibility assurance
- Alternative-separation scoring
- Decision packet integrity digest
- Human approval before `ready`
- Risk Brain hard block for critical low-confidence/high-uncertainty decisions

## Lifecycle
`blocked`, `draft`, `review-required`, `conflict`, `approved`, `ready`, `rejected`, `revoked`, `archived`.

## API
- `GET /v1/decision-synthesis/status`
- `POST /v1/decision-synthesis/records`
- `GET /v1/decision-synthesis/records`
- `GET /v1/decision-synthesis/records/{record_id}`
- `POST /v1/decision-synthesis/records/{record_id}/actions`
- `GET /v1/decision-synthesis/audit`

## Safety boundary
This module synthesizes and governs candidate decisions only. It does not create executable change proposals, invoke connectors, mutate credentials or permissions, move funds, submit orders or execute trades. Human approval is mandatory before a candidate decision reaches `ready`.

## Integration
v21.124 assembles a citation-complete, conflict-resolved reasoning packet. v21.125 turns that packet into a bounded decision object with explicit alternatives and uncertainty. The next layer may use only a `ready` decision packet as input to an execution-proposal contract.
