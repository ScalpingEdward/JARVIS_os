from datetime import datetime, timezone
from uuid import UUID

from .models import AuditEntry, RuntimeMission, RuntimeMissionCreate, RuntimeReport, RuntimeStatus, RuntimeUpdate


class CompanyRuntimeService:
    def __init__(self) -> None:
        self._missions: dict[UUID, RuntimeMission] = {}
        self._audit: list[AuditEntry] = []

    def create(self, payload: RuntimeMissionCreate) -> RuntimeMission:
        mission = RuntimeMission(**payload.model_dump())
        self._missions[mission.id] = mission
        self._audit.append(AuditEntry(mission_id=mission.id, action="mission_created"))
        return mission

    def list_all(self) -> list[RuntimeMission]:
        return sorted(self._missions.values(), key=lambda item: (item.priority, item.created_at))

    def get(self, mission_id: UUID) -> RuntimeMission | None:
        return self._missions.get(mission_id)

    def claim_next(self) -> RuntimeMission | None:
        candidates = [m for m in self.list_all() if m.status == RuntimeStatus.queued]
        if not candidates:
            return None
        mission = candidates[0]
        mission.status = RuntimeStatus.assigned
        mission.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditEntry(mission_id=mission.id, action="mission_claimed"))
        return mission

    def update(self, mission_id: UUID, payload: RuntimeUpdate) -> RuntimeMission | None:
        mission = self._missions.get(mission_id)
        if mission is None:
            return None
        mission.tokens_used += payload.tokens_used_delta
        mission.cost_used_usd += payload.cost_used_delta_usd
        mission.status = payload.status
        if mission.tokens_used > mission.token_limit or mission.cost_used_usd > mission.cost_limit_usd:
            mission.status = RuntimeStatus.failed
            payload.note = "Budget limit exceeded"
        if mission.status == RuntimeStatus.failed:
            if mission.retry_count < mission.max_retries:
                mission.retry_count += 1
                mission.status = RuntimeStatus.queued
            else:
                mission.status = RuntimeStatus.dead_letter
        if mission.status == RuntimeStatus.completed and mission.requires_human_approval:
            mission.status = RuntimeStatus.waiting_approval
        mission.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditEntry(mission_id=mission.id, action=f"status:{mission.status.value}", note=payload.note))
        return mission

    def approve(self, mission_id: UUID) -> RuntimeMission | None:
        mission = self._missions.get(mission_id)
        if mission is None or mission.status != RuntimeStatus.waiting_approval:
            return None
        mission.status = RuntimeStatus.completed
        mission.updated_at = datetime.now(timezone.utc)
        self._audit.append(AuditEntry(mission_id=mission.id, action="human_approved"))
        return mission

    def audit(self, mission_id: UUID | None = None) -> list[AuditEntry]:
        if mission_id is None:
            return list(self._audit)
        return [entry for entry in self._audit if entry.mission_id == mission_id]

    def report(self) -> RuntimeReport:
        values = list(self._missions.values())
        return RuntimeReport(
            queued=sum(m.status == RuntimeStatus.queued for m in values),
            active=sum(m.status in {RuntimeStatus.assigned, RuntimeStatus.working} for m in values),
            waiting_review=sum(m.status == RuntimeStatus.waiting_review for m in values),
            waiting_approval=sum(m.status == RuntimeStatus.waiting_approval for m in values),
            completed=sum(m.status == RuntimeStatus.completed for m in values),
            failed=sum(m.status == RuntimeStatus.failed for m in values),
            dead_letter=sum(m.status == RuntimeStatus.dead_letter for m in values),
            total_cost_usd=round(sum(m.cost_used_usd for m in values), 4),
            total_tokens=sum(m.tokens_used for m in values),
        )

    def reset(self) -> None:
        self._missions.clear()
        self._audit.clear()


company_runtime_service = CompanyRuntimeService()
