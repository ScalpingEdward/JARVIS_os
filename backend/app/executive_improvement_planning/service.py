from datetime import datetime, timezone
from uuid import UUID

from .models import (
    EngineeringBacklogItem,
    ImprovementPlanningAudit,
    ImprovementPlanningCreate,
    ImprovementPlanningExecuteRequest,
    ImprovementPlanningRecord,
    ImprovementPlanningState,
    ImprovementPlanningStatus,
)


class ImprovementPlanningService:
    def __init__(self) -> None:
        self._records: dict[UUID, ImprovementPlanningRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[ImprovementPlanningAudit] = []

    def create(self, payload: ImprovementPlanningCreate) -> ImprovementPlanningRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail, items, aggregate = self._evaluate(payload)
        record = ImprovementPlanningRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            backlog_items=items,
            aggregate_priority_score=aggregate,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: ImprovementPlanningCreate):
        if payload.upstream_risk_brain_blocked:
            return ImprovementPlanningState.BLOCKED, "upstream Risk Brain hard block", [], 100
        if not payload.v20_08_improvement_approved:
            return ImprovementPlanningState.EVIDENCE_REQUIRED, "approved v20.08 improvement evidence required", [], 0

        evidence = payload.evidence
        if evidence.incident_learning_state != "approved":
            return ImprovementPlanningState.EVIDENCE_REQUIRED, "incident learning state must be approved", [], 0
        if not evidence.improvement_actions:
            return ImprovementPlanningState.EVIDENCE_REQUIRED, "at least one approved improvement action is required", [], 0

        severity_weight = {"low": 20, "medium": 45, "high": 70, "critical": 95}.get(
            evidence.incident_severity.lower(), 45
        )
        outage_weight = min(100.0, evidence.estimated_outage_cost / 100.0)
        recurrence_weight = min(100.0, evidence.incident_count * 15.0)
        complexity_penalty = payload.technical_complexity * 0.18
        impact = min(100.0, payload.business_impact * 0.45 + severity_weight * 0.25 + evidence.recurrence_risk_score * 0.30)
        priority = min(
            100.0,
            max(
                0.0,
                impact * 0.45
                + recurrence_weight * 0.20
                + outage_weight * 0.20
                + severity_weight * 0.15
                - complexity_penalty,
            ),
        )
        confidence = min(0.98, 0.55 + min(evidence.incident_count, 5) * 0.06 + (0.08 if evidence.recurrence_risk_score >= 60 else 0))
        effort = max(1, min(21, round(payload.technical_complexity / 8) + (3 if evidence.requires_code_change else 0)))

        items: list[EngineeringBacklogItem] = []
        seen: set[str] = set()
        for action in evidence.improvement_actions:
            normalized = "-".join(action.lower().split())[:80]
            if normalized in seen:
                continue
            seen.add(normalized)
            items.append(
                EngineeringBacklogItem(
                    title=action[:120],
                    description=f"Governed defensive resilience improvement originating from v20.08 record {evidence.incident_learning_id}",
                    priority_score=round(priority, 2),
                    effort_points=effort,
                    confidence_score=round(confidence, 2),
                    impact_score=round(impact, 2),
                    defensive_only=True,
                    duplicate_group_key=normalized,
                    dependencies=evidence.dependencies,
                )
            )

        if not items:
            return ImprovementPlanningState.EVIDENCE_REQUIRED, "approved improvements collapsed to an empty backlog", [], 0

        state = ImprovementPlanningState.PRIORITIZED if priority >= 60 else ImprovementPlanningState.QUEUED
        detail = "engineering backlog prioritized" if state == ImprovementPlanningState.PRIORITIZED else "engineering backlog queued"
        return state, detail, items, round(priority, 2)

    def execute(self, record_id: UUID, workspace_id: str, request: ImprovementPlanningExecuteRequest) -> ImprovementPlanningRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("improvement planning record not found")

        if request.action == "schedule":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {ImprovementPlanningState.QUEUED, ImprovementPlanningState.PRIORITIZED}:
                raise ValueError("scheduling unavailable")
            sprint = request.target_sprint or record.request.target_sprint
            if not sprint:
                raise ValueError("target_sprint required")
            record.state = ImprovementPlanningState.SCHEDULED
            record.detail = f"scheduled for {sprint}"
        elif request.action == "release-to-v20.01":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {ImprovementPlanningState.PRIORITIZED, ImprovementPlanningState.SCHEDULED}:
                raise ValueError("release unavailable")
            record.state = ImprovementPlanningState.READY_FOR_V20_01
            record.detail = "approved backlog released to governed v20.01 planning"
        elif request.action == "cancel":
            record.state = ImprovementPlanningState.CANCELLED
            record.detail = "engineering backlog cancelled"
        elif request.action == "archive":
            record.state = ImprovementPlanningState.ARCHIVED
            record.detail = "engineering backlog archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ImprovementPlanningRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[ImprovementPlanningRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ImprovementPlanningStatus:
        records = self.list_records(workspace_id)
        blocked = {
            ImprovementPlanningState.BLOCKED,
            ImprovementPlanningState.EVIDENCE_REQUIRED,
            ImprovementPlanningState.CANCELLED,
            ImprovementPlanningState.FAILED,
        }
        return ImprovementPlanningStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            queued_records=sum(record.state == ImprovementPlanningState.QUEUED for record in records),
            prioritized_records=sum(record.state == ImprovementPlanningState.PRIORITIZED for record in records),
            ready_records=sum(record.state == ImprovementPlanningState.READY_FOR_V20_01 for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[ImprovementPlanningAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: ImprovementPlanningRecord, actor_id: str, action: str) -> None:
        self._audit.append(
            ImprovementPlanningAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


improvement_planning_service = ImprovementPlanningService()
