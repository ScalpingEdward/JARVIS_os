from __future__ import annotations

from datetime import datetime, timezone

from .models import AuditEvent, MissionActionRequest, MissionState, RiskDecision, StrategicMission, StrategicMissionCreate


class StrategicControlError(RuntimeError):
    pass


class StrategicControlService:
    def __init__(self) -> None:
        self._records: dict[str, StrategicMission] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: StrategicMissionCreate) -> StrategicMission:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise StrategicControlError("duplicate source key")
        record = StrategicMission(**payload.model_dump())
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> StrategicMission:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise StrategicControlError("strategic mission not found")
        return record

    def list(self, workspace_id: str) -> list[StrategicMission]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: MissionActionRequest) -> StrategicMission:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, MissionState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = MissionState.BLOCKED
            elif not record.strategic_evidence_refs:
                raise StrategicControlError("strategic evidence is required")
            else:
                record.state = MissionState.EVIDENCE_READY
        elif action == "align":
            self._require(record, MissionState.EVIDENCE_READY)
            if record.aggregate_risk > record.maximum_aggregate_risk:
                record.state = MissionState.ESCALATED
            else:
                record.state = MissionState.ALIGNED
        elif action == "request-review":
            self._require(record, MissionState.ALIGNED)
            record.state = MissionState.EXECUTIVE_REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, MissionState.EXECUTIVE_REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = MissionState.APPROVED
        elif action == "activate":
            self._require(record, MissionState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = MissionState.ACTIVATED
        elif action == "start":
            self._require(record, MissionState.ACTIVATED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = MissionState.EXECUTING
        elif action == "record-cycle":
            if record.state not in {MissionState.EXECUTING, MissionState.MONITORING}:
                raise StrategicControlError("mission execution is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            if record.execution_cycles >= record.maximum_execution_cycles:
                raise StrategicControlError("maximum execution cycles reached")
            record.execution_cycles += 1
            record.execution_evidence_refs.extend(request.evidence_refs)
            if request.aggregate_risk is not None:
                record.aggregate_risk = request.aggregate_risk
            if record.aggregate_risk > record.maximum_aggregate_risk:
                record.state = MissionState.ESCALATED
            elif request.cycle_successful:
                record.consecutive_success_cycles += 1
                record.state = MissionState.MONITORING
            else:
                record.consecutive_success_cycles = 0
                record.state = MissionState.MONITORING
        elif action == "achieve":
            self._require(record, MissionState.MONITORING)
            if record.consecutive_success_cycles < record.required_success_cycles:
                raise StrategicControlError("required success cycles incomplete")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = MissionState.ACHIEVED
        elif action == "escalate":
            if record.state in {MissionState.ARCHIVED, MissionState.ABORTED, MissionState.BLOCKED}:
                raise StrategicControlError("escalation not allowed")
            record.state = MissionState.ESCALATED
        elif action == "suspend":
            if record.state not in {MissionState.ACTIVATED, MissionState.EXECUTING, MissionState.MONITORING, MissionState.ESCALATED}:
                raise StrategicControlError("suspension not allowed")
            record.state = MissionState.SUSPENDED
        elif action == "resume":
            self._require(record, MissionState.SUSPENDED)
            record.state = MissionState.MONITORING if record.execution_cycles else MissionState.ACTIVATED
        elif action == "abort":
            if record.state in {MissionState.ARCHIVED, MissionState.ACHIEVED, MissionState.ABORTED}:
                raise StrategicControlError("abort not allowed")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.state = MissionState.ABORTED
        elif action == "archive":
            if record.state not in {MissionState.ACHIEVED, MissionState.ABORTED, MissionState.ESCALATED, MissionState.BLOCKED}:
                raise StrategicControlError("archive not allowed")
            record.state = MissionState.ARCHIVED
        else:
            raise StrategicControlError("unsupported action")

        self._touch(record)
        self._emit(record, action, request.actor, before, record.state)
        return record

    @staticmethod
    def _require(record: StrategicMission, expected: MissionState) -> None:
        if record.state != expected:
            raise StrategicControlError(f"action requires state {expected.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise StrategicControlError(f"{label} is required")
        if value in store:
            raise StrategicControlError(f"{label} replay detected")
        store.add(value)

    @staticmethod
    def _touch(record: StrategicMission) -> None:
        record.updated_at = datetime.now(timezone.utc)

    def _emit(self, record: StrategicMission, action: str, actor: str, before: MissionState | None, after: MissionState) -> None:
        self._audit.append(AuditEvent(record_id=record.record_id, workspace_id=record.workspace_id, action=action, actor=actor, from_state=before, to_state=after))


service = StrategicControlService()
