import pytest

from app.modules.self_learning_performance_optimizer.models import (
    OptimizerAction,
    OptimizerCommand,
    OptimizerCreate,
    OptimizerState,
    PerformanceSample,
)
from app.modules.self_learning_performance_optimizer.service import (
    OptimizerError,
    SelfLearningPerformanceOptimizerService,
)


def sample(r, symbol="XAUUSD", session="london", tag="fvg", grade="A"):
    return PerformanceSample(
        symbol=symbol,
        session=session,
        strategy_tag=tag,
        setup_grade=grade,
        realized_r_multiple=r,
        execution_quality_score=85,
        discipline_score=90,
        risk_efficiency_score=80,
    )


def payload(**overrides):
    samples = [sample(1.2), sample(0.8), sample(1.0), sample(-0.4)]
    data = dict(
        workspace_id="ws-1",
        source_key="journal-window-1",
        journal_record_ids=["j1", "j2", "j3", "j4"],
        samples=samples,
        minimum_sample_size=4,
        upstream_evidence_verified=True,
    )
    data.update(overrides)
    return OptimizerCreate(**data)


def test_builds_governed_recommendation():
    service = SelfLearningPerformanceOptimizerService()
    record = service.create(payload())
    assert record.state == OptimizerState.RECOMMENDATION_READY
    assert record.recommendation is not None
    assert record.recommendation.sample_size == 4
    assert record.recommendation.risk_multiplier <= 1.2
    assert record.recommendation.preferred_segments


def test_missing_evidence_fails_closed():
    service = SelfLearningPerformanceOptimizerService()
    record = service.create(payload(upstream_evidence_verified=False))
    assert record.state == OptimizerState.EVIDENCE_REQUIRED
    assert record.recommendation is None


def test_risk_brain_block_is_authoritative():
    service = SelfLearningPerformanceOptimizerService()
    record = service.create(payload(risk_brain_blocked=True))
    assert record.state == OptimizerState.BLOCKED


def test_human_approval_and_replay_protection():
    service = SelfLearningPerformanceOptimizerService()
    first = service.create(payload())
    approved = service.act("ws-1", first.id, OptimizerAction(
        command=OptimizerCommand.APPROVE, actor="human", approval_token="approval-1"
    ))
    assert approved.state == OptimizerState.APPROVED
    issued = service.act("ws-1", first.id, OptimizerAction(
        command=OptimizerCommand.ISSUE, actor="human", downstream_receipt="receipt-1"
    ))
    assert issued.state == OptimizerState.ISSUED

    second = service.create(payload(source_key="journal-window-2"))
    with pytest.raises(OptimizerError, match="replay"):
        service.act("ws-1", second.id, OptimizerAction(
            command=OptimizerCommand.APPROVE, actor="human", approval_token="approval-1"
        ))


def test_workspace_isolation_and_duplicate_source_protection():
    service = SelfLearningPerformanceOptimizerService()
    record = service.create(payload())
    with pytest.raises(OptimizerError, match="not found"):
        service.get("other-workspace", record.id)
    with pytest.raises(OptimizerError, match="duplicate"):
        service.create(payload())
