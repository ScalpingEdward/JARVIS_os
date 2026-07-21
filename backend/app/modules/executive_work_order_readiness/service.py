import hashlib
from datetime import datetime, timezone
from uuid import UUID

from .models import (
    EngineeringWorkOrder,
    WorkOrderReadinessAudit,
    WorkOrderReadinessCreate,
    WorkOrderReadinessExecuteRequest,
    WorkOrderReadinessRecord,
    WorkOrderReadinessState,
    WorkOrderReadinessStatus,
)


class WorkOrderReadinessService:
    def __init__(self) -> None:
        self._records: dict[UUID, WorkOrderReadinessRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._continuity_tokens: set[tuple[str, str]] = set()
        self._engineering_receipts: set[tuple[str, str]] = set()
        self._audit: list[WorkOrderReadinessAudit] = []

    def create(self, payload: WorkOrderReadinessCreate) -> WorkOrderReadinessRecord:
        source_key = (payload.workspace_id, payload.source_key)
        continuity_key = (payload.workspace_id, payload.evidence.continuity_token)
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        if continuity_key in self._continuity_tokens:
            raise ValueError("continuity token already consumed")

        state, detail, work_order, score = self._evaluate(payload)
        record = WorkOrderReadinessRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            work_order=work_order,
            readiness_score=score,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._continuity_tokens.add(continuity_key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: WorkOrderReadinessCreate):
        evidence = payload.evidence
        if payload.upstream_risk_brain_blocked:
            return WorkOrderReadinessState.BLOCKED, "upstream Risk Brain hard block", None, 0
        if not payload.v20_11_continuity_confirmed:
            return WorkOrderReadinessState.EVIDENCE_REQUIRED, "v20.11 continuity confirmation required", None, 0
        if evidence.reconciliation_state != "continuity-confirmed":
            return WorkOrderReadinessState.EVIDENCE_REQUIRED, "reconciliation record must be continuity-confirmed", None, 0
        if not evidence.human_approved:
            return WorkOrderReadinessState.HUMAN_REVIEW_REQUIRED, "upstream human approval evidence required", None, 20
        if not evidence.scope or not evidence.acceptance_criteria or not evidence.constraints:
            return WorkOrderReadinessState.EVIDENCE_REQUIRED, "scope, acceptance criteria and constraints are mandatory", None, 25

        unresolved = [item for item in evidence.dependencies if not payload.dependency_status.get(item, False)]
        if unresolved:
            return WorkOrderReadinessState.DEPENDENCY_BLOCKED, f"unresolved dependencies: {', '.join(unresolved)}", None, 40

        score = min(100.0, round(
            30
            + min(len(evidence.acceptance_criteria) * 8, 24)
            + min(len(evidence.constraints) * 5, 15)
            + evidence.confidence_score * 0.2
            + (11 if not evidence.dependencies else 6),
            2,
        ))
        work_order = EngineeringWorkOrder(
            objective=evidence.objective,
            scope=evidence.scope,
            acceptance_criteria=evidence.acceptance_criteria,
            constraints=evidence.constraints,
            dependencies=evidence.dependencies,
            priority_score=evidence.priority_score,
            confidence_score=evidence.confidence_score,
            effort_points=evidence.effort_points,
            continuity_token=evidence.continuity_token,
            evidence_digest=evidence.evidence_digest,
        )
        return WorkOrderReadinessState.HUMAN_REVIEW_REQUIRED, "engineering work order prepared; explicit issuance approval required", work_order, score

    def execute(self, record_id: UUID, workspace_id: str, request: WorkOrderReadinessExecuteRequest) -> WorkOrderReadinessRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("work order readiness record not found")

        if request.action == "approve-readiness":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != WorkOrderReadinessState.HUMAN_REVIEW_REQUIRED or record.work_order is None:
                raise ValueError("readiness approval unavailable")
            record.state = WorkOrderReadinessState.READY
            record.detail = "engineering work order readiness approved"
        elif request.action == "issue":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != WorkOrderReadinessState.READY:
                raise ValueError("work order is not ready")
            raw = f"{workspace_id}:{record.id}:{record.request.evidence.continuity_token}:{record.request.evidence.evidence_digest}"
            record.issuance_token = hashlib.sha256(raw.encode()).hexdigest()
            record.state = WorkOrderReadinessState.ISSUED
            record.detail = "governed engineering work order issued"
        elif request.action == "accept":
            if record.state != WorkOrderReadinessState.ISSUED:
                raise ValueError("issued work order required")
            if not request.engineering_receipt_id:
                raise ValueError("engineering receipt required")
            receipt_key = (workspace_id, request.engineering_receipt_id)
            if receipt_key in self._engineering_receipts:
                raise ValueError("engineering receipt already consumed")
            self._engineering_receipts.add(receipt_key)
            record.state = WorkOrderReadinessState.ACCEPTED_BY_ENGINEERING
            record.detail = "engineering execution workflow accepted work order"
        elif request.action == "reject":
            record.state = WorkOrderReadinessState.REJECTED
            record.detail = "engineering work order rejected"
        elif request.action == "archive":
            record.state = WorkOrderReadinessState.ARCHIVED
            record.detail = "work order readiness record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> WorkOrderReadinessRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[WorkOrderReadinessRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> WorkOrderReadinessStatus:
        records = self.list_records(workspace_id)
        blocked = {
            WorkOrderReadinessState.BLOCKED,
            WorkOrderReadinessState.EVIDENCE_REQUIRED,
            WorkOrderReadinessState.DEPENDENCY_BLOCKED,
            WorkOrderReadinessState.REJECTED,
            WorkOrderReadinessState.FAILED,
        }
        return WorkOrderReadinessStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state == WorkOrderReadinessState.READY for record in records),
            issued_records=sum(record.state == WorkOrderReadinessState.ISSUED for record in records),
            accepted_records=sum(record.state == WorkOrderReadinessState.ACCEPTED_BY_ENGINEERING for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[WorkOrderReadinessAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: WorkOrderReadinessRecord, actor_id: str, action: str) -> None:
        self._audit.append(WorkOrderReadinessAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


work_order_readiness_service = WorkOrderReadinessService()
