# Agent Operating Contract

## Mission
Build JARVIS OS incrementally according to the master plan. Preserve provider independence, security boundaries, testability, portability, and user ownership.

## Required workflow
1. Read all governing documents before editing.
2. Select only an unblocked task marked `READY`.
3. Create a dedicated branch and pull request.
4. Make the smallest coherent change that satisfies the task.
5. Run formatting, type checks, unit tests, and security-relevant checks.
6. Update documentation and task status.
7. Never merge your own pull request unless an explicit policy permits it.

## Prohibited autonomous actions
- Production deployment
- Real trading orders
- Sending external email or messages
- Spending money or enabling paid services
- Deleting production data
- Rotating or exposing secrets
- Weakening approval, audit, or security controls
- Changing architecture without an ADR and explicit approval

## Agent roles
- **Master/Orchestrator:** breaks approved goals into tasks, tracks dependencies, assigns workers, and reports progress.
- **Architect:** specifications, ADRs, boundaries, technical review.
- **Implementer:** code, schemas, migrations, integrations.
- **Test Agent:** unit, integration, regression, and adversarial tests.
- **Security Reviewer:** permissions, secrets, prompt injection, dependencies, supply chain.
- **Release Agent:** packaging and release notes; no production deployment.

## Completion report
Every task result must include:
- changed files
- tests and checks run
- results
- unresolved risks
- decisions required from the owner
- suggested next task
