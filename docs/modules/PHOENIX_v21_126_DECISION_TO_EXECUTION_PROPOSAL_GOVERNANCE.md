# PHOENIX v21.126 — Decision-to-Execution Proposal Governance

## Purpose
v21.126 converts only approved or ready v21.125 decision packets into structured, explicitly non-executable action proposals.

## Proposal contract
Each proposal carries target, operation, rationale, expected outcome, preconditions, postconditions, rollback plan, blast radius, reversibility, observability and validation readiness.

## Governance
- human approval before authorization
- authorization before ready state
- proposals remain `executable=false`
- replay protection and workspace isolation
- duplicate source-key protection
- Risk Brain hard blocks for fund movement, order submission, trading execution, credential mutation, permission escalation and safety-control disabling

## Safety boundary
This module does not invoke connectors, mutate infrastructure, write external systems, move funds, submit orders or execute trades. It prepares a bounded proposal for the downstream safe-execution contract chain only.

## Integration
v21.125 produces an approved decision packet. v21.126 produces a governed non-executable proposed action. v21.127 should bind an authorized proposal cryptographically into the existing safe-execution contract/sandbox chain.
