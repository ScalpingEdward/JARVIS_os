import hashlib
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from .models import (
    RoadmapAudit,
    RoadmapCreate,
    RoadmapExecuteRequest,
    RoadmapMilestone,
    RoadmapRecord,
    RoadmapState,
    RoadmapStatus,
)


class ExecutiveRoadmapService:
    def __init__(self) -> None:
        self._records: dict[UUID, RoadmapRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._budget_tokens: set[tuple[str, str]] = set()
        self._kpi_receipts: set[tuple[str, str]] = set()
        self._audit: list[RoadmapAudit] = []

    def create(self, payload: RoadmapCreate) -> RoadmapRecord:
        source_key = (payload.workspace_id, payload.source_key)
        budget_key = (payload.workspace_id, payload.budget_approval_token)
        if source_key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        if budget_key in self._budget_tokens:
            raise ValueError("budget approval token already consumed")

        state, detail, milestones, confidence = self._generate(payload)
        record = RoadmapRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            milestones=milestones,
            total_budget=round(sum(item.allocated_budget for item in payload.workstreams), 2),
            total_expected_value=round(sum(item.expected_value for item in payload.workstreams), 2),
            roadmap_confidence=confidence,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._budget_tokens.add(budget_key)
        self._log(record, payload.actor_id, "create")
        return record

    def _generate(self, payload: RoadmapCreate):
        if payload.upstream_risk_brain_blocked:
            return RoadmapState.BLOCKED, "upstream Risk Brain hard block", [], 0
        if not payload.v21_04_budget_approved:
            return RoadmapState.EVIDENCE_REQUIRED, "approved v21.04 budget evidence required", [], 0
        if not payload.strategic_constraints:
            return RoadmapState.EVIDENCE_REQUIRED, "strategic constraints are required", [], 0
        if not payload.workstreams:
            return RoadmapState.EVIDENCE_REQUIRED, "at least one funded workstream is required", [], 0

        blocked = [item.workstream_id for item in payload.workstreams if not item.dependency_ready]
        if blocked:
            return RoadmapState.BLOCKED, f"dependency-blocked workstreams: {', '.join(blocked)}", [], 0

        ordered = sorted(payload.workstreams, key=lambda item: (item.priority_rank, -item.expected_value))
        today = date.today()
        horizon_end = today + timedelta(days=payload.planning_horizon_days)
        lane_ends = [today for _ in range(payload.max_parallel_workstreams)]
        milestones: list[RoadmapMilestone] = []
        schedule_conflict = False

        for sequence, item in enumerate(ordered, start=1):
            lane = min(range(len(lane_ends)), key=lambda index: lane_ends[index])
            start = max(today, lane_ends[lane])
            if item.target_start:
                start = max(start, item.target_start)
            duration = max(7, min(90, item.effort_points * 2))
            end = start + timedelta(days=duration)
            if item.target_end and end > item.target_end:
                schedule_conflict = True
            if end > horizon_end:
                schedule_conflict = True
            lane_ends[lane] = end
            milestones.append(
                RoadmapMilestone(
                    milestone_id=f"RM-{sequence:03d}",
                    title=item.title,
                    sequence=sequence,
                    owner_role=item.owner_role,
                    start_date=start,
                    end_date=end,
                    workstream_ids=[item.workstream_id],
                    allocated_budget=item.allocated_budget,
                    expected_value=item.expected_value,
                    dependencies=item.dependencies,
                    exit_criteria=[
                        "approved scope completed",
                        "acceptance evidence recorded",
                        "budget variance reviewed",
                        "Risk Brain authority unchanged",
                    ],
                )
            )

        budget = sum(item.allocated_budget for item in ordered)
        value = sum(item.expected_value for item in ordered)
        roi_signal = min(25.0, (value / budget * 10) if budget else 0)
        confidence = round(min(100.0, 60 + roi_signal + min(len(ordered) * 2, 10)), 2)
        if schedule_conflict:
            return RoadmapState.SCHEDULE_CONFLICT, "roadmap generated with horizon or target-date conflicts", milestones, max(35, confidence - 25)
        return RoadmapState.HUMAN_REVIEW_REQUIRED, "executive roadmap generated; explicit approval required", milestones, confidence

    def execute(self, record_id: UUID, workspace_id: str, request: RoadmapExecuteRequest) -> RoadmapRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("roadmap record not found")

        if request.action == "approve-roadmap":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state not in {RoadmapState.HUMAN_REVIEW_REQUIRED, RoadmapState.ROADMAP_READY}:
                raise ValueError("roadmap approval unavailable")
            raw = f"{workspace_id}:{record.id}:{record.request.budget_approval_token}:{len(record.milestones)}"
            record.approval_token = hashlib.sha256(raw.encode()).hexdigest()
            record.state = RoadmapState.APPROVED
            record.detail = "executive roadmap approved"
        elif request.action == "issue-to-kpi":
            if not request.human_approved:
                raise ValueError("human approval required")
            if record.state != RoadmapState.APPROVED or not record.approval_token:
                raise ValueError("approved roadmap required")
            if not request.kpi_receipt_id:
                raise ValueError("kpi receipt id required")
            receipt_key = (workspace_id, request.kpi_receipt_id)
            if receipt_key in self._kpi_receipts:
                raise ValueError("kpi receipt already consumed")
            self._kpi_receipts.add(receipt_key)
            record.state = RoadmapState.ISSUED_TO_KPI
            record.detail = "approved roadmap issued to v21.06 KPI boundary"
        elif request.action == "request-review":
            if record.state != RoadmapState.SCHEDULE_CONFLICT:
                raise ValueError("review request unavailable")
            record.state = RoadmapState.HUMAN_REVIEW_REQUIRED
            record.detail = request.resolution_note or "schedule conflict escalated for human resolution"
        elif request.action == "reject":
            record.state = RoadmapState.REJECTED
            record.detail = request.resolution_note or "executive roadmap rejected"
        elif request.action == "archive":
            record.state = RoadmapState.ARCHIVED
            record.detail = "executive roadmap archived"
        else:
            raise ValueError("unsupported action")

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> RoadmapRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[RoadmapRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> RoadmapStatus:
        records = self.list_records(workspace_id)
        blocked = {RoadmapState.BLOCKED, RoadmapState.EVIDENCE_REQUIRED, RoadmapState.REJECTED, RoadmapState.FAILED}
        return RoadmapStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            ready_records=sum(record.state in {RoadmapState.ROADMAP_READY, RoadmapState.HUMAN_REVIEW_REQUIRED} for record in records),
            approved_records=sum(record.state == RoadmapState.APPROVED for record in records),
            issued_records=sum(record.state == RoadmapState.ISSUED_TO_KPI for record in records),
            conflict_records=sum(record.state == RoadmapState.SCHEDULE_CONFLICT for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[RoadmapAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: RoadmapRecord, actor_id: str, action: str) -> None:
        self._audit.append(RoadmapAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


executive_roadmap_service = ExecutiveRoadmapService()
