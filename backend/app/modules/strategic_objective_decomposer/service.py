from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    StrategicDeliverable,
    StrategicMilestone,
    StrategicObjectiveAudit,
    StrategicObjectiveCreate,
    StrategicObjectiveExecuteRequest,
    StrategicObjectivePlan,
    StrategicObjectiveRecord,
    StrategicObjectiveState,
    StrategicObjectiveStatus,
)


class StrategicObjectiveDecomposerService:
    def __init__(self) -> None:
        self._records: dict[UUID, StrategicObjectiveRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._approval_tokens: set[tuple[str, str]] = set()
        self._audit: list[StrategicObjectiveAudit] = []

    def create(self, payload: StrategicObjectiveCreate) -> StrategicObjectiveRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail, plan = self._decompose(payload)
        record = StrategicObjectiveRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            plan=plan,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _decompose(self, payload: StrategicObjectiveCreate):
        if payload.upstream_risk_brain_blocked:
            return StrategicObjectiveState.BLOCKED, "upstream Risk Brain hard block", None
        if not payload.success_metrics:
            return StrategicObjectiveState.EVIDENCE_REQUIRED, "at least one measurable success metric is required", None
        if not payload.constraints:
            return StrategicObjectiveState.EVIDENCE_REQUIRED, "strategic constraints are required", None

        priority = round(min(100.0, payload.business_value * 0.45 + payload.urgency * 0.35 + payload.confidence * 0.20), 2)
        objective_slug = "-".join(payload.objective.lower().split())[:48]
        dependencies = list(dict.fromkeys(payload.known_dependencies))

        deliverables = [
            StrategicDeliverable(
                id=f"{objective_slug}-d1",
                title="Validated objective charter",
                description="Convert the strategic objective into governed scope, measurable outcomes and explicit boundaries.",
                acceptance_criteria=["scope is explicit", "success metrics are measurable", "constraints are preserved"],
                dependencies=[],
                estimated_effort_points=3,
                priority_score=priority,
                owner_role="executive-planning",
            ),
            StrategicDeliverable(
                id=f"{objective_slug}-d2",
                title="Dependency and risk readiness map",
                description="Resolve ownership, sequencing, dependencies and material execution risks before work issuance.",
                acceptance_criteria=["dependencies have owners", "critical risks have mitigations", "unresolved blockers are visible"],
                dependencies=[f"{objective_slug}-d1"],
                estimated_effort_points=5,
                priority_score=priority,
                owner_role="risk-and-capacity-planning",
            ),
            StrategicDeliverable(
                id=f"{objective_slug}-d3",
                title="Governed execution roadmap",
                description="Produce milestones and bounded work packages suitable for downstream executive planning.",
                acceptance_criteria=["milestones are sequenced", "deliverables have exit criteria", "human approval precedes issuance"],
                dependencies=[f"{objective_slug}-d2", *dependencies],
                estimated_effort_points=8,
                priority_score=priority,
                owner_role="executive-roadmap",
            ),
        ]
        milestones = [
            StrategicMilestone(
                id=f"{objective_slug}-m1",
                title="Objective validated",
                objective="Establish an approved strategic charter.",
                deliverable_ids=[deliverables[0].id],
                exit_criteria=["objective, scope, constraints and success metrics are approved"],
                sequence=1,
            ),
            StrategicMilestone(
                id=f"{objective_slug}-m2",
                title="Execution readiness established",
                objective="Establish dependency, risk and ownership readiness.",
                deliverable_ids=[deliverables[1].id],
                exit_criteria=["critical dependencies and risks are governed"],
                sequence=2,
            ),
            StrategicMilestone(
                id=f"{objective_slug}-m3",
                title="Roadmap ready for executive planning",
                objective="Issue a bounded roadmap to downstream planning without authorizing execution.",
                deliverable_ids=[deliverables[2].id],
                exit_criteria=["roadmap is human-approved and ready for prioritization"],
                sequence=3,
            ),
        ]
        risks = ["objective ambiguity", "dependency delay", "capacity shortfall", "budget overrun"]
        if payload.target_date:
            risks.append("target-date compression")
        if payload.budget_limit is not None:
            risks.append("budget-limit breach")

        plan = StrategicObjectivePlan(
            objective=payload.objective,
            executive_summary=f"Governed decomposition of strategic objective: {payload.objective}",
            milestones=milestones,
            deliverables=deliverables,
            dependencies=dependencies,
            constraints=payload.constraints,
            success_metrics=payload.success_metrics,
            risks=risks,
            total_effort_points=sum(item.estimated_effort_points for item in deliverables),
            aggregate_priority_score=priority,
        )
        return StrategicObjectiveState.HUMAN_REVIEW_REQUIRED, "strategic objective decomposed; explicit human approval required", plan

    def execute(self, record_id: UUID, workspace_id: str, request: StrategicObjectiveExecuteRequest) -> StrategicObjectiveRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("strategic objective record not found")

        if request.action == "approve":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != StrategicObjectiveState.HUMAN_REVIEW_REQUIRED or record.plan is None:
                raise ValueError("approval unavailable")
            material = f"{workspace_id}:{record.id}:{record.source_key}:{record.plan.aggregate_priority_score}"
            token = sha256(material.encode("utf-8")).hexdigest()
            token_key = (workspace_id, token)
            if token_key in self._approval_tokens:
                raise ValueError("approval token already consumed")
            self._approval_tokens.add(token_key)
            record.approval_token = token
            record.state = StrategicObjectiveState.APPROVED
            record.detail = "strategic decomposition approved"
        elif request.action == "issue-to-executive-planning":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != StrategicObjectiveState.APPROVED or not record.approval_token:
                raise ValueError("approved strategic plan required")
            record.state = StrategicObjectiveState.ISSUED_TO_EXECUTIVE_PLANNING
            record.detail = "approved strategic plan issued to executive planning boundary"
        elif request.action == "reject":
            record.state = StrategicObjectiveState.REJECTED
            record.detail = request.resolution_note or "strategic decomposition rejected"
        elif request.action == "archive":
            record.state = StrategicObjectiveState.ARCHIVED
            record.detail = "strategic objective record archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> StrategicObjectiveRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[StrategicObjectiveRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> StrategicObjectiveStatus:
        records = self.list_records(workspace_id)
        blocked = {
            StrategicObjectiveState.BLOCKED,
            StrategicObjectiveState.EVIDENCE_REQUIRED,
            StrategicObjectiveState.REJECTED,
            StrategicObjectiveState.FAILED,
        }
        return StrategicObjectiveStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            review_records=sum(record.state == StrategicObjectiveState.HUMAN_REVIEW_REQUIRED for record in records),
            approved_records=sum(record.state == StrategicObjectiveState.APPROVED for record in records),
            issued_records=sum(record.state == StrategicObjectiveState.ISSUED_TO_EXECUTIVE_PLANNING for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[StrategicObjectiveAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: StrategicObjectiveRecord, actor_id: str, action: str) -> None:
        self._audit.append(
            StrategicObjectiveAudit(
                record_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=record.detail,
            )
        )


strategic_objective_decomposer_service = StrategicObjectiveDecomposerService()
