from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    EnterpriseRiskActionRequest,
    EnterpriseRiskCreate,
    EnterpriseRiskGovernanceRecord,
    EnterpriseRiskState,
    RiskDecision,
    RiskLevel,
)


class EnterpriseRiskGovernanceError(RuntimeError):
    pass


class EnterpriseRiskGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, EnterpriseRiskGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: EnterpriseRiskCreate) -> EnterpriseRiskGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise EnterpriseRiskGovernanceError("duplicate source key")
        record = EnterpriseRiskGovernanceRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> EnterpriseRiskGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise EnterpriseRiskGovernanceError("enterprise risk record not found")
        return record

    def list(self, workspace_id: str) -> list[EnterpriseRiskGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: EnterpriseRiskActionRequest) -> EnterpriseRiskGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, EnterpriseRiskState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = EnterpriseRiskState.BLOCKED
            elif not record.enterprise_risk_evidence_refs:
                raise EnterpriseRiskGovernanceError("enterprise risk evidence is required")
            else:
                record.state = EnterpriseRiskState.EVIDENCE_READY
        elif action == "aggregate":
            self._require(record, EnterpriseRiskState.EVIDENCE_READY)
            self._refresh(record)
            appetite_breach = any(item.current_exposure > item.risk_appetite_limit for item in record.risks)
            weak_control = any(item.control_effectiveness < record.minimum_control_effectiveness for item in record.risks)
            breached = (
                appetite_breach
                or weak_control
                or record.aggregate_exposure > record.maximum_aggregate_exposure
                or record.critical_risks > record.maximum_critical_risks
            )
            record.state = EnterpriseRiskState.ESCALATED if breached else EnterpriseRiskState.AGGREGATED
        elif action == "prepare-board-pack":
            self._require(record, EnterpriseRiskState.AGGREGATED)
            if any(item.confidence < record.minimum_decision_confidence for item in record.board_decisions):
                raise EnterpriseRiskGovernanceError("board decision confidence below threshold")
            record.state = EnterpriseRiskState.BOARD_PACK_PREPARED
        elif action == "request-review":
            self._require(record, EnterpriseRiskState.BOARD_PACK_PREPARED)
            record.state = EnterpriseRiskState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, EnterpriseRiskState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = EnterpriseRiskState.APPROVED
        elif action == "present":
            self._require(record, EnterpriseRiskState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.board_evidence_refs.extend(request.evidence_refs)
            record.state = EnterpriseRiskState.PRESENTED
        elif action == "record-cycle":
            if record.state not in {EnterpriseRiskState.PRESENTED, EnterpriseRiskState.MONITORING}:
                raise EnterpriseRiskGovernanceError("board oversight monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.board_evidence_refs.extend(request.evidence_refs)
            if request.observed_aggregate_exposure is not None:
                record.aggregate_exposure = request.observed_aggregate_exposure
            if request.observed_critical_risks is not None:
                record.critical_risks = request.observed_critical_risks
            healthy = (
                bool(request.cycle_healthy)
                and record.aggregate_exposure <= record.maximum_aggregate_exposure
                and record.critical_risks <= record.maximum_critical_risks
            )
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = EnterpriseRiskState.MONITORING if healthy else EnterpriseRiskState.ESCALATED
        elif action == "verify":
            self._require(record, EnterpriseRiskState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise EnterpriseRiskGovernanceError("insufficient healthy monitoring cycles")
            record.state = EnterpriseRiskState.VERIFIED
        elif action == "escalate":
            record.state = EnterpriseRiskState.ESCALATED
        elif action == "suspend":
            if record.state in {EnterpriseRiskState.REVOKED, EnterpriseRiskState.ARCHIVED}:
                raise EnterpriseRiskGovernanceError("record cannot be suspended")
            record.state = EnterpriseRiskState.SUSPENDED
        elif action == "resume":
            self._require(record, EnterpriseRiskState.SUSPENDED)
            record.state = EnterpriseRiskState.MONITORING
        elif action == "revoke":
            if record.state == EnterpriseRiskState.ARCHIVED:
                raise EnterpriseRiskGovernanceError("archived record cannot be revoked")
            record.state = EnterpriseRiskState.REVOKED
        elif action == "archive":
            if record.state not in {EnterpriseRiskState.VERIFIED, EnterpriseRiskState.REVOKED}:
                raise EnterpriseRiskGovernanceError("only verified or revoked records can be archived")
            record.state = EnterpriseRiskState.ARCHIVED
        else:
            raise EnterpriseRiskGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request.model_dump(exclude_none=True))
        return record

    @staticmethod
    def _refresh(record: EnterpriseRiskGovernanceRecord) -> None:
        record.aggregate_exposure = sum(item.current_exposure for item in record.risks)
        record.critical_risks = sum(item.level == RiskLevel.CRITICAL for item in record.risks)

    @staticmethod
    def _require(record: EnterpriseRiskGovernanceRecord, state: EnterpriseRiskState) -> None:
        if record.state != state:
            raise EnterpriseRiskGovernanceError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise EnterpriseRiskGovernanceError(f"{label} is required")
        if value in store:
            raise EnterpriseRiskGovernanceError(f"{label} already consumed")
        store.add(value)

    def _emit(self, record: EnterpriseRiskGovernanceRecord, action: str, actor: str, before: EnterpriseRiskState | None, after: EnterpriseRiskState, details: dict | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))


service = EnterpriseRiskGovernanceService()
