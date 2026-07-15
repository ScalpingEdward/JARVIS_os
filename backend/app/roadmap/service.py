from copy import deepcopy
from datetime import date, timedelta, datetime, timezone
from uuid import UUID

from .models import (
    AuditEntry, ReplanResponse, RiskItem, RiskReport, RoadmapCreate, RoadmapMilestone,
    RoadmapPriority, RoadmapProgress, RoadmapRecord, RoadmapStatus, RoadmapTask,
    TaskStatusUpdate, TodayPlan, WorkStatus,
)


class RoadmapError(ValueError):
    pass


class RoadmapService:
    def __init__(self) -> None:
        self._items: dict[UUID, RoadmapRecord] = {}

    def reset(self) -> None:
        self._items.clear()

    def create(self, payload: RoadmapCreate) -> RoadmapRecord:
        agents = payload.preferred_agents or ["claude", "codex", "openai", "gemini"]
        today = date.today()
        milestones = [
            RoadmapMilestone(title="Discovery and architecture", objective="Define scope, risks and architecture", sequence=1, due_date=today + timedelta(days=3)),
            RoadmapMilestone(title="Core implementation", objective="Build the primary product capabilities", sequence=2, due_date=today + timedelta(days=10)),
            RoadmapMilestone(title="Verification and review", objective="Test, review and harden the system", sequence=3, due_date=today + timedelta(days=14)),
            RoadmapMilestone(title="Approved release", objective="Document and prepare a human-approved release", sequence=4, due_date=payload.target_date or today + timedelta(days=18)),
        ]
        milestones[1].depends_on = [milestones[0].id]
        milestones[2].depends_on = [milestones[1].id]
        milestones[3].depends_on = [milestones[2].id]
        specs = [
            (0, "Requirements and acceptance criteria", "Convert the goal and constraints into verifiable requirements.", 4, False),
            (0, "Architecture and risk review", "Design components, interfaces, permissions and failure handling.", 6, False),
            (1, "Implement core backend", "Build the core application workflow.", 12, False),
            (1, "Implement operator interface", "Build the control and progress interface.", 10, False),
            (2, "Automated verification", "Add regression, safety and integration tests.", 8, False),
            (2, "Independent quality review", "Review security, maintainability and operational risks.", 6, False),
            (3, "Documentation and rollback plan", "Document setup, operation, backup and rollback.", 5, False),
            (3, "Release approval", "Prepare release evidence for explicit human approval.", 2, True),
        ]
        tasks: list[RoadmapTask] = []
        previous: UUID | None = None
        for index, (milestone_index, title, description, hours, approval) in enumerate(specs):
            task = RoadmapTask(
                title=title, description=description, milestone_id=milestones[milestone_index].id,
                priority=payload.priority if index < 4 else RoadmapPriority.normal,
                assigned_agent=agents[index % len(agents)], reviewer_agent=agents[(index + 1) % len(agents)],
                depends_on=[previous] if previous else [], estimated_hours=hours,
                due_date=milestones[milestone_index].due_date, approval_required=approval,
            )
            task.status = WorkStatus.ready if previous is None else WorkStatus.pending
            tasks.append(task)
            milestones[milestone_index].task_ids.append(task.id)
            previous = task.id
        record = RoadmapRecord(
            title=payload.title, goal=payload.goal, target_date=payload.target_date,
            priority=payload.priority, constraints=payload.constraints, milestones=milestones, tasks=tasks,
            status=RoadmapStatus.active,
            audit_log=[AuditEntry(action="roadmap_created", details="Long-term roadmap generated from project goal")],
        )
        self._items[record.id] = record
        return deepcopy(record)

    def get(self, roadmap_id: UUID) -> RoadmapRecord:
        if roadmap_id not in self._items:
            raise RoadmapError("Roadmap not found")
        return deepcopy(self._items[roadmap_id])

    def update_task(self, roadmap_id: UUID, task_id: UUID, payload: TaskStatusUpdate) -> RoadmapRecord:
        roadmap = self._require(roadmap_id)
        task = next((item for item in roadmap.tasks if item.id == task_id), None)
        if task is None:
            raise RoadmapError("Task not found")
        if payload.status == WorkStatus.in_progress and not self._dependencies_complete(roadmap, task):
            raise RoadmapError("Task dependencies are not completed")
        if payload.status == WorkStatus.blocked and not payload.blocker:
            raise RoadmapError("A blocker description is required")
        task.status, task.blocker = payload.status, payload.blocker
        self._refresh(roadmap)
        roadmap.audit_log.append(AuditEntry(action="task_updated", details=f"{task.title}: {payload.status.value}"))
        return deepcopy(roadmap)

    def progress(self, roadmap_id: UUID) -> RoadmapProgress:
        roadmap = self._require(roadmap_id)
        completed = sum(task.status == WorkStatus.completed for task in roadmap.tasks)
        completed_milestones = sum(m.status == WorkStatus.completed for m in roadmap.milestones)
        return RoadmapProgress(
            roadmap_id=roadmap.id, status=roadmap.status,
            progress_percent=round(completed * 100 / len(roadmap.tasks)) if roadmap.tasks else 100,
            completed_tasks=completed, total_tasks=len(roadmap.tasks),
            completed_milestones=completed_milestones, total_milestones=len(roadmap.milestones),
        )

    def today(self, roadmap_id: UUID, capacity_hours: int = 8) -> TodayPlan:
        roadmap = self._require(roadmap_id)
        selected: list[UUID] = []
        used = 0
        for task in sorted(roadmap.tasks, key=lambda item: (item.priority != RoadmapPriority.critical, item.due_date or date.max)):
            if task.status in {WorkStatus.ready, WorkStatus.in_progress} and used + task.estimated_hours <= capacity_hours:
                selected.append(task.id)
                used += task.estimated_hours
        return TodayPlan(roadmap_id=roadmap.id, generated_for=date.today(), task_ids=selected, estimated_hours=used)

    def risks(self, roadmap_id: UUID) -> RiskReport:
        roadmap = self._require(roadmap_id)
        today = date.today()
        risks: list[RiskItem] = []
        for task in roadmap.tasks:
            if task.status == WorkStatus.blocked:
                risks.append(RiskItem(level=RoadmapPriority.high, code="blocked_task", message=task.blocker or "Task blocked", task_id=task.id))
            if task.due_date and task.due_date < today and task.status != WorkStatus.completed:
                risks.append(RiskItem(level=RoadmapPriority.critical, code="overdue_task", message=f"{task.title} is overdue", task_id=task.id))
        if roadmap.target_date and roadmap.target_date < today and roadmap.status != RoadmapStatus.completed:
            risks.append(RiskItem(level=RoadmapPriority.critical, code="roadmap_overdue", message="Roadmap target date has passed"))
        return RiskReport(roadmap_id=roadmap.id, risks=risks, count=len(risks))

    def replan(self, roadmap_id: UUID) -> ReplanResponse:
        roadmap = self._require(roadmap_id)
        changed: list[UUID] = []
        cursor = date.today()
        for task in roadmap.tasks:
            if task.status == WorkStatus.completed:
                continue
            cursor += timedelta(days=max(1, task.estimated_hours // 6))
            if task.due_date != cursor:
                task.due_date = cursor
                changed.append(task.id)
        roadmap.updated_at = datetime.now(timezone.utc)
        roadmap.audit_log.append(AuditEntry(action="roadmap_replanned", details=f"Rescheduled {len(changed)} open tasks"))
        self._refresh(roadmap)
        return ReplanResponse(roadmap=deepcopy(roadmap), changed_task_ids=changed)

    def _require(self, roadmap_id: UUID) -> RoadmapRecord:
        if roadmap_id not in self._items:
            raise RoadmapError("Roadmap not found")
        return self._items[roadmap_id]

    @staticmethod
    def _dependencies_complete(roadmap: RoadmapRecord, task: RoadmapTask) -> bool:
        completed = {item.id for item in roadmap.tasks if item.status == WorkStatus.completed}
        return set(task.depends_on) <= completed

    def _refresh(self, roadmap: RoadmapRecord) -> None:
        completed_ids = {task.id for task in roadmap.tasks if task.status == WorkStatus.completed}
        for task in roadmap.tasks:
            if task.status == WorkStatus.pending and set(task.depends_on) <= completed_ids:
                task.status = WorkStatus.ready
        for milestone in roadmap.milestones:
            related = [task for task in roadmap.tasks if task.milestone_id == milestone.id]
            if related and all(task.status == WorkStatus.completed for task in related):
                milestone.status = WorkStatus.completed
            elif any(task.status == WorkStatus.blocked for task in related):
                milestone.status = WorkStatus.blocked
            elif any(task.status in {WorkStatus.ready, WorkStatus.in_progress} for task in related):
                milestone.status = WorkStatus.in_progress
        if all(task.status == WorkStatus.completed for task in roadmap.tasks):
            roadmap.status = RoadmapStatus.completed
        elif any(task.status == WorkStatus.blocked for task in roadmap.tasks):
            roadmap.status = RoadmapStatus.blocked
        else:
            roadmap.status = RoadmapStatus.active
        roadmap.updated_at = datetime.now(timezone.utc)


roadmap_service = RoadmapService()
