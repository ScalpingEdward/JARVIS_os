# PHOENIX v21.155 — Reintegration Reliability Baseline Commit & Controlled Consumer Rollout Governance

v21.155 converts a human-approved v21.154 `approved-preview` into a separately approved, versioned reliability baseline record and a staged consumer eligibility rollout.

## Flow

`Approved Preview → Commit Review → Human Approval → Committed Baseline → Stage Review → Staged → Active`

Every stage advance requires explicit human approval. A baseline becoming `committed` or `active` in this governance module does not itself mutate runtime routing, policies, credentials, permissions, or execution settings.

## Controls

- exact workspace and preview evidence binding
- versioned baseline ID/value/digest records
- supported downstream consumer allow-list
- fail-closed unsupported-consumer handling
- Risk Brain hard-block propagation
- source-key replay protection and workspace isolation
- deterministic audit digests
- human approval before commit and every rollout-stage advance

## Safety boundary

This module records governance state only. It performs no network calls, no route mutation, no policy mutation, no fund movement, no order submission and no trading execution.

## Roadmap

End-stage Availability / Deferred Approval / Presence / Voice / Mobile / Hologram work remains tracked separately in issue #413 and should be installed only after the current core governance chain is stable.

## Next

v21.156 should add Reintegration Baseline Adoption Receipt & Cross-Consumer Consistency Governance, requiring every active eligible consumer to acknowledge the exact baseline version/digest and detecting inconsistent adoption across the consumer set before closure.
