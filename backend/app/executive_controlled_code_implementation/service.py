from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ControlledImplementationAudit,
    ControlledImplementationCreate,
    ControlledImplementationRecord,
    ControlledImplementationStatus,
    ImplementationExecuteRequest,
    ImplementationState,
    ImplementationStep,
)


class ControlledCodeImplementationService:
    PROTECTED_PREFIXES = (
        ".github/",
        "backend/app/risk",
        "backend/app/execution",
        "backend/app/broker",
        "backend/app/executive_autonomous_portfolio_governor",
    )
    FORBIDDEN_TERMS = (
        "bypass",
        "disable approval",
        "remove approval",
        "force live",
        "relax all limits",
        "ignore risk brain",
    )

    def __init__(self) -> None:
        self._records: dict[UUID, ControlledImplementationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[ControlledImplementationAudit] = []

    def create(self, payload: ControlledImplementationCreate) -> ControlledImplementationRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail, risk_level, blocked = self._evaluate(payload)
        steps = [
            ImplementationStep(order=1, name="verify-approved-plan"),
            ImplementationStep(order=2, name="verify-isolated-branch"),
            ImplementationStep(order=3, name="apply-bounded-file-changes"),
            ImplementationStep(order=4, name="run-required-tests"),
            ImplementationStep(order=5, name="review-diff-and-protected-paths"),
            ImplementationStep(order=6, name="prepare-draft-pull-request"),
        ]
        record = ControlledImplementationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            risk_level=risk_level,
            blocked_reasons=blocked,
            steps=steps,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: ControlledImplementationCreate):
        if payload.upstream_risk_brain_blocked:
            return ImplementationState.BLOCKED, "upstream Risk Brain hard block", "critical", ["risk-brain-block"]
        if not payload.plan_approved_v20_01:
            return ImplementationState.EVIDENCE_REQUIRED, "approved v20.01 plan required", "standard", ["v20.01-approval"]

        objective = payload.objective.lower()
        unsafe = [term for term in self.FORBIDDEN_TERMS if term in objective]
        if unsafe:
            return ImplementationState.BLOCKED, "unsafe code-change objective rejected", "critical", unsafe

        protected = [change.path for change in payload.changes if change.protected or change.path.startswith(self.PROTECTED_PREFIXES)]
        high_risk_words = ("risk", "execution", "broker", "live", "kill", "margin", "drawdown")
        high_risk = bool(protected) or any(word in objective for word in high_risk_words)
        risk_level = "high" if high_risk else "standard"

        if any(change.path == "main" or change.path.startswith(".git/") for change in payload.changes):
            return ImplementationState.BLOCKED, "repository control paths cannot be modified", "critical", ["repository-control-path"]
        if high_risk and not payload.human_approved:
            return ImplementationState.APPROVAL_REQUIRED, "high-risk implementation requires explicit human approval", risk_level, protected
        if not payload.human_approved:
            return ImplementationState.APPROVAL_REQUIRED, "human approval required before implementation", risk_level, []
        return ImplementationState.READY, "approved bounded implementation is ready", risk_level, []

    def execute(self, record_id: UUID, workspace_id: str, request: ImplementationExecuteRequest) -> ControlledImplementationRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("implementation record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved

        if record.state in {ImplementationState.BLOCKED, ImplementationState.EVIDENCE_REQUIRED, ImplementationState.INPUT_INVALID, ImplementationState.FAILED} and request.action not in {"archive", "fail"}:
            raise ValueError("implementation action unavailable from current state")

        if request.action == "approve":
            if not approved:
                raise ValueError("human approval required")
            record.state = ImplementationState.READY
            record.detail = "implementation approved and ready"
            record.steps[0].status = "passed"
            record.steps[0].evidence = "human and v20.01 approval verified"
        elif request.action == "start":
            if record.state != ImplementationState.READY or not approved:
                raise ValueError("approved ready state required")
            record.state = ImplementationState.APPLYING
            record.detail = "bounded changes are being applied on isolated branch"
            record.steps[1].status = "passed"
            record.steps[1].evidence = record.request.implementation_branch
            record.steps[2].status = "in-progress"
        elif request.action == "mark-tests-passed":
            if record.state != ImplementationState.APPLYING:
                raise ValueError("implementation must be applying")
            if record.request.ci_required and request.ci_passed is not True:
                raise ValueError("passing CI evidence required")
            record.commit_sha = request.commit_sha
            record.steps[2].status = "passed"
            record.steps[2].evidence = request.commit_sha or "bounded changes recorded"
            record.steps[3].status = "passed"
            record.steps[3].evidence = "required tests and CI passed"
            record.state = ImplementationState.REVIEW_REQUIRED
            record.detail = "tests passed; governed diff review required"
        elif request.action == "mark-review-passed":
            if record.state != ImplementationState.REVIEW_REQUIRED:
                raise ValueError("review-required state expected")
            if record.request.diff_review_required and request.diff_review_passed is not True:
                raise ValueError("passing diff review evidence required")
            if not request.pull_request_url:
                raise ValueError("draft pull request URL required")
            record.pull_request_url = request.pull_request_url
            record.steps[4].status = "passed"
            record.steps[4].evidence = "diff and protected-path review passed"
            record.steps[5].status = "passed"
            record.steps[5].evidence = request.pull_request_url
            record.state = ImplementationState.PR_READY
            record.detail = "draft pull request ready for human review; merge not authorized"
        elif request.action == "archive":
            record.state = ImplementationState.ARCHIVED
            record.detail = "implementation record archived"
        elif request.action == "fail":
            record.state = ImplementationState.FAILED
            record.detail = request.detail or "implementation failed and requires rollback review"

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ControlledImplementationRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ControlledImplementationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ControlledImplementationStatus:
        records = self.list_records(workspace_id)
        active = {ImplementationState.READY, ImplementationState.APPLYING, ImplementationState.TESTING}
        review = {ImplementationState.APPROVAL_REQUIRED, ImplementationState.REVIEW_REQUIRED, ImplementationState.BLOCKED, ImplementationState.EVIDENCE_REQUIRED}
        return ControlledImplementationStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            active_records=sum(record.state in active for record in records),
            review_records=sum(record.state in review for record in records),
            pr_ready_records=sum(record.state == ImplementationState.PR_READY for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[ControlledImplementationAudit]:
        return [entry for entry in self._audit if entry.workspace_id == workspace_id]

    def _log(self, record: ControlledImplementationRecord, actor_id: str, action: str) -> None:
        self._audit.append(ControlledImplementationAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


controlled_code_implementation_service = ControlledCodeImplementationService()
