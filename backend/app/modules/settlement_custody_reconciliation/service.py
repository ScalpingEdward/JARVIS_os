from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, RiskDecision, SettlementActionRequest, SettlementCreate, SettlementGovernanceRecord, SettlementState, SettlementStatus


class SettlementGovernanceError(RuntimeError):
    pass


class SettlementGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, SettlementGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: SettlementCreate) -> SettlementGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise SettlementGovernanceError("duplicate source key")
        record = SettlementGovernanceRecord(**payload.model_dump())
        record.unreconciled_value = self._calculate_unreconciled(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> SettlementGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise SettlementGovernanceError("settlement governance record not found")
        return record

    def list(self, workspace_id: str) -> list[SettlementGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: SettlementActionRequest) -> SettlementGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, SettlementState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = SettlementState.BLOCKED
            elif not record.settlement_evidence_refs:
                raise SettlementGovernanceError("settlement evidence is required")
            else:
                record.state = SettlementState.EVIDENCE_READY
        elif action == "evaluate":
            self._require(record, SettlementState.EVIDENCE_READY)
            if self._has_fee_violation(record) or record.unreconciled_value > record.maximum_unreconciled_value:
                record.state = SettlementState.ESCALATED
            else:
                record.state = SettlementState.EVALUATED
        elif action == "propose-reconciliation":
            self._require(record, SettlementState.EVALUATED)
            known = {item.instruction_id: item for item in record.instructions}
            if not request.instruction_ids or not set(request.instruction_ids).issubset(known):
                raise SettlementGovernanceError("known instruction_ids are required")
            if any(known[item].confidence < record.minimum_confidence for item in request.instruction_ids):
                raise SettlementGovernanceError("reconciliation confidence below threshold")
            record.selected_instruction_ids = list(dict.fromkeys(request.instruction_ids))
            record.state = SettlementState.RECONCILIATION_PROPOSED
        elif action == "request-review":
            self._require(record, SettlementState.RECONCILIATION_PROPOSED)
            record.state = SettlementState.HUMAN_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, SettlementState.HUMAN_REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = SettlementState.APPROVED
        elif action == "start-settlement":
            self._require(record, SettlementState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = SettlementState.SETTLING
        elif action == "record-settlement":
            self._require(record, SettlementState.SETTLING)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            item = self._settlement(record, request.settlement_id)
            if request.settlement_status is None:
                raise SettlementGovernanceError("settlement_status is required")
            item.status = request.settlement_status
            item.actual_fee = request.actual_fee
            record.reconciliation_evidence_refs.extend(request.evidence_refs)
            if item.status in {SettlementStatus.FAILED, SettlementStatus.REVERSED} or self._fee_variance(item) > record.maximum_fee_variance:
                record.state = SettlementState.ESCALATED
        elif action == "start-reconciliation":
            self._require(record, SettlementState.SETTLING)
            if any(item.status == SettlementStatus.PENDING for item in record.settlements):
                raise SettlementGovernanceError("all settlements must be terminal")
            if any(item.status != SettlementStatus.SETTLED for item in record.settlements):
                raise SettlementGovernanceError("failed or reversed settlement requires escalation")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = SettlementState.RECONCILING
        elif action == "record-cycle":
            self._require(record, SettlementState.RECONCILING)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.reconciliation_evidence_refs.extend(request.evidence_refs)
            if request.unreconciled_value is not None:
                record.unreconciled_value = request.unreconciled_value
            if record.unreconciled_value > record.maximum_unreconciled_value or not request.cycle_healthy:
                record.consecutive_healthy_cycles = 0
                record.state = SettlementState.ESCALATED
            else:
                record.consecutive_healthy_cycles += 1
        elif action == "confirm-reconciled":
            self._require(record, SettlementState.RECONCILING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise SettlementGovernanceError("healthy reconciliation cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = SettlementState.RECONCILED
        elif action == "escalate":
            if record.state in {SettlementState.BLOCKED, SettlementState.ARCHIVED, SettlementState.REVOKED}:
                raise SettlementGovernanceError("escalation not allowed")
            record.state = SettlementState.ESCALATED
        elif action == "suspend":
            if record.state not in {SettlementState.APPROVED, SettlementState.SETTLING, SettlementState.RECONCILING, SettlementState.ESCALATED}:
                raise SettlementGovernanceError("suspension not allowed")
            record.state = SettlementState.SUSPENDED
        elif action == "resume":
            self._require(record, SettlementState.SUSPENDED)
            record.state = SettlementState.RECONCILING
        elif action == "revoke":
            if record.state in {SettlementState.ARCHIVED, SettlementState.REVOKED, SettlementState.BLOCKED}:
                raise SettlementGovernanceError("revocation not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = SettlementState.REVOKED
        elif action == "archive":
            if record.state not in {SettlementState.RECONCILED, SettlementState.REVOKED, SettlementState.ESCALATED}:
                raise SettlementGovernanceError("archive not allowed")
            record.state = SettlementState.ARCHIVED
        else:
            raise SettlementGovernanceError("unsupported action")

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state)
        return record

    @staticmethod
    def _calculate_unreconciled(record: SettlementGovernanceRecord) -> float:
        return sum(max(0.0, abs(item.internal_quantity - item.external_quantity) - item.tolerance) for item in record.positions)

    @staticmethod
    def _fee_variance(item) -> float:
        if item.actual_fee is None:
            return 0
        if item.expected_fee == 0:
            return 0 if item.actual_fee == 0 else 1
        return abs(item.actual_fee - item.expected_fee) / item.expected_fee

    def _has_fee_violation(self, record: SettlementGovernanceRecord) -> bool:
        return any(self._fee_variance(item) > record.maximum_fee_variance for item in record.settlements)

    @staticmethod
    def _settlement(record: SettlementGovernanceRecord, settlement_id: str | None):
        for item in record.settlements:
            if item.settlement_id == settlement_id:
                return item
        raise SettlementGovernanceError("known settlement_id is required")

    @staticmethod
    def _require(record: SettlementGovernanceRecord, state: SettlementState) -> None:
        if record.state != state:
            raise SettlementGovernanceError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise SettlementGovernanceError(f"{label} is required")
        if value in store:
            raise SettlementGovernanceError(f"{label} already consumed")
        store.add(value)

    @staticmethod
    def _touch(record: SettlementGovernanceRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record, action, actor, before, after) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after))


service = SettlementGovernanceService()
