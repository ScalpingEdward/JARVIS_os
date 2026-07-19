import pytest

from app.executive_champion_challenger.models import (
    CandidateRole,
    ComparisonCreate,
    ComparisonPolicy,
    EvaluationDecision,
    StrategyCandidateCreate,
    StrategyEvidence,
)
from app.executive_champion_challenger.service import ExecutiveChampionChallengerService


def evidence(sample_size=500, pf=2.0, expectancy=0.30, drawdown=4.0, calibration=0.08):
    return StrategyEvidence(
        sample_size=sample_size,
        win_rate=0.62,
        average_r=0.30,
        expectancy_r=expectancy,
        profit_factor=pf,
        max_drawdown_pct=drawdown,
        confidence_calibration_error=calibration,
    )


def candidate(service, role, version, metrics, workspace="ws-1", account="ftmo-100k"):
    return service.create_candidate(
        StrategyCandidateCreate(
            workspace_id=workspace,
            account_profile_id=account,
            strategy_id="ict-london",
            strategy_version=version,
            role=role,
            evidence=metrics,
            actor_id="researcher",
        )
    )


def test_recommends_and_manually_promotes_stronger_challenger():
    service = ExecutiveChampionChallengerService()
    champion = candidate(service, CandidateRole.CHAMPION, "2.8", evidence(pf=2.0, expectancy=0.30), account="ftmo")
    challenger = candidate(service, CandidateRole.CHALLENGER, "2.9", evidence(pf=2.5, expectancy=0.50, drawdown=3.5), account="ftmo")

    comparison = service.compare(
        ComparisonCreate(
            workspace_id="ws-1",
            account_profile_id="ftmo",
            champion_id=champion.id,
            challenger_id=challenger.id,
            policy=ComparisonPolicy(required_confidence=0.90),
            actor_id="researcher",
        )
    )

    assert comparison.decision == EvaluationDecision.PROMOTION_RECOMMENDED
    assert service.get_candidate(champion.id, "ws-1").role == CandidateRole.CHAMPION

    result = service.promote("ws-1", comparison.id, "risk-committee")
    assert result.promoted is True
    assert service.get_candidate(challenger.id, "ws-1").role == CandidateRole.CHAMPION
    assert service.get_candidate(champion.id, "ws-1").role == CandidateRole.RETIRED


def test_insufficient_sample_never_recommends_promotion():
    service = ExecutiveChampionChallengerService()
    champion = candidate(service, CandidateRole.CHAMPION, "1", evidence(sample_size=30), account="e8")
    challenger = candidate(service, CandidateRole.CHALLENGER, "2", evidence(sample_size=40, pf=4.0, expectancy=1.0), account="e8")
    comparison = service.compare(
        ComparisonCreate(
            workspace_id="ws-1",
            account_profile_id="e8",
            champion_id=champion.id,
            challenger_id=challenger.id,
            actor_id="researcher",
        )
    )
    assert comparison.decision == EvaluationDecision.INSUFFICIENT_EVIDENCE
    assert service.promote("ws-1", comparison.id, "committee").promoted is False


def test_one_champion_per_account_profile():
    service = ExecutiveChampionChallengerService()
    candidate(service, CandidateRole.CHAMPION, "1", evidence(), account="the5ers")
    with pytest.raises(ValueError, match="already has a champion"):
        candidate(service, CandidateRole.CHAMPION, "2", evidence(), account="the5ers")


def test_workspace_and_account_isolation():
    service = ExecutiveChampionChallengerService()
    champion = candidate(service, CandidateRole.CHAMPION, "1", evidence(), workspace="alpha", account="ftmo")
    challenger = candidate(service, CandidateRole.CHALLENGER, "2", evidence(pf=3.0), workspace="alpha", account="e8")
    assert service.get_candidate(champion.id, "beta") is None
    with pytest.raises(ValueError, match="requested account profile"):
        service.compare(
            ComparisonCreate(
                workspace_id="alpha",
                account_profile_id="ftmo",
                champion_id=champion.id,
                challenger_id=challenger.id,
                actor_id="researcher",
            )
        )


def test_drawdown_and_calibration_can_block_promotion():
    service = ExecutiveChampionChallengerService()
    champion = candidate(service, CandidateRole.CHAMPION, "1", evidence(drawdown=3.0), account="fxify")
    challenger = candidate(service, CandidateRole.CHALLENGER, "2", evidence(pf=3.0, expectancy=0.8, drawdown=8.0, calibration=0.4), account="fxify")
    comparison = service.compare(
        ComparisonCreate(
            workspace_id="ws-1",
            account_profile_id="fxify",
            champion_id=champion.id,
            challenger_id=challenger.id,
            policy=ComparisonPolicy(required_confidence=0.80),
            actor_id="researcher",
        )
    )
    assert comparison.decision == EvaluationDecision.KEEP_CHAMPION
    assert any("Drawdown" in reason for reason in comparison.reasons)
    assert any("calibration" in reason for reason in comparison.reasons)
