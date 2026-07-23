from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    ResilienceActionRequest,
    ResilienceCreate,
    ResilienceGovernanceRecord,
    ResilienceState,
    RiskDecision,
    TestStatus,
)


class ResilienceGovernanceError(RuntimeError):
    pass


class ResilienceGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, ResilienceGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: ResilienceCreate) -> ResilienceGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ResilienceGovernanceError("duplicate source key")
        record = ResilienceGovernanceRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> ResilienceGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise ResilienceGovernanceError("resilience governance record not found")
        return record

    def list(self, workspace_id: str) -> list[ResilienceGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: ResilienceActionRequest) -> ResilienceGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, ResilienceState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = ResilienceState.BLOCKED
            elif not record.resilience_evidence_refs:
                raise ResilienceGovernanceError("resilience evidence is required")
            else:
                record.state = ResilienceState.EVIDENCE_READY
        elif action == "design":
            self._require(record, ResilienceState.EVIDENCE_READY)
            if any(item.confidence < record.minimum_control_confidence for item in record.controls):
                raise ResilienceGovernanceError("resilience control confidence below threshold")
            record.state = ResilienceState.DESIGNED
        elif action == "prepare-test-plan":
            self._require(record, ResilienceState.DESIGNED)
            if not all(item.evidence_refs for item in record.scenarios):
                raise ResilienceGovernanceError("scenario evidence is required")
            record.state = ResilienceState.TEST_PLAN_READY
        elif action == "request-review":
            self._require(record, ResilienceState.TEST_PLAN_READY)
            record.state = ResilienceState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, ResilienceState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = ResilienceState.APPROVED
        elif action == "execute":
            self._require(record, ResilienceState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.execution_evidence_refs.extend(request.evidence_refs)
            self._refresh(record)
            if self._breached(record):
                record.state = ResilienceState.ESCALATED
            else:
                record.state = ResilienceState.EXECUTING
        elif action == "record-cycle":
            if record.state not in {ResilienceState.EXECUTING, ResilienceState.MONITORING}:
                raise ResilienceGovernanceError("resilience monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.execution_evidence_refs.extend(request.evidence_refs)
            if request.observed_failed_scenarios is not None:
                record.failed_scenarios = request.observed_failed_scenarios
            if request.observed_degraded_scenarios is not None:
                record.degraded_scenarios = request.observed_degraded_scenarios
            if request.observed_minimum_availability is not None:
                record.minimum_observed_availability = request.observed_minimum_availability
            healthy = bool(request.cycle_healthy) and not self._breached(record)
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = ResilienceState.MONITORING if healthy else ResilienceState.ESCALATED
        elif action == "verify":
            self._require(record, ResilienceState.MONITORING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise ResilienceGovernanceError("insufficient healthy cycles")
            record.state = ResilienceState.VERIFIED
        elif action == "escalate":
            record.state = ResilienceState.ESCALATED
        elif action == "suspend":
            if record.state in {ResilienceState.ARCHIVED, ResilienceState.REVOKED}:
                raise ResilienceGovernanceError("record cannot be suspended")
            record.state = ResilienceState.SUSPENDED
        elif action == "resume":
            self._require(record, ResilienceState.SUSPENDED)
            record.state = ResilienceState.MONITORING
        elif action == "revoke":
            if record.state == ResilienceState.ARCHIVED:
                raise ResilienceGovernanceError("archived record cannot be revoked")
            record.state = ResilienceState.REVOKED
        elif action == "archive":
            if record.state not in {ResilienceState.VERIFIED, ResilienceState.REVOKED, ResilienceState.ESCALATED}:
                raise ResilienceGovernanceError("record is not archivable")
            record.state = ResilienceState.ARCHIVED
        else:
            raise ResilienceGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request.note)
        return record

    def _refresh(self, record: ResilienceGovernanceRecord) -> None:
        record.failed_scenarios = sum(item.status == TestStatus.FAILED for item in record.scenarios)
        record.degraded_scenarios = sum(item.status == TestStatus.DEGRADED for item in record.scenarios)
        record.minimum_observed_availability = min(item.service_availability for item in record.scenarios)

    def _breached(self, record: ResilienceGovernanceRecord) -> bool:
        recovery_breach = any(
            item.observed_recovery_minutes is not None
            and item.observed_recovery_minutes > item.target_recovery_minutes
            for item in record.scenarios
        )
        recovery_point_breach = any(
            item.observed_recovery_point_minutes is not None
            and item.observed_recovery_point_minutes > item.target_recovery_point_minutes
            for item in record.scenarios
        )
        return (
            recovery_breach
            or recovery_point_breach
            or record.failed_scenarios > record.maximum_failed_scenarios
            or record.degraded_scenarios > record.maximum_degraded_scenarios
            or record.minimum_observed_availability < record.minimum_service_availability
        )

    @staticmethod
    def _require(record: ResilienceGovernanceRecord, expected: ResilienceState) -> None:
        if record.state != expected:
            raise ResilienceGovernanceError(f"action requires state {expected.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise ResilienceGovernanceError(f"{label} is required")
        if value in store:
            raise ResilienceGovernanceError(f"{label} replay detected")
        store.add(value)

    def _emit(
        self,
        record: ResilienceGovernanceRecord,
        action: str,
        actor: str,
        before: ResilienceState | None,
        after: ResilienceState,
        note: str | None = None,
    ) -> None:
        details = {"note": note} if note else {}
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=before,
                to_state=after,
                details=details,
            )
        )


service = ResilienceGovernanceService()
