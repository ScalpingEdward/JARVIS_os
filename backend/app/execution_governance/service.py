from datetime import datetime, timezone
from threading import RLock
from uuid import UUID

from .models import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequest,
    AuditRecord,
    ExecutionRelease,
    GateResult,
    GateState,
    GateType,
    GovernanceStatus,
    ReleaseCreate,
    ReleaseStatus,
    ReleaseValidation,
)


class ExecutionGovernanceService:
    def __init__(self) -> None:
        self._records: dict[UUID, ExecutionRelease] = {}
        self._audit: list[AuditRecord] = []
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _write_audit(self, workspace_id: str, action: str, actor_id: str, release_id: UUID | None = None, details: dict | None = None) -> None:
        self._audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, release_id=release_id, details=details or {}, created_at=self._now()))

    def create(self, payload: ReleaseCreate) -> ExecutionRelease:
        now = self._now()
        record = ExecutionRelease(**payload.model_dump(), created_at=now, updated_at=now)
        with self._lock:
            if any(item.workspace_id == payload.workspace_id and item.title == payload.title for item in self._records.values()):
                raise ValueError("A release with this title already exists in the workspace")
            self._records[record.id] = record
            self._write_audit(payload.workspace_id, "release-created", payload.owner_id, record.id)
        return record

    def list_records(self, workspace_id: str) -> list[ExecutionRelease]:
        with self._lock:
            return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, release_id: UUID, workspace_id: str) -> ExecutionRelease | None:
        with self._lock:
            record = self._records.get(release_id)
            return record if record and record.workspace_id == workspace_id else None

    def validate(self, release_id: UUID, workspace_id: str, actor_id: str) -> ExecutionRelease:
        with self._lock:
            record = self._records.get(release_id)
            if record is None or record.workspace_id != workspace_id:
                raise KeyError("Release not found")

            results = [GateResult(key=gate.key, gate_type=gate.gate_type, state=GateState.passed if gate.passed else GateState.failed, blocking=gate.blocking, explanation=gate.explanation or ("Gate passed" if gate.passed else "Gate failed"), evidence=gate.evidence) for gate in record.gates]
            checklist_complete = set(record.checklist_items).issubset(set(record.completed_checklist_items))
            rollback_ready = bool(record.rollback_steps)
            dry_run_ready = record.dry_run_completed

            synthetic = [
                GateResult(key="change-freeze", gate_type=GateType.change_freeze, state=GateState.failed if record.change_freeze_active else GateState.passed, blocking=True, explanation="Active change freeze blocks release" if record.change_freeze_active else "No active change freeze", evidence=[]),
                GateResult(key="rollback-readiness", gate_type=GateType.rollback, state=GateState.passed if rollback_ready else GateState.failed, blocking=True, explanation="Rollback plan available" if rollback_ready else "Rollback plan missing", evidence=record.rollback_steps),
                GateResult(key="dry-run", gate_type=GateType.dry_run, state=GateState.passed if dry_run_ready else GateState.failed, blocking=True, explanation="Dry run completed" if dry_run_ready else "Dry run not completed", evidence=[]),
                GateResult(key="checklist", gate_type=GateType.checklist, state=GateState.passed if checklist_complete else GateState.failed, blocking=True, explanation="Checklist complete" if checklist_complete else "Checklist incomplete", evidence=record.completed_checklist_items),
            ]
            results.extend(synthetic)
            blocking = [item.explanation for item in results if item.blocking and item.state == GateState.failed]
            warnings = [item.explanation for item in results if not item.blocking and item.state != GateState.passed]
            passed = sum(item.state == GateState.passed for item in results)
            readiness = round((passed / len(results) * 100) if results else 100.0, 2)
            validation = ReleaseValidation(validated_at=self._now(), gate_results=results, readiness_score=readiness, blocking_reasons=blocking, warnings=warnings, rollback_ready=rollback_ready, dry_run_ready=dry_run_ready, checklist_complete=checklist_complete, emergency_stop_ready=record.emergency_stop_ready)
            next_status = ReleaseStatus.blocked if blocking else ReleaseStatus.pending_approval
            updated = record.model_copy(update={"validation": validation, "status": next_status, "updated_at": self._now()})
            self._records[release_id] = updated
            self._write_audit(workspace_id, "release-validated", actor_id, release_id, {"blocking_reasons": len(blocking), "readiness_score": readiness})
            return updated

    def approve(self, release_id: UUID, payload: ApprovalRequest) -> ExecutionRelease:
        with self._lock:
            record = self._records.get(release_id)
            if record is None or record.workspace_id != payload.workspace_id:
                raise KeyError("Release not found")
            if record.validation is None:
                raise ValueError("Release must be validated before approval")
            if record.validation.blocking_reasons:
                raise ValueError("Blocked releases cannot be approved")
            if payload.reviewer_id == record.owner_id:
                raise ValueError("Release owners cannot approve their own release")
            stage = next((item for item in record.approval_stages if item.key == payload.stage_key), None)
            if stage is None:
                raise ValueError("Unknown approval stage")
            if stage.approver_roles and payload.reviewer_role not in stage.approver_roles:
                raise ValueError("Reviewer role is not allowed for this stage")
            if any(item.stage_key == payload.stage_key and item.reviewer_id == payload.reviewer_id for item in record.approvals):
                raise ValueError("Reviewer has already decided this stage")

            approvals = [*record.approvals, ApprovalRecord(stage_key=payload.stage_key, reviewer_id=payload.reviewer_id, reviewer_role=payload.reviewer_role, decision=payload.decision, reason=payload.reason, created_at=self._now())]
            if payload.decision == ApprovalDecision.reject:
                next_status = ReleaseStatus.rejected
            else:
                complete = all(sum(item.stage_key == stage_item.key and item.decision == ApprovalDecision.approve for item in approvals) >= stage_item.required_approvals for stage_item in record.approval_stages)
                next_status = ReleaseStatus.approved if complete else ReleaseStatus.pending_approval
            updated = record.model_copy(update={"approvals": approvals, "status": next_status, "updated_at": self._now()})
            self._records[release_id] = updated
            self._write_audit(payload.workspace_id, f"release-{payload.decision.value}d", payload.reviewer_id, release_id, {"stage": payload.stage_key})
            return updated

    def status(self, workspace_id: str) -> GovernanceStatus:
        records = self.list_records(workspace_id)
        return GovernanceStatus(releases=len(records), pending_approval=sum(item.status == ReleaseStatus.pending_approval for item in records), approved=sum(item.status == ReleaseStatus.approved for item in records), blocked=sum(item.status == ReleaseStatus.blocked for item in records))

    def audit_records(self, workspace_id: str) -> list[AuditRecord]:
        with self._lock:
            return [item for item in self._audit if item.workspace_id == workspace_id]


execution_governance_service = ExecutionGovernanceService()
