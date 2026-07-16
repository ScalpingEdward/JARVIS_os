from app.company_runtime.models import RuntimeMissionCreate, RuntimeStatus, RuntimeUpdate
from app.company_runtime.service import company_runtime_service


def setup_function() -> None:
    company_runtime_service.reset()


def test_runtime_claim_budget_retry_and_dead_letter() -> None:
    mission = company_runtime_service.create(
        RuntimeMissionCreate(
            title="Build connector",
            objective="Implement and test a connector",
            priority=1,
            token_limit=100,
            cost_limit_usd=1.0,
            max_retries=1,
        )
    )
    claimed = company_runtime_service.claim_next()
    assert claimed is not None
    assert claimed.id == mission.id
    assert claimed.status == RuntimeStatus.assigned

    retried = company_runtime_service.update(
        mission.id,
        RuntimeUpdate(status=RuntimeStatus.failed, tokens_used_delta=50, cost_used_delta_usd=0.5),
    )
    assert retried is not None
    assert retried.status == RuntimeStatus.queued
    assert retried.retry_count == 1

    dead = company_runtime_service.update(
        mission.id,
        RuntimeUpdate(status=RuntimeStatus.failed),
    )
    assert dead is not None
    assert dead.status == RuntimeStatus.dead_letter


def test_completion_requires_human_approval() -> None:
    mission = company_runtime_service.create(
        RuntimeMissionCreate(title="Release", objective="Prepare release")
    )
    waiting = company_runtime_service.update(
        mission.id,
        RuntimeUpdate(status=RuntimeStatus.completed),
    )
    assert waiting is not None
    assert waiting.status == RuntimeStatus.waiting_approval

    approved = company_runtime_service.approve(mission.id)
    assert approved is not None
    assert approved.status == RuntimeStatus.completed

    report = company_runtime_service.report()
    assert report.completed == 1
    assert report.automatic_merge is False
    assert report.automatic_order_execution is False
