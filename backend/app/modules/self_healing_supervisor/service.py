from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    HealthStatus,
    RiskDecision,
    SelfHealingSupervisor,
    SupervisorActionRequest,
    SupervisorCreate,
    SupervisorState,
)


class SelfHealingSupervisorError(RuntimeError):
    pass


class SelfHealingSupervisorService:
    def __init__(self) -> None:
        self._records: dict[str, SelfHealingSupervisor] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._signal_ids: set[tuple[str, str]] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: SupervisorCreate) -> SelfHealingSupervisor:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise SelfHealingSupervisorError("duplicate source key")
        record = SelfHealingSupervisor(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        for signal in record.health_signals:
            self._signal_ids.add((record.workspace_id, signal.signal_id))
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> SelfHealingSupervisor:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise SelfHealingSupervisorError("self-healing supervisor not found")
        return record

    def list(self, workspace_id: str) -> list[SelfHealingSupervisor]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: SupervisorActionRequest) -> SelfHealingSupervisor:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "start-monitoring":
            self._require(record, SupervisorState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = SupervisorState.BLOCKED
            elif not record.monitoring_evidence_refs:
                raise SelfHealingSupervisorError("monitoring evidence is required")
            else:
                record.state = self._derived_health_state(record)
        elif action == "ingest-signal":
            if record.state in {SupervisorState.ARCHIVED, SupervisorState.BLOCKED, SupervisorState.SUSPENDED}:
                raise SelfHealingSupervisorError("signals cannot be ingested in current state")
            if request.signal is None:
                raise SelfHealingSupervisorError("signal is required")
            key = (workspace_id, request.signal.signal_id)
            if key in self._signal_ids:
                raise SelfHealingSupervisorError("duplicate signal id")
            self._signal_ids.add(key)
            record.health_signals.append(request.signal)
            record.consecutive_healthy_cycles = 0
            record.state = self._derived_health_state(record)
        elif action == "propose-recovery":
            self._require(record, SupervisorState.DEGRADED)
            if record.risk_decision == RiskDecision.BLOCK:
                raise SelfHealingSupervisorError("Risk Brain hard block")
            candidate = self._candidate(record, request.candidate_id)
            record.selected_candidate_id = candidate.candidate_id
            record.state = SupervisorState.RECOVERY_PROPOSED
        elif action == "request-review":
            self._require(record, SupervisorState.RECOVERY_PROPOSED)
            record.state = SupervisorState.HUMAN_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, SupervisorState.HUMAN_REVIEW_REQUIRED)
            self._consume_token(request.approval_token)
            record.approval_actor = request.actor
            record.state = SupervisorState.APPROVED
        elif action == "start-recovery":
            self._require(record, SupervisorState.APPROVED)
            if record.recovery_attempts >= record.max_recovery_attempts:
                raise SelfHealingSupervisorError("maximum recovery attempts reached")
            self._consume_receipt(request.receipt_id)
            record.recovery_attempts += 1
            record.consecutive_healthy_cycles = 0
            record.state = SupervisorState.RECOVERING
        elif action == "record-cycle":
            if record.state not in {SupervisorState.RECOVERING, SupervisorState.STABILIZING}:
                raise SelfHealingSupervisorError("health cycles require active recovery")
            if request.healthy_cycle is None:
                raise SelfHealingSupervisorError("healthy_cycle is required")
            if request.healthy_cycle:
                record.consecutive_healthy_cycles += 1
                record.state = SupervisorState.STABILIZING
            else:
                record.consecutive_healthy_cycles = 0
                record.state = SupervisorState.RECOVERING
        elif action == "complete-recovery":
            if record.state != SupervisorState.STABILIZING:
                raise SelfHealingSupervisorError("recovery must be stabilizing")
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise SelfHealingSupervisorError("insufficient healthy stabilization cycles")
            if not request.recovery_evidence_refs:
                raise SelfHealingSupervisorError("recovery evidence is required")
            self._consume_receipt(request.receipt_id)
            record.recovery_evidence_refs.extend(request.recovery_evidence_refs)
            record.state = SupervisorState.HEALTHY
        elif action == "fail-recovery":
            if record.state not in {SupervisorState.RECOVERING, SupervisorState.STABILIZING}:
                raise SelfHealingSupervisorError("no active recovery")
            if not request.recovery_evidence_refs:
                raise SelfHealingSupervisorError("failure evidence is required")
            self._consume_receipt(request.receipt_id)
            record.recovery_evidence_refs.extend(request.recovery_evidence_refs)
            record.state = SupervisorState.FAILED
        elif action == "suspend":
            if record.state in {SupervisorState.ARCHIVED, SupervisorState.SUSPENDED}:
                raise SelfHealingSupervisorError("supervisor cannot be suspended")
            record.state = SupervisorState.SUSPENDED
        elif action == "resume":
            self._require(record, SupervisorState.SUSPENDED)
            record.state = self._derived_health_state(record)
        elif action == "archive":
            if record.state not in {SupervisorState.HEALTHY, SupervisorState.FAILED, SupervisorState.BLOCKED, SupervisorState.SUSPENDED}:
                raise SelfHealingSupervisorError("supervisor is not terminal")
            record.state = SupervisorState.ARCHIVED

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state, self._details(request))
        return record

    @staticmethod
    def _derived_health_state(record: SelfHealingSupervisor) -> SupervisorState:
        statuses = {signal.status for signal in record.health_signals}
        if HealthStatus.CRITICAL in statuses or HealthStatus.DEGRADED in statuses:
            return SupervisorState.DEGRADED
        if statuses == {HealthStatus.HEALTHY}:
            return SupervisorState.HEALTHY
        return SupervisorState.MONITORING

    @staticmethod
    def _candidate(record: SelfHealingSupervisor, candidate_id: str | None):
        if not candidate_id:
            raise SelfHealingSupervisorError("candidate_id is required")
        for candidate in record.recovery_candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        raise SelfHealingSupervisorError("recovery candidate not found")

    @staticmethod
    def _require(record: SelfHealingSupervisor, state: SupervisorState) -> None:
        if record.state != state:
            raise SelfHealingSupervisorError(f"action requires state {state.value}")

    def _consume_token(self, token: str | None) -> None:
        if not token:
            raise SelfHealingSupervisorError("approval token is required")
        if token in self._approval_tokens:
            raise SelfHealingSupervisorError("approval token replay detected")
        self._approval_tokens.add(token)

    def _consume_receipt(self, receipt_id: str | None) -> None:
        if not receipt_id:
            raise SelfHealingSupervisorError("receipt id is required")
        if receipt_id in self._receipt_ids:
            raise SelfHealingSupervisorError("receipt replay detected")
        self._receipt_ids.add(receipt_id)

    @staticmethod
    def _touch(record: SelfHealingSupervisor) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record: SelfHealingSupervisor, action: str, actor: str, before: SupervisorState | None, after: SupervisorState, details: dict | None = None) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after, details=details or {}))

    @staticmethod
    def _details(request: SupervisorActionRequest) -> dict:
        details: dict = {}
        if request.signal is not None:
            details["signal_id"] = request.signal.signal_id
        if request.candidate_id:
            details["candidate_id"] = request.candidate_id
        if request.healthy_cycle is not None:
            details["healthy_cycle"] = request.healthy_cycle
        if request.note:
            details["note"] = request.note
        return details


service = SelfHealingSupervisorService()
