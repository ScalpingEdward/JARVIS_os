from datetime import date, timedelta

import pytest

from app.roadmap.models import RoadmapCreate, TaskStatusUpdate, WorkStatus
from app.roadmap.service import RoadmapError, roadmap_service


def setup_function() -> None:
    roadmap_service.reset()


def _roadmap():
    return roadmap_service.create(
        RoadmapCreate(
            title="JARVIS v1",
            goal="Build a production-ready autonomous software engineering assistant",
            constraints=["No automatic merge", "Human approval for release"],
        )
    )


def test_create_generates_milestones_tasks_agents_and_approval_gate() -> None:
    roadmap = _roadmap()
    assert len(roadmap.milestones) == 4
    assert len(roadmap.tasks) == 8
    assert roadmap.tasks[0].status == WorkStatus.ready
    assert roadmap.tasks[-1].approval_required is True
    assert roadmap.audit_log[0].action == "roadmap_created"


def test_dependencies_unlock_next_task_and_progress_updates() -> None:
    roadmap = _roadmap()
    first, second = roadmap.tasks[0], roadmap.tasks[1]
    with pytest.raises(RoadmapError, match="dependencies"):
        roadmap_service.update_task(roadmap.id, second.id, TaskStatusUpdate(status=WorkStatus.in_progress))
    roadmap_service.update_task(roadmap.id, first.id, TaskStatusUpdate(status=WorkStatus.completed))
    updated = roadmap_service.get(roadmap.id)
    assert next(task for task in updated.tasks if task.id == second.id).status == WorkStatus.ready
    assert roadmap_service.progress(roadmap.id).completed_tasks == 1


def test_today_plan_respects_capacity() -> None:
    roadmap = _roadmap()
    plan = roadmap_service.today(roadmap.id, capacity_hours=4)
    assert plan.estimated_hours <= 4
    assert plan.task_ids == [roadmap.tasks[0].id]


def test_blockers_and_overdue_tasks_appear_as_risks() -> None:
    roadmap = _roadmap()
    first = roadmap.tasks[0]
    roadmap_service.update_task(
        roadmap.id,
        first.id,
        TaskStatusUpdate(status=WorkStatus.blocked, blocker="External API unavailable"),
    )
    internal = roadmap_service._items[roadmap.id]
    internal.tasks[0].due_date = date.today() - timedelta(days=1)
    report = roadmap_service.risks(roadmap.id)
    assert {risk.code for risk in report.risks} == {"blocked_task", "overdue_task"}


def test_replan_changes_only_open_tasks_and_records_audit_entry() -> None:
    roadmap = _roadmap()
    first = roadmap.tasks[0]
    roadmap_service.update_task(roadmap.id, first.id, TaskStatusUpdate(status=WorkStatus.completed))
    result = roadmap_service.replan(roadmap.id)
    assert first.id not in result.changed_task_ids
    assert result.roadmap.audit_log[-1].action == "roadmap_replanned"


def test_api_exposes_roadmap_progress_today_risks_and_replan(client) -> None:
    created = client.post(
        "/v1/roadmaps",
        json={"title": "Trading platform", "goal": "Build a safe Telegram signal trading platform"},
    )
    assert created.status_code == 200
    roadmap_id = created.json()["id"]
    assert client.get(f"/v1/roadmaps/{roadmap_id}/progress").status_code == 200
    assert client.get(f"/v1/roadmaps/{roadmap_id}/today").status_code == 200
    assert client.get(f"/v1/roadmaps/{roadmap_id}/risks").status_code == 200
    assert client.post(f"/v1/roadmaps/{roadmap_id}/replan").status_code == 200
