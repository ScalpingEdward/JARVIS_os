from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AuthorizedMergeAudit,
    AuthorizedMergeCreate,
    AuthorizedMergeRecord,
    AuthorizedMergeStatus,
    MergeExecutionRequest,
    MergeExecutionState,
)


class AuthorizedMergeExecutorService:
    def __init__(self) -> None:
        self._records: dict[UUID, AuthorizedMergeRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[AuthorizedMergeAudit] = []

    def create(self, payload: AuthorizedMergeCreate) -> AuthorizedMergeRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail = self._evaluate(payload)
        record = AuthorizedMergeRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    @staticmethod
    def _evaluate(payload: AuthorizedMergeCreate) -> tuple[MergeExecutionState, str]:
        evidence = payload.evidence
        if payload.upstream_risk_brain_blocked:
            return MergeExecutionState.BLOCKED, "upstream Risk Brain hard block"
        if not evidence.v20_04_merge_authorized:
            return MergeExecutionState.EVIDENCE_REQUIRED, "v20.04 merge authorization required"
        if evidence.base_branch not in {"main", "master"}:
            return MergeExecutionState.BLOCKED, "merge target must be the protected default branch"
        if not evidence.ci_passed or not evidence.tests_passed:
            return MergeExecutionState.BLOCKED, "pre-merge CI and tests must pass"
        if evidence.unresolved_comments:
            return MergeExecutionState.BLOCKED, "unresolved review comments block merge"
        if not evidence.rollback_verified or not evidence.mergeable:
            return MergeExecutionState.BLOCKED, "rollback verification and mergeability required"
        if not payload.human_approved:
            return MergeExecutionState.AUTHORIZATION_PENDING, "explicit human approval required"
        return MergeExecutionState.READY, "authorization bound to PR and head commit; merge request ready"

    def execute(self, record_id: UUID, workspace_id: str, request: MergeExecutionRequest) -> AuthorizedMergeRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("merge execution record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved

        if request.action == "request-merge":
            if record.state not in {MergeExecutionState.AUTHORIZATION_PENDING, MergeExecutionState.READY}:
                raise ValueError("merge request unavailable from current state")
            if not approved:
                raise ValueError("human approval required")
            record.state = MergeExecutionState.MERGE_REQUESTED
            record.detail = "authorized merge requested; external GitHub merge action may execute"
        elif request.action == "confirm-merged":
            if record.state != MergeExecutionState.MERGE_REQUESTED:
                raise ValueError("merge confirmation unavailable")
            if not request.merge_commit_sha:
                raise ValueError("merge_commit_sha required")
            record.merge_commit_sha = request.merge_commit_sha
            record.state = MergeExecutionState.POST_MERGE_VERIFYING
            record.detail = "merge confirmed; post-merge verification required"
        elif request.action == "verify-post-merge":
            if record.state != MergeExecutionState.POST_MERGE_VERIFYING:
                raise ValueError("post-merge verification unavailable")
            if request.post_merge_ci_passed and request.post_merge_tests_passed:
                record.state = MergeExecutionState.VERIFIED
                record.detail = "post-merge CI and tests passed"
            else:
                record.state = MergeExecutionState.ROLLBACK_REQUIRED
                record.detail = "post-merge verification failed; rollback required"
        elif request.action == "mark-rollback-required":
            record.state = MergeExecutionState.ROLLBACK_REQUIRED
            record.detail = "rollback required by operator"
        elif request.action == "archive":
            record.state = MergeExecutionState.ARCHIVED
            record.detail = "merge execution archived"

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> AuthorizedMergeRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[AuthorizedMergeRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> AuthorizedMergeStatus:
        records = self.list_records(workspace_id)
        return AuthorizedMergeStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            verified_records=sum(record.state == MergeExecutionState.VERIFIED for record in records),
            rollback_records=sum(record.state == MergeExecutionState.ROLLBACK_REQUIRED for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[AuthorizedMergeAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: AuthorizedMergeRecord, actor_id: str, action: str) -> None:
        self._audit.append(AuthorizedMergeAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


authorized_merge_executor_service = AuthorizedMergeExecutorService()
