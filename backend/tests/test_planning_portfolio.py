from uuid import uuid4

import pytest

from app.planning_portfolio.models import (
    ApprovalRequest,
    CapacityProfile,
    PortfolioAnalysisRequest,
    PortfolioCandidate,
    PortfolioCreate,
    PortfolioState,
)
from app.planning_portfolio.service import PlanningPortfolioService


@pytest.fixture
def service() -> PlanningPortfolioService:
    return PlanningPortfolioService()


def _portfolio(service: PlanningPortfolioService, workspace: str = "alpha"):
    first = uuid4()
    second = uuid4()
    return service.create(
        PortfolioCreate(
            workspace_id=workspace,
            owner_id="owner-1",
            key="jarvis.portfolio",
            title="JARVIS delivery portfolio",
            max_total_cost=120,
            max_parallel_plans=2,
            capacity_profiles=[CapacityProfile(capability="python", available_units=2, planning_window_minutes=480)],
            candidates=[
                PortfolioCandidate(
                    plan_id=first,
                    selected_option_key="safe",
                    strategic_value=0.9,
                    urgency=0.8,
                    confidence=0.9,
                    estimated_cost=60,
                    required_capacity={"python": 1},
                ),
                PortfolioCandidate(
                    plan_id=second,
                    selected_option_key="fast",
                    strategic_value=0.7,
                    urgency=0.6,
                    confidence=0.7,
                    estimated_cost=80,
                    required_capacity={"python": 2},
                ),
            ],
        )
    )


def test_analysis_selects_best_fitting_candidates(service: PlanningPortfolioService) -> None:
    portfolio = _portfolio(service)
    analysis = service.analyze(
        portfolio.id,
        PortfolioAnalysisRequest(workspace_id="alpha", actor_id="planner-1"),
    )
    assert len(analysis.recommended_sequence) == 1
    assert len(analysis.deferred_plan_ids) == 1
    assert analysis.total_selected_cost <= 120
    assert analysis.replanning_actions


def test_owner_cannot_self_approve(service: PlanningPortfolioService) -> None:
    portfolio = _portfolio(service)
    service.analyze(portfolio.id, PortfolioAnalysisRequest(workspace_id="alpha", actor_id="planner"))
    with pytest.raises(ValueError, match="self-approve"):
        service.approve(portfolio.id, ApprovalRequest(workspace_id="alpha", reviewer_id="owner-1"))


def test_independent_approval(service: PlanningPortfolioService) -> None:
    portfolio = _portfolio(service)
    service.analyze(portfolio.id, PortfolioAnalysisRequest(workspace_id="alpha", actor_id="planner"))
    approved = service.approve(
        portfolio.id,
        ApprovalRequest(workspace_id="alpha", reviewer_id="reviewer-2"),
    )
    assert approved.state == PortfolioState.APPROVED
    assert service.status("alpha").approved_portfolios == 1


def test_workspace_isolation(service: PlanningPortfolioService) -> None:
    portfolio = _portfolio(service)
    assert service.get("beta", portfolio.id) is None
    with pytest.raises(ValueError, match="not found"):
        service.analyze(portfolio.id, PortfolioAnalysisRequest(workspace_id="beta", actor_id="planner"))


def test_invalid_dependency_is_rejected() -> None:
    first = uuid4()
    with pytest.raises(ValueError, match="dependencies"):
        PortfolioCreate(
            workspace_id="alpha",
            owner_id="owner",
            key="invalid",
            title="Invalid",
            candidates=[
                PortfolioCandidate(plan_id=first, selected_option_key="a", dependencies=[uuid4()]),
                PortfolioCandidate(plan_id=uuid4(), selected_option_key="b"),
            ],
        )


def test_automatic_external_action_is_rejected() -> None:
    with pytest.raises(ValueError, match="automatic external actions"):
        PortfolioCreate(
            workspace_id="alpha",
            owner_id="owner",
            key="unsafe",
            title="Unsafe",
            candidates=[
                PortfolioCandidate(plan_id=uuid4(), selected_option_key="a"),
                PortfolioCandidate(plan_id=uuid4(), selected_option_key="b"),
            ],
            automatic_external_action=True,
        )
