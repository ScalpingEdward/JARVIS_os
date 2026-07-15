# Definition of Done

A task is complete only when all applicable conditions are satisfied.

## Scope
- Acceptance criteria are met without unrelated changes.
- Architecture and security rules remain intact.
- Any intentional architectural decision has an ADR.

## Quality
- Code is formatted and type-checked where applicable.
- Unit tests cover new logic.
- Integration tests cover changed boundaries.
- Existing tests pass.
- Failure paths and timeouts are handled.

## Security
- No secrets or personal data are committed.
- Permissions follow least privilege.
- External input is validated.
- New dependencies have documented license and security rationale.

## Documentation
- Setup and usage instructions are updated.
- Configuration changes are reflected in examples.
- Important decisions and limitations are documented.

## Delivery
- Work is committed on a dedicated branch.
- A pull request explains changes, tests, risks, and follow-up work.
- Critical actions have recorded owner approval.
- The result is portable and reproducible on a clean environment.
