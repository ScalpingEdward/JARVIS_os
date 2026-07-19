from uuid import uuid4

import pytest

from app.executive_talent.models import Criticality, Readiness, RiskLevel, SuccessorCandidate, TalentPortfolioCreate, TalentRole, TalentUpdate, WorkforceScenario
from app.executive_talent.service import ExecutiveTalentService


def build_payload(workspace_id: str = "workspace-a") -> TalentPortfolioCreate:
    critical = TalentRole(name="Chief Operations Officer", owner_id="coo", criticality=Criticality.critical, required_capacity=1, available_capacity=0.7, required_skills=["operations", "crisis"], covered_skills=["operations"], retention_risk=RiskLevel.high)
    standard = TalentRole(name="Analytics Lead", owner_id="analytics", required_capacity=2, available_capacity=2, required_skills=["data"], covered_skills=["data"])
    successor = SuccessorCandidate(role_id=critical.role_id, person_id="candidate-1", readiness=Readiness.developing, readiness_score=60)
    scenario = WorkforceScenario(name="Executive departure", probability=0.4, capacity_impact=70, affected_role_ids=[critical.role_id], mitigation_strength=30)
    return TalentPortfolioCreate(workspace_id=workspace_id, name="Leadership Portfolio", executive_owner_id="ceo", roles=[critical, standard], successors=[successor], scenarios=[scenario])


def test_assessment_surfaces_capacity_skill_and_succession_gaps():
    service = ExecutiveTalentService()
    item = service.create(build_payload())
    assessed = service.assess(item.portfolio_id, "workspace-a", "board")
    assert assessed.capacity_coverage_score < 100
    assert assessed.skill_coverage_score < 100
    assert assessed.succession_readiness_score == 0
    assert len(assessed.critical_role_gaps) == 1
    assert assessed.executive_actions
    assert assessed.autonomous_actions_enabled is False


def test_update_improves_successor_readiness():
    service = ExecutiveTalentService()
    item = service.create(build_payload())
    role = item.roles[0]
    candidate = item.successors[0]
    service.update(item.portfolio_id, "workspace-a", TalentUpdate(role_id=role.role_id, candidate_id=candidate.candidate_id, readiness=Readiness.ready_now, readiness_score=90, actor_id="chro"))
    assessed = service.assess(item.portfolio_id, "workspace-a", "chro")
    assert assessed.succession_readiness_score == 100
    assert assessed.critical_role_gaps == []


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveTalentService()
    item = service.create(build_payload())
    assert service.get(item.portfolio_id, "workspace-b") is None
    with pytest.raises(ValueError):
        service.create(build_payload())


def test_unknown_role_reference_is_rejected():
    payload = build_payload()
    with pytest.raises(ValueError):
        TalentPortfolioCreate(workspace_id="x", name="Invalid", executive_owner_id="ceo", roles=payload.roles, successors=[SuccessorCandidate(role_id=uuid4(), person_id="ghost")])
