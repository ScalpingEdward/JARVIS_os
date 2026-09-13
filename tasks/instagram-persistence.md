# Instagram durable storage

Status: REVIEW (implementation complete; merge and deployment verification pending)

Source: owner handoff in `docs/SESSION_2026-09-13.md` and the request to
continue from commit `e760fbc4` with persistence first.

## Scope

Make the existing SQLAlchemy-backed Instagram pool, drafts, and candidates
use the database configured by Docker. Preserve the prefixed configuration
used by native installations and tests. No publishing or credential changes.

## Acceptance criteria

- `DATABASE_URL` from the shipped Compose setup is honored.
- `JARVIS_DATABASE_URL` remains supported and takes precedence when both
  environment variables are present.
- Pool items, source groups, reservations, finalized drafts, candidate
  decisions and published receipts survive a new Python process using the
  same database from a different working directory.
- An ingest of an existing `media_ref` remains a duplicate after restart.
- Existing container-local SQLite data has a documented backup and
  preservation path before the API container is recreated.

## Dependencies and next task

Unblocked: existing Instagram database tables and service persistence are
already on `main`. After merge, verify the owner's deployment and then
implement explicit recovery for rejected/uncertain publishing states.

## Result

- `Settings` now accepts both database URL names; the original native
  default and explicit constructor arguments remain supported.
- Nine new regressions pass. Before the fix, three failed, including the
  real process/workdir replacement test with `DATABASE_URL`.
- Full backend CI command from `backend/`: 2,855 tests passed.
- Ruff formatting/lint checks and mypy checks cover the changed Python
  files. The SQLite preservation procedure was also exercised locally
  with an integrity check and an overwrite refusal.
- Deployment examples and `docs/instagram-persistence.md` document the
  existing-data preservation path. No production migration was performed.
- No runtime dependency or external integration was added. Actual Docker
  volume bindings and the owner's current records still need operator
  verification before replacing their running container.
