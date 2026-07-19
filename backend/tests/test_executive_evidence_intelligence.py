import pytest

from app.executive_evidence_intelligence.models import (
    EvidenceComparisonCreate,
    EvidenceContext,
    EvidenceObservationCreate,
    EvidenceQuery,
    EvidenceSource,
    EvidenceVerdict,
)
from app.executive_evidence_intelligence.service import executive_evidence_intelligence_service


@pytest.fixture(autouse=True)
def reset_service() -> None:
    executive_evidence_intelligence_service.reset()


def context(strategy_id: str, factors: dict | None = None) -> EvidenceContext:
    return EvidenceContext(
        strategy_id=strategy_id,
        strategy_version="1.0",
        account_profile="FTMO-100K",
        symbol="XAUUSD",
        timeframe="M15",
        market_regime="strong_trend",
        session="london",
        killzone="london_open",
        weekday=1,
        news_risk=0.10,
        factors=factors or {"delta_confirmation": True, "fvg": True},
    )


def record(reference: str, strategy_id: str, realized_r: float, confidence: float = 0.70) -> None:
    executive_evidence_intelligence_service.record_observation(
        EvidenceObservationCreate(
            workspace_id="workspace-a",
            actor_id="tester",
            source=EvidenceSource.SHADOW_TRADE,
            source_reference=reference,
            context=context(strategy_id),
            realized_r=realized_r,
            won=realized_r > 0,
            confidence_at_decision=confidence,
            max_favorable_excursion_r=max(realized_r, 0),
            max_adverse_excursion_r=abs(min(realized_r, 0)),
        )
    )


def test_positive_evidence_assessment() -> None:
    for index in range(40):
        record(f"positive-{index}", "ict-trend", 1.5 if index < 26 else -1.0)
    assessment = executive_evidence_intelligence_service.assess(
        EvidenceQuery(
            workspace_id="workspace-a",
            strategy_id="ict-trend",
            symbol="XAUUSD",
            market_regime="strong_trend",
            minimum_sample=30,
        ),
        actor_id="tester",
    )
    assert assessment.verdict == EvidenceVerdict.POSITIVE
    assert assessment.metrics.sample_size == 40
    assert assessment.metrics.expectancy_r > 0
    assert assessment.metrics.profit_factor is not None


def test_minimum_sample_gate() -> None:
    for index in range(5):
        record(f"small-{index}", "ict-trend", 2.0)
    assessment = executive_evidence_intelligence_service.assess(
        EvidenceQuery(workspace_id="workspace-a", strategy_id="ict-trend", minimum_sample=30),
        actor_id="tester",
    )
    assert assessment.verdict == EvidenceVerdict.INSUFFICIENT
    assert "below minimum" in assessment.reasons[0]


def test_factor_specific_evidence() -> None:
    record("factor-match", "ict-trend", 2.0)
    executive_evidence_intelligence_service.record_observation(
        EvidenceObservationCreate(
            workspace_id="workspace-a",
            actor_id="tester",
            source=EvidenceSource.SHADOW_TRADE,
            source_reference="factor-miss",
            context=context("ict-trend", {"delta_confirmation": False, "fvg": True}),
            realized_r=-1.0,
            won=False,
            confidence_at_decision=0.60,
        )
    )
    assessment = executive_evidence_intelligence_service.assess(
        EvidenceQuery(
            workspace_id="workspace-a",
            strategy_id="ict-trend",
            factor_filters={"delta_confirmation": True},
            minimum_sample=1,
        ),
        actor_id="tester",
    )
    assert assessment.metrics.sample_size == 1
    assert assessment.metrics.average_r == 2.0


def test_duplicate_source_reference_is_blocked() -> None:
    record("duplicate", "ict-trend", 1.0)
    with pytest.raises(ValueError):
        record("duplicate", "ict-trend", 1.0)


def test_candidate_comparison_requires_real_edge() -> None:
    for index in range(60):
        record(f"base-{index}", "baseline", 1.0 if index < 35 else -1.0)
        record(f"candidate-{index}", "candidate", 1.5 if index < 42 else -1.0)
    comparison = executive_evidence_intelligence_service.compare(
        EvidenceComparisonCreate(
            workspace_id="workspace-a",
            actor_id="tester",
            baseline_query=EvidenceQuery(workspace_id="workspace-a", strategy_id="baseline", minimum_sample=50),
            candidate_query=EvidenceQuery(workspace_id="workspace-a", strategy_id="candidate", minimum_sample=50),
            minimum_sample=50,
            minimum_expectancy_edge_r=0.10,
        )
    )
    assert comparison.recommendation == "candidate_supported"
    assert comparison.candidate_edge_r >= 0.10


def test_workspace_isolation_and_audit() -> None:
    record("isolated", "ict-trend", 1.0)
    assert len(executive_evidence_intelligence_service.list_observations("workspace-a")) == 1
    assert executive_evidence_intelligence_service.list_observations("workspace-b") == []
    audit = executive_evidence_intelligence_service.audit_records("workspace-a")
    assert len(audit) == 1
    assert audit[0].action == "record"
