# PHOENIX v21.163 — Versioned Reliability Baseline Proposal & Controlled Commit Governance

v21.163 converts a human-approved v21.162 impact preview into a separately reviewed, versioned reliability baseline candidate.

## Flow

`Approved Feedback → Impact Simulation → Approved Preview → Versioned Proposal → Human Approval → Committed`

## Controls

- exact workspace and baseline lineage preservation
- previous-version and previous-value rollback metadata
- monotonic versioning
- bounded value range `[0.0, 1.0]`
- bounded candidate delta (default `0.05`)
- Risk Brain hard-block propagation
- replay protection and workspace isolation
- deterministic preview, baseline, record and audit digests

## Safety boundary

`committed` creates governance state and rollback lineage only. It does not activate the baseline, mutate consumers, change routing or policies, expand permissions/credentials, move funds, submit orders or execute trades.

## Next

v21.164 should add Reliability Baseline Controlled Rollout & Adoption Eligibility Governance, governing staged downstream eligibility for a committed baseline without autonomous runtime mutation.
