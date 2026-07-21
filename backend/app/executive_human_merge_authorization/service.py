from datetime import datetime, timezone
from uuid import UUID

from .models import (
    MergeAuthorizationAudit,
    MergeAuthorizationCreate,
    MergeAuthorizationExecuteRequest,
    MergeAuthorizationRecord,
    MergeAuthorizationState,
    MergeAuthorizationStatus,
)


class HumanMergeAuthorizationService:
    def __init__(self) -> None:
        self._records: dict[UUID, MergeAuthorizationRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[MergeAuthorizationAudit] = []

    def create(self, payload: MergeAuthorizationCreate) -> MergeAuthorizationRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail = self._evaluate(payload)
        record = MergeAuthorizationRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            release_candidate_id=f"rc-{payload.evidence.pull_request_number}-{payload.evidence.head_commit_sha[:8]}",
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    @staticmethod
    def _evaluate(payload: MergeAuthorizationCreate):
        evidence = payload.evidence
        if payload.upstream_risk_brain_blocked:
            return MergeAuthorizationState.BLOCKED, "upstream Risk Brain hard block"
        if not evidence.v20_03_merge_recommended:
            return MergeAuthorizationState.EVIDENCE_REQUIRED, "v20.03 merge recommendation required"
        if not evidence.ci_passed or not evidence.tests_passed:
            return MergeAuthorizationState.BLOCKED, "CI and tests must pass"
        if evidence.critical_findings or evidence.unresolved_comments:
            return MergeAuthorizationState.BLOCKED, "critical findings and unresolved comments must be cleared"
        if not evidence.diff_reviewed or not evidence.rollback_verified:
            return MergeAuthorizationState.EVIDENCE_REQUIRED, "diff review and rollback verification required"
        if evidence.protected_paths_changed or evidence.risk_or_execution_changed:
            return MergeAuthorizationState.HUMAN_REVIEW_REQUIRED, "sensitive changes require explicit human review"
        if payload.human_approved:
            return MergeAuthorizationState.RELEASE_CANDIDATE, "release candidate approved for final merge authorization"
        return MergeAuthorizationState.AUTHORIZATION_PENDING, "human authorization required"

    def execute(self, record_id: UUID, workspace_id: str, request: MergeAuthorizationExecuteRequest) -> MergeAuthorizationRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("merge authorization record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action == "confirm-review":
            if not approved:
                raise ValueError("human approval required")
            if record.state not in {MergeAuthorizationState.HUMAN_REVIEW_REQUIRED, MergeAuthorizationState.AUTHORIZATION_PENDING}:
                raise ValueError("review confirmation unavailable")
            record.state = MergeAuthorizationState.RELEASE_CANDIDATE
            record.detail = "human review confirmed; release candidate ready"
        elif request.action == "authorize-merge":
            if not approved or not request.confirmation_token:
                raise ValueError("explicit human approval and confirmation token required")
            if record.state != MergeAuthorizationState.RELEASE_CANDIDATE:
                raise ValueError("merge authorization unavailable")
            record.state = MergeAuthorizationState.MERGE_AUTHORIZED
            record.merge_authorized = True
            record.detail = "merge explicitly authorized; execution remains external"
        elif request.action == "reject-merge":
            record.state = MergeAuthorizationState.MERGE_REJECTED
            record.merge_authorized = False
            record.detail = "merge rejected"
        elif request.action == "expire":
            record.state = MergeAuthorizationState.EXPIRED
            record.merge_authorized = False
            record.detail = "merge authorization expired"
        elif request.action == "archive":
            record.state = MergeAuthorizationState.ARCHIVED
            record.detail = "merge authorization archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> MergeAuthorizationRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[MergeAuthorizationRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> MergeAuthorizationStatus:
        records = self.list_records(workspace_id)
        blocked = {MergeAuthorizationState.BLOCKED, MergeAuthorizationState.EVIDENCE_REQUIRED, MergeAuthorizationState.MERGE_REJECTED, MergeAuthorizationState.EXPIRED}
        return MergeAuthorizationStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            authorized_records=sum(record.state == MergeAuthorizationState.MERGE_AUTHORIZED for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[MergeAuthorizationAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: MergeAuthorizationRecord, actor_id: str, action: str) -> None:
        self._audit.append(MergeAuthorizationAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


human_merge_authorization_service = HumanMergeAuthorizationService()
