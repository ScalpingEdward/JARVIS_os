from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ControlledDeploymentAudit,
    ControlledDeploymentCreate,
    ControlledDeploymentRecord,
    ControlledDeploymentStatus,
    DeploymentExecuteRequest,
    DeploymentState,
    DeploymentStep,
)


class ControlledDeploymentService:
    def __init__(self) -> None:
        self._records: dict[UUID, ControlledDeploymentRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[ControlledDeploymentAudit] = []

    def create(self, payload: ControlledDeploymentCreate) -> ControlledDeploymentRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail = self._evaluate(payload)
        record = ControlledDeploymentRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            rollback_target_sha=payload.evidence.merge_commit_sha,
            steps=self._steps(),
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    @staticmethod
    def _evaluate(payload: ControlledDeploymentCreate) -> tuple[DeploymentState, str]:
        evidence = payload.evidence
        if payload.upstream_risk_brain_blocked:
            return DeploymentState.BLOCKED, "upstream Risk Brain hard block"
        if not evidence.v20_05_verified:
            return DeploymentState.EVIDENCE_REQUIRED, "v20.05 verified merge evidence required"
        required = (
            evidence.pre_deploy_ci_passed,
            evidence.tests_passed,
            evidence.secrets_validated,
            evidence.migrations_validated,
            evidence.rollback_verified,
        )
        if not all(required):
            return DeploymentState.BLOCKED, "deployment prerequisites are incomplete"
        if not payload.human_approved:
            return DeploymentState.APPROVAL_REQUIRED, "human deployment approval required"
        return DeploymentState.READY, "deployment plan approved and ready"

    def execute(self, record_id: UUID, workspace_id: str, request: DeploymentExecuteRequest) -> ControlledDeploymentRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("deployment record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved
        if request.action == "approve":
            if record.state != DeploymentState.APPROVAL_REQUIRED or not approved:
                raise ValueError("deployment approval unavailable")
            record.state, record.detail = DeploymentState.READY, "deployment approved"
        elif request.action == "start-deployment":
            if record.state != DeploymentState.READY or not approved:
                raise ValueError("deployment start unavailable")
            record.state, record.detail = DeploymentState.DEPLOYING, "controlled deployment started"
            record.deployed_commit_sha = record.request.evidence.merge_commit_sha
            for step in record.steps[:4]:
                step.status = "completed"
        elif request.action == "verify-runtime":
            if record.state not in {DeploymentState.DEPLOYING, DeploymentState.RUNTIME_VERIFYING}:
                raise ValueError("runtime verification unavailable")
            record.state = DeploymentState.RUNTIME_VERIFYING
            health = request.runtime_health_passed if request.runtime_health_passed is not None else record.request.evidence.runtime_health_passed
            smoke = request.smoke_tests_passed if request.smoke_tests_passed is not None else record.request.evidence.smoke_tests_passed
            error_rate = request.error_rate_pct if request.error_rate_pct is not None else record.request.evidence.error_rate_pct
            latency = request.p95_latency_ms if request.p95_latency_ms is not None else record.request.evidence.p95_latency_ms
            if health and smoke and error_rate <= record.request.max_error_rate_pct and latency <= record.request.max_p95_latency_ms:
                record.state, record.detail = DeploymentState.HEALTHY, "runtime health and smoke verification passed"
                for step in record.steps:
                    step.status = "completed"
            else:
                record.state, record.detail = DeploymentState.ROLLBACK_REQUIRED, "runtime verification failed; rollback required"
        elif request.action == "start-rollback":
            if record.state != DeploymentState.ROLLBACK_REQUIRED:
                raise ValueError("rollback unavailable")
            record.state, record.detail = DeploymentState.ROLLING_BACK, "rollback started"
        elif request.action == "complete-rollback":
            if record.state != DeploymentState.ROLLING_BACK:
                raise ValueError("rollback completion unavailable")
            record.state, record.detail = DeploymentState.ROLLED_BACK, "rollback completed and release isolated"
        elif request.action == "archive":
            record.state, record.detail = DeploymentState.ARCHIVED, "deployment record archived"
        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ControlledDeploymentRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ControlledDeploymentRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ControlledDeploymentStatus:
        records = self.list_records(workspace_id)
        rollback = {DeploymentState.ROLLBACK_REQUIRED, DeploymentState.ROLLING_BACK, DeploymentState.ROLLED_BACK}
        return ControlledDeploymentStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            healthy_records=sum(record.state == DeploymentState.HEALTHY for record in records),
            rollback_records=sum(record.state in rollback for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[ControlledDeploymentAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    @staticmethod
    def _steps() -> list[DeploymentStep]:
        return [
            DeploymentStep(name="validate-artifact"),
            DeploymentStep(name="validate-secrets"),
            DeploymentStep(name="validate-migrations"),
            DeploymentStep(name="deploy-release"),
            DeploymentStep(name="runtime-health-check"),
            DeploymentStep(name="smoke-tests"),
        ]

    def _log(self, record: ControlledDeploymentRecord, actor_id: str, action: str) -> None:
        self._audit.append(ControlledDeploymentAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


controlled_deployment_service = ControlledDeploymentService()
