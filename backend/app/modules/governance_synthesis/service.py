from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    GovernanceActionRequest,
    GovernanceState,
    GovernanceSynthesisCreate,
    GovernanceSynthesisRecord,
    RiskDecision,
)


class GovernanceSynthesisError(RuntimeError):
    pass


class GovernanceSynthesisService:
    def __init__(self) -> None:
        self._records: dict[str, GovernanceSynthesisRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: GovernanceSynthesisCreate) -> GovernanceSynthesisRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise GovernanceSynthesisError("duplicate source key")
        record = GovernanceSynthesisRecord(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> GovernanceSynthesisRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise GovernanceSynthesisError("governance synthesis record not found")
        return record

    def list(self, workspace_id: str) -> list[GovernanceSynthesisRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: GovernanceActionRequest) -> GovernanceSynthesisRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, GovernanceState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = GovernanceState.BLOCKED
            elif not record.governance_evidence_refs:
                raise GovernanceSynthesisError("governance evidence is required")
            elif any(item.confidence < record.minimum_signal_confidence for item in record.signals):
                raise GovernanceSynthesisError("signal confidence below threshold")
            else:
                record.state = GovernanceState.EVIDENCE_READY
        elif action == "synthesize":
            self._require(record, GovernanceState.EVIDENCE_READY)
            record.aggregate_risk = round(sum(item.severity for item in record.signals) / len(record.signals))
            if record.aggregate_risk > record.maximum_aggregate_risk:
                record.state = GovernanceState.ESCALATED
            else:
                record.state = GovernanceState.SYNTHESIZED
        elif action == "request-executive-review":
            self._require(record, GovernanceState.SYNTHESIZED)
            if not request.directive_ids:
                raise GovernanceSynthesisError("directive_ids are required")
            known = {item.directive_id for item in record.directives}
            if not set(request.directive_ids).issubset(known):
                raise GovernanceSynthesisError("unknown directive id")
            record.selected_directive_ids = list(dict.fromkeys(request.directive_ids))
            record.state = GovernanceState.EXECUTIVE_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, GovernanceState.EXECUTIVE_REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = GovernanceState.APPROVED
        elif action == "issue-directive":
            self._require(record, GovernanceState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            if not record.selected_directive_ids:
                raise GovernanceSynthesisError("approved directives are required")
            record.issued_at = datetime.now(timezone.utc)
            record.state = GovernanceState.DIRECTIVE_ISSUED
        elif action == "record-monitoring":
            if record.state not in {GovernanceState.DIRECTIVE_ISSUED, GovernanceState.MONITORING}:
                raise GovernanceSynthesisError("directive monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            if not request.evidence_refs:
                raise GovernanceSynthesisError("monitoring evidence is required")
            record.monitoring_evidence_refs.extend(request.evidence_refs)
            if request.monitoring_healthy:
                record.consecutive_healthy_cycles += 1
                record.state = GovernanceState.MONITORING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = GovernanceState.ESCALATED
        elif action == "verify":
            self._require(record, GovernanceState.MONITORING)
            if record.consecutive_healthy_cycles < record.monitoring_cycles_required:
                raise GovernanceSynthesisError("monitoring cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = GovernanceState.VERIFIED
        elif action == "escalate":
            if record.state in {GovernanceState.ARCHIVED, GovernanceState.REVOKED, GovernanceState.REJECTED}:
                raise GovernanceSynthesisError("escalation not allowed")
            record.state = GovernanceState.ESCALATED
        elif action == "revoke":
            if record.state not in {GovernanceState.DIRECTIVE_ISSUED, GovernanceState.MONITORING, GovernanceState.VERIFIED, GovernanceState.ESCALATED}:
                raise GovernanceSynthesisError("revocation not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = GovernanceState.REVOKED
        elif action == "reject":
            self._require(record, GovernanceState.EXECUTIVE_REVIEW_REQUIRED)
            record.state = GovernanceState.REJECTED
        elif action == "fail":
            if record.state in {GovernanceState.ARCHIVED, GovernanceState.REVOKED, GovernanceState.REJECTED}:
                raise GovernanceSynthesisError("failure transition not allowed")
            record.state = GovernanceState.FAILED
        elif action == "archive":
            if record.state not in {GovernanceState.VERIFIED, GovernanceState.REVOKED, GovernanceState.REJECTED, GovernanceState.FAILED, GovernanceState.BLOCKED, GovernanceState.ESCALATED}:
                raise GovernanceSynthesisError("record must be terminal before archive")
            record.state = GovernanceState.ARCHIVED
        else:
            raise GovernanceSynthesisError("unsupported action")

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state, {"directive_ids": request.directive_ids})
        return record

    @staticmethod
    def _require(record: GovernanceSynthesisRecord, state: GovernanceState) -> None:
        if record.state != state:
            raise GovernanceSynthesisError(f"expected state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise GovernanceSynthesisError(f"{label} is required")
        if value in store:
            raise GovernanceSynthesisError(f"duplicate {label}")
        store.add(value)

    @staticmethod
    def _touch(record: GovernanceSynthesisRecord) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record: GovernanceSynthesisRecord, action: str, actor: str, before: GovernanceState | None, after: GovernanceState, details: dict | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))


service = GovernanceSynthesisService()
