from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    PlanningReceiptAudit,
    PlanningReceiptCreate,
    PlanningReceiptExecuteRequest,
    PlanningReceiptRecord,
    PlanningReceiptState,
    PlanningReceiptStatus,
    ReconciliationFinding,
)


class PlanningReceiptReconciliationService:
    def __init__(self) -> None:
        self._records: dict[UUID, PlanningReceiptRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._continuity_keys: set[tuple[str, str]] = set()
        self._audit: list[PlanningReceiptAudit] = []

    def create(self, payload: PlanningReceiptCreate) -> PlanningReceiptRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail, findings, continuity_token = self._evaluate(payload)
        record = PlanningReceiptRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            findings=findings,
            continuity_token=continuity_token,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: PlanningReceiptCreate):
        if payload.upstream_risk_brain_blocked:
            return PlanningReceiptState.BLOCKED, "upstream Risk Brain hard block", [], None
        if not payload.v20_10_accepted:
            return PlanningReceiptState.EVIDENCE_REQUIRED, "accepted v20.10 handoff evidence required", [], None

        handoff = payload.handoff
        receipt = payload.receipt
        if handoff.handoff_state != "accepted-by-v20.01":
            return PlanningReceiptState.EVIDENCE_REQUIRED, "v20.10 handoff must be accepted-by-v20.01", [], None
        if not handoff.human_approved or not receipt.accepted:
            return PlanningReceiptState.EVIDENCE_REQUIRED, "human-approved handoff and accepted receipt required", [], None
        if receipt.target_module != "v20.01":
            return PlanningReceiptState.BLOCKED, "receipt target must be v20.01", [], None

        findings: list[ReconciliationFinding] = []
        self._compare(findings, "handoff_token", handoff.handoff_token, receipt.handoff_token, "critical")
        self._compare(findings, "evidence_digest", handoff.evidence_digest, receipt.evidence_digest, "critical")
        self._compare(findings, "objective", handoff.objective, receipt.objective, "high")
        self._compare(findings, "scope", self._normalized(handoff.scope), self._normalized(receipt.scope), "high")
        self._compare(
            findings,
            "acceptance_criteria",
            self._normalized(handoff.acceptance_criteria),
            self._normalized(receipt.acceptance_criteria),
            "critical",
        )
        self._compare(findings, "constraints", self._normalized(handoff.constraints), self._normalized(receipt.constraints), "critical")
        self._compare(findings, "dependencies", self._normalized(handoff.dependencies), self._normalized(receipt.dependencies), "medium")
        self._compare(findings, "priority_score", str(handoff.priority_score), str(receipt.priority_score), "medium")
        self._compare(findings, "confidence_score", str(handoff.confidence_score), str(receipt.confidence_score), "medium")
        self._compare(findings, "effort_points", str(handoff.effort_points), str(receipt.effort_points), "medium")

        if findings:
            return PlanningReceiptState.DRIFT_DETECTED, "planning receipt differs from governed handoff", findings, None

        continuity_key = (payload.workspace_id, receipt.receipt_id)
        if continuity_key in self._continuity_keys:
            return PlanningReceiptState.BLOCKED, "planning receipt already reconciled", [], None

        token_material = "|".join(
            [payload.workspace_id, handoff.handoff_record_id, receipt.receipt_id, handoff.handoff_token, handoff.evidence_digest]
        )
        continuity_token = sha256(token_material.encode("utf-8")).hexdigest()
        return PlanningReceiptState.RECONCILED, "planning receipt matches immutable v20.10 handoff", [], continuity_token

    @staticmethod
    def _normalized(values: list[str]) -> str:
        return "|".join(sorted(item.strip() for item in values))

    @staticmethod
    def _compare(findings: list[ReconciliationFinding], field: str, expected: str, actual: str, severity: str) -> None:
        if expected != actual:
            findings.append(ReconciliationFinding(field=field, expected=expected, actual=actual, severity=severity))

    def execute(self, record_id: UUID, workspace_id: str, request: PlanningReceiptExecuteRequest) -> PlanningReceiptRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("planning receipt record not found")

        if request.action == "confirm-continuity":
            if record.state != PlanningReceiptState.RECONCILED:
                raise ValueError("continuity confirmation unavailable")
            if not request.human_approved:
                raise ValueError("human approval required")
            receipt_id = record.request.receipt.receipt_id
            continuity_key = (record.workspace_id, receipt_id)
            if continuity_key in self._continuity_keys:
                raise ValueError("planning receipt already consumed")
            self._continuity_keys.add(continuity_key)
            record.state = PlanningReceiptState.CONTINUITY_CONFIRMED
            record.detail = "governance continuity confirmed for v20.01 planning cycle"
        elif request.action == "request-review":
            if record.state != PlanningReceiptState.DRIFT_DETECTED:
                raise ValueError("review request unavailable")
            record.state = PlanningReceiptState.HUMAN_REVIEW_REQUIRED
            record.detail = "planning drift requires explicit human resolution"
        elif request.action == "reject":
            record.state = PlanningReceiptState.REJECTED
            record.detail = request.resolution_note or "planning receipt rejected"
        elif request.action == "archive":
            record.state = PlanningReceiptState.ARCHIVED
            record.detail = "planning receipt reconciliation archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> PlanningReceiptRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[PlanningReceiptRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> PlanningReceiptStatus:
        records = self.list_records(workspace_id)
        blocked = {
            PlanningReceiptState.BLOCKED,
            PlanningReceiptState.EVIDENCE_REQUIRED,
            PlanningReceiptState.REJECTED,
            PlanningReceiptState.FAILED,
        }
        return PlanningReceiptStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            pending_records=sum(record.state == PlanningReceiptState.RECONCILIATION_PENDING for record in records),
            drift_records=sum(record.state in {PlanningReceiptState.DRIFT_DETECTED, PlanningReceiptState.HUMAN_REVIEW_REQUIRED} for record in records),
            reconciled_records=sum(record.state == PlanningReceiptState.RECONCILED for record in records),
            continuity_records=sum(record.state == PlanningReceiptState.CONTINUITY_CONFIRMED for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[PlanningReceiptAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: PlanningReceiptRecord, actor_id: str, action: str) -> None:
        self._audit.append(
            PlanningReceiptAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


planning_receipt_reconciliation_service = PlanningReceiptReconciliationService()
