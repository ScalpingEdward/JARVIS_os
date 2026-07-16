from app.company.models import MissionCreate, WorkStatus
from app.company.service import company_service


def setup_function() -> None:
    company_service.reset()


def test_company_has_nine_specialized_agents() -> None:
    agents = company_service.list_agents()
    assert len(agents) == 9
    assert {agent.role.value for agent in agents} == {
        "ceo", "quant", "trading", "research", "backend", "frontend", "qa", "security", "business"
    }


def test_mission_is_decomposed_with_dependencies_and_reviews() -> None:
    detail = company_service.create_mission(
        MissionCreate(title="Build market intelligence", objective="Create a safe supervised intelligence workflow")
    )
    assert len(detail.work_items) == 5
    assert detail.ready_count == 1
    assert detail.blocked_count == 4
    assert detail.work_items[-1].requires_human_approval is True


def test_release_cannot_complete_without_human_approval() -> None:
    detail = company_service.create_mission(
        MissionCreate(title="Prepare release", objective="Build and review a supervised software release")
    )
    for item in detail.work_items[:-1]:
        company_service.update_work_item(item.id, WorkStatus.COMPLETED, "done")
    release = company_service.get_mission(detail.mission.id).work_items[-1]
    updated = company_service.update_work_item(release.id, WorkStatus.COMPLETED, "ready")
    assert updated.status == WorkStatus.REVIEW


def test_company_status_disables_automatic_merge_and_trading() -> None:
    status = company_service.status()
    assert status.automatic_merge is False
    assert status.automatic_order_execution is False
    assert status.operating_mode == "human_supervised"
