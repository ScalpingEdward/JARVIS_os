from datetime import datetime, timezone
from uuid import UUID

from .models import (
    IncidentLearningAudit,
    IncidentLearningCreate,
    IncidentLearningExecuteRequest,
    IncidentLearningRecord,
    IncidentLearningState,
    IncidentLearningStatus,
    ResilienceImprovement,
    RootCauseFinding,
)


class IncidentLearningService:
    def __init__(self) -> None:
        self._records: dict[UUID, IncidentLearningRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[IncidentLearningAudit] = []

    def create(self, payload: IncidentLearningCreate) -> IncidentLearningRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail, causes, improvements, recurrence = self._evaluate(payload)
        record = IncidentLearningRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            root_causes=causes,
            improvements=improvements,
            recurrence_risk_score=recurrence,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: IncidentLearningCreate):
        if payload.upstream_risk_brain_blocked:
            return IncidentLearningState.BLOCKED, "upstream Risk Brain hard block", [], [], 100
        if not payload.v20_07_incident_closed:
            return IncidentLearningState.EVIDENCE_REQUIRED, "closed v20.07 incident evidence required", [], [], 100

        evidence = payload.evidence
        if evidence.incident_state not in {"recovered", "rolled-back", "archived"}:
            return IncidentLearningState.EVIDENCE_REQUIRED, "incident must be terminal before learning analysis", [], [], 100
        if not evidence.findings:
            return IncidentLearningState.EVIDENCE_REQUIRED, "incident findings are required", [], [], 100

        causes: list[RootCauseFinding] = []
        improvements: list[ResilienceImprovement] = []
        joined = " ".join(evidence.findings).lower()

        mappings = (
            ("broker", "broker-connectivity", "add broker connectivity circuit breaker and reconnection verification"),
            ("feed", "market-data", "add stale-feed detection and defensive trading pause"),
            ("database", "database", "add database availability guard and retry budget"),
            ("queue", "queue", "add queue depth alerting and bounded consumer restart"),
            ("latency", "performance", "add latency budget monitoring and load shedding"),
            ("vps", "infrastructure", "add VPS heartbeat and controlled service restart"),
            ("health", "runtime-health", "expand health checks and dependency diagnostics"),
        )
        for token, category, action in mappings:
            if token in joined:
                causes.append(RootCauseFinding(category=category, confidence=0.85, detail=f"evidence indicates {category} degradation"))
                improvements.append(ResilienceImprovement(action=action, defensive_only=True, requires_code_change=True, requires_human_review=True))

        if not causes:
            causes.append(RootCauseFinding(category="unknown", confidence=0.35, detail="available evidence is insufficient for a deterministic root cause"))
            improvements.append(ResilienceImprovement(action="increase diagnostic telemetry and retain incident evidence", defensive_only=True, requires_code_change=False, requires_human_review=False))

        recurrence = min(100.0, round(evidence.recurrence_count * 18 + min(evidence.duration_seconds / 60, 40), 2))
        sensitive = evidence.severity.lower() == "critical" or evidence.recurrence_count >= 3 or any(item.requires_code_change for item in improvements)
        if sensitive:
            return IncidentLearningState.HUMAN_REVIEW_REQUIRED, "resilience improvements require explicit human review", causes, improvements, recurrence
        return IncidentLearningState.IMPROVEMENT_PROPOSED, "defensive resilience improvement proposed", causes, improvements, recurrence

    def execute(self, record_id: UUID, workspace_id: str, request: IncidentLearningExecuteRequest) -> IncidentLearningRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("incident learning record not found")

        if request.action == "approve":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {IncidentLearningState.HUMAN_REVIEW_REQUIRED, IncidentLearningState.IMPROVEMENT_PROPOSED}:
                raise ValueError("approval unavailable")
            record.state = IncidentLearningState.APPROVED
            record.detail = "defensive resilience improvement approved for governed implementation planning"
        elif request.action == "reject":
            record.state = IncidentLearningState.REJECTED
            record.detail = "resilience improvement rejected"
        elif request.action == "archive":
            record.state = IncidentLearningState.ARCHIVED
            record.detail = "incident learning record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> IncidentLearningRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[IncidentLearningRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> IncidentLearningStatus:
        records = self.list_records(workspace_id)
        blocked = {IncidentLearningState.BLOCKED, IncidentLearningState.EVIDENCE_REQUIRED, IncidentLearningState.REJECTED, IncidentLearningState.FAILED}
        return IncidentLearningStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            proposed_records=sum(record.state == IncidentLearningState.IMPROVEMENT_PROPOSED for record in records),
            human_review_records=sum(record.state == IncidentLearningState.HUMAN_REVIEW_REQUIRED for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[IncidentLearningAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: IncidentLearningRecord, actor_id: str, action: str) -> None:
        self._audit.append(IncidentLearningAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


incident_learning_service = IncidentLearningService()
