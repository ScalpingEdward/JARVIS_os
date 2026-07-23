from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    ExecutiveActionRequest,
    ExecutiveDecisionCreate,
    ExecutiveDecisionRecord,
    ExecutiveState,
    ObjectiveStatus,
    RiskDecision,
)


class ExecutiveGovernanceError(RuntimeError):
    pass


class ExecutiveDecisionService:
    def __init__(self) -> None:
        self._records: dict[str, ExecutiveDecisionRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: ExecutiveDecisionCreate) -> ExecutiveDecisionRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ExecutiveGovernanceError("duplicate source key")
        record = ExecutiveDecisionRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> ExecutiveDecisionRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ExecutiveGovernanceError("executive decision record not found")
        return record

    def list(self, workspace_id: str) -> list[ExecutiveDecisionRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: ExecutiveActionRequest) -> ExecutiveDecisionRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, ExecutiveState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = ExecutiveState.BLOCKED
            elif not record.decision_evidence_refs:
                raise ExecutiveGovernanceError("decision evidence is required")
            else:
                record.state = ExecutiveState.EVIDENCE_READY
        elif action == "analyze":
            self._require(record, ExecutiveState.EVIDENCE_READY)
            self._refresh(record)
            breached = (
                record.weighted_objective_score < record.minimum_weighted_objective_score
                or record.breached_objectives > record.maximum_breached_objectives
                or record.at_risk_objectives > record.maximum_at_risk_objectives
            )
            record.state = ExecutiveState.ESCALATED if breached else ExecutiveState.ANALYZED
        elif action == "prepare-decision":
            self._require(record, ExecutiveState.ANALYZED)
            selected = self._selected(record)
            if selected.confidence < record.minimum_option_confidence:
                raise ExecutiveGovernanceError("selected option confidence below threshold")
            record.selected_option_score = selected.expected_business_impact - max(selected.expected_risk_impact, 0)
            record.state = ExecutiveState.DECISION_READY
        elif action == "request-review":
            self._require(record, ExecutiveState.DECISION_READY)
            record.state = ExecutiveState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, ExecutiveState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = ExecutiveState.APPROVED
        elif action == "activate":
            self._require(record, ExecutiveState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "activation receipt")
            if record.risk_decision == RiskDecision.BLOCK:
                raise ExecutiveGovernanceError("Risk Brain blocked activation")
            record.activation_evidence_refs.extend(request.evidence_refs)
            record.state = ExecutiveState.ACTIVATED
        elif action == "record-cycle":
            if record.state not in {ExecutiveState.ACTIVATED, ExecutiveState.MONITORING}:
                raise ExecutiveGovernanceError("record-cycle requires activated or monitoring state")
            record.state = ExecutiveState.MONITORING
            healthy = bool(request.cycle_healthy)
            if request.observed_weighted_objective_score is not None:
                record.weighted_objective_score = request.observed_weighted_objective_score
            if request.observed_breached_objectives is not None:
                record.breached_objectives = request.observed_breached_objectives
            if request.observed_at_risk_objectives is not None:
                record.at_risk_objectives = request.observed_at_risk_objectives
            breached = (
                record.weighted_objective_score < record.minimum_weighted_objective_score
                or record.breached_objectives > record.maximum_breached_objectives
                or record.at_risk_objectives > record.maximum_at_risk_objectives
            )
            if breached:
                record.state = ExecutiveState.ESCALATED
                record.consecutive_healthy_cycles = 0
            else:
                record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
        elif action == "verify":
            self._require(record, ExecutiveState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise ExecutiveGovernanceError("insufficient healthy monitoring cycles")
            record.state = ExecutiveState.VERIFIED
        elif action == "escalate":
            record.state = ExecutiveState.ESCALATED
        elif action == "suspend":
            if record.state not in {ExecutiveState.APPROVED, ExecutiveState.ACTIVATED, ExecutiveState.MONITORING}:
                raise ExecutiveGovernanceError("state cannot be suspended")
            record.state = ExecutiveState.SUSPENDED
        elif action == "resume":
            self._require(record, ExecutiveState.SUSPENDED)
            record.state = ExecutiveState.MONITORING if record.activation_evidence_refs else ExecutiveState.APPROVED
        elif action == "revoke":
            if record.state == ExecutiveState.ARCHIVED:
                raise ExecutiveGovernanceError("archived record cannot be revoked")
            record.state = ExecutiveState.REVOKED
        elif action == "archive":
            if record.state not in {ExecutiveState.VERIFIED, ExecutiveState.REVOKED, ExecutiveState.ESCALATED}:
                raise ExecutiveGovernanceError("only terminal records can be archived")
            record.state = ExecutiveState.ARCHIVED
        else:
            raise ExecutiveGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request)
        return record

    def _refresh(self, record: ExecutiveDecisionRecord) -> None:
        record.weighted_objective_score = sum(item.weight * item.current_score for item in record.objectives)
        record.breached_objectives = sum(
            1 for item in record.objectives
            if item.status == ObjectiveStatus.BREACHED or item.current_score < item.minimum_acceptable_score
        )
        record.at_risk_objectives = sum(1 for item in record.objectives if item.status == ObjectiveStatus.AT_RISK)

    @staticmethod
    def _selected(record: ExecutiveDecisionRecord):
        return next(item for item in record.options if item.option_id == record.selected_option_id)

    @staticmethod
    def _require(record: ExecutiveDecisionRecord, expected: ExecutiveState) -> None:
        if record.state != expected:
            raise ExecutiveGovernanceError(f"action requires {expected.value} state")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise ExecutiveGovernanceError(f"{label} is required")
        if value in store:
            raise ExecutiveGovernanceError(f"{label} replay detected")
        store.add(value)

    def _emit(
        self,
        record: ExecutiveDecisionRecord,
        action: str,
        actor: str,
        before: ExecutiveState | None,
        after: ExecutiveState,
        request: ExecutiveActionRequest | None = None,
    ) -> None:
        details = {} if request is None else {
            "note": request.note,
            "evidence_refs": request.evidence_refs,
        }
        self._audit.append(AuditEvent(
            record_id=record.record_id,
            workspace_id=record.workspace_id,
            action=action,
            actor=actor,
            from_state=before,
            to_state=after,
            details=details,
        ))


service = ExecutiveDecisionService()
