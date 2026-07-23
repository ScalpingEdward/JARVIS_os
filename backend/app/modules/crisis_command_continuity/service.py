from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AuditEvent,
    CrisisActionRequest,
    CrisisCreate,
    CrisisGovernanceRecord,
    CrisisState,
    IncidentSeverity,
    IncidentStatus,
    RiskDecision,
)


class CrisisGovernanceError(RuntimeError):
    pass


class CrisisGovernanceService:
    def __init__(self) -> None:
        self._records: dict[str, CrisisGovernanceRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[str] = set()
        self._receipt_ids: set[str] = set()
        self._audit: list[AuditEvent] = []

    def create(self, payload: CrisisCreate) -> CrisisGovernanceRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise CrisisGovernanceError("duplicate source key")
        record = CrisisGovernanceRecord(**payload.model_dump())
        self._refresh(record)
        self._records[record.record_id] = record
        self._source_keys.add(key)
        self._emit(record, "create", "system", None, record.state)
        return record

    def get(self, record_id: str, workspace_id: str) -> CrisisGovernanceRecord:
        record = self._records.get(record_id)
        if record is None or record.workspace_id != workspace_id:
            raise CrisisGovernanceError("crisis governance record not found")
        return record

    def list(self, workspace_id: str) -> list[CrisisGovernanceRecord]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditEvent]:
        return [event for event in self._audit if event.workspace_id == workspace_id]

    def act(self, record_id: str, workspace_id: str, request: CrisisActionRequest) -> CrisisGovernanceRecord:
        record = self.get(record_id, workspace_id)
        before = record.state
        action = request.action

        if action == "prepare-evidence":
            self._require(record, CrisisState.DRAFT)
            if record.risk_decision == RiskDecision.BLOCK:
                record.state = CrisisState.BLOCKED
            elif not record.crisis_evidence_refs:
                raise CrisisGovernanceError("crisis evidence is required")
            else:
                record.state = CrisisState.EVIDENCE_READY
        elif action == "assess":
            self._require(record, CrisisState.EVIDENCE_READY)
            self._refresh(record)
            overdue = any(
                item.status != IncidentStatus.RESOLVED
                and item.elapsed_minutes > item.recovery_time_objective_minutes
                for item in record.incidents
            )
            impact_breach = any(item.business_impact > item.maximum_tolerable_impact for item in record.incidents)
            breached = (
                overdue
                or impact_breach
                or record.open_incidents > record.maximum_open_incidents
                or record.critical_incidents > record.maximum_critical_incidents
                or record.aggregate_impact > record.maximum_aggregate_impact
            )
            record.state = CrisisState.ESCALATED if breached else CrisisState.ASSESSED
        elif action == "prepare-command-plan":
            self._require(record, CrisisState.ASSESSED)
            if any(item.confidence < record.minimum_action_confidence for item in record.continuity_actions):
                raise CrisisGovernanceError("continuity action confidence below threshold")
            record.state = CrisisState.COMMAND_PLAN_READY
        elif action == "request-review":
            self._require(record, CrisisState.COMMAND_PLAN_READY)
            record.state = CrisisState.REVIEW_REQUIRED
        elif action == "approve":
            self._require(record, CrisisState.REVIEW_REQUIRED)
            self._consume(self._approval_tokens, request.approval_token, "approval token")
            record.approval_actor = request.actor
            record.state = CrisisState.APPROVED
        elif action == "activate":
            self._require(record, CrisisState.APPROVED)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.command_evidence_refs.extend(request.evidence_refs)
            record.state = CrisisState.ACTIVATED
        elif action == "record-cycle":
            if record.state not in {CrisisState.ACTIVATED, CrisisState.STABILIZING, CrisisState.RECOVERING}:
                raise CrisisGovernanceError("crisis monitoring is not active")
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            record.command_evidence_refs.extend(request.evidence_refs)
            if request.observed_open_incidents is not None:
                record.open_incidents = request.observed_open_incidents
            if request.observed_critical_incidents is not None:
                record.critical_incidents = request.observed_critical_incidents
            if request.observed_aggregate_impact is not None:
                record.aggregate_impact = request.observed_aggregate_impact
            healthy = (
                bool(request.cycle_healthy)
                and record.open_incidents <= record.maximum_open_incidents
                and record.critical_incidents <= record.maximum_critical_incidents
                and record.aggregate_impact <= record.maximum_aggregate_impact
            )
            record.consecutive_healthy_cycles = record.consecutive_healthy_cycles + 1 if healthy else 0
            record.state = CrisisState.STABILIZING if healthy else CrisisState.ESCALATED
        elif action == "start-recovery":
            self._require(record, CrisisState.STABILIZING)
            if record.consecutive_healthy_cycles < record.required_healthy_cycles:
                raise CrisisGovernanceError("healthy cycle requirement not met")
            record.state = CrisisState.RECOVERING
        elif action == "resolve":
            self._require(record, CrisisState.RECOVERING)
            self._consume(self._receipt_ids, request.receipt_id, "receipt")
            if record.open_incidents or record.critical_incidents or record.aggregate_impact > record.maximum_aggregate_impact:
                raise CrisisGovernanceError("crisis cannot be resolved while limits remain breached")
            record.command_evidence_refs.extend(request.evidence_refs)
            record.state = CrisisState.RESOLVED
        elif action == "escalate":
            record.state = CrisisState.ESCALATED
        elif action == "suspend":
            if record.state in {CrisisState.REVOKED, CrisisState.ARCHIVED}:
                raise CrisisGovernanceError("record cannot be suspended")
            record.state = CrisisState.SUSPENDED
        elif action == "resume":
            self._require(record, CrisisState.SUSPENDED)
            record.state = CrisisState.ESCALATED
        elif action == "revoke":
            if record.state == CrisisState.ARCHIVED:
                raise CrisisGovernanceError("archived record cannot be revoked")
            record.state = CrisisState.REVOKED
        elif action == "archive":
            if record.state not in {CrisisState.RESOLVED, CrisisState.REVOKED}:
                raise CrisisGovernanceError("only resolved or revoked records can be archived")
            record.state = CrisisState.ARCHIVED
        else:
            raise CrisisGovernanceError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._emit(record, action, request.actor, before, record.state, request.model_dump(exclude_none=True))
        return record

    @staticmethod
    def _refresh(record: CrisisGovernanceRecord) -> None:
        active = [item for item in record.incidents if item.status != IncidentStatus.RESOLVED]
        record.open_incidents = len(active)
        record.critical_incidents = sum(item.severity == IncidentSeverity.CRITICAL for item in active)
        record.aggregate_impact = sum(item.business_impact for item in active)

    @staticmethod
    def _require(record: CrisisGovernanceRecord, state: CrisisState) -> None:
        if record.state != state:
            raise CrisisGovernanceError(f"action requires state {state.value}")

    @staticmethod
    def _consume(store: set[str], value: str | None, label: str) -> None:
        if not value:
            raise CrisisGovernanceError(f"{label} is required")
        if value in store:
            raise CrisisGovernanceError(f"{label} has already been used")
        store.add(value)

    def _emit(
        self,
        record: CrisisGovernanceRecord,
        action: str,
        actor: str,
        before: CrisisState | None,
        after: CrisisState,
        details: dict | None = None,
    ) -> None:
        self._audit.append(
            AuditEvent(
                record_id=record.record_id,
                workspace_id=record.workspace_id,
                action=action,
                actor=actor,
                from_state=before,
                to_state=after,
                details=details or {},
            )
        )


service = CrisisGovernanceService()
