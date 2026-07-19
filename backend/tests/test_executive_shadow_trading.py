from uuid import uuid4

import pytest

from app.executive_shadow_trading.models import (
    ExperimentCreate,
    ExperimentStatus,
    ExperimentStatusUpdate,
    FactorSnapshot,
    ShadowDirection,
    ShadowOutcome,
    ShadowTradeCreate,
    ShadowTradeResult,
)
from app.executive_shadow_trading.service import ExecutiveShadowTradingService


def running_experiment(service: ExecutiveShadowTradingService, workspace: str = "alpha"):
    experiment = service.create_experiment(ExperimentCreate(
        workspace_id=workspace,
        name="London XAU Delta Validation",
        strategy_id="ict-xau-london",
        hypothesis="Delta improves reversal selection during London open",
        minimum_sample_size=20,
        permitted_account_profiles=["ftmo-100k-shadow"],
    ))
    service.update_status(experiment.id, workspace, ExperimentStatusUpdate(status=ExperimentStatus.running, actor_id="researcher"))
    return experiment


def test_shadow_prediction_and_resolution_recalculate_metrics():
    service = ExecutiveShadowTradingService()
    experiment = running_experiment(service)
    trade = service.create_trade(ShadowTradeCreate(
        workspace_id="alpha",
        experiment_id=experiment.id,
        strategy_id="ict-xau-london",
        account_profile_id="ftmo-100k-shadow",
        symbol="XAUUSD",
        session="london",
        market_regime="bullish_reversal",
        direction=ShadowDirection.long,
        entry_price=2400,
        stop_price=2395,
        target_price=2415,
        confidence=0.72,
        factors=[FactorSnapshot(name="delta", value=420, weight=0.25)],
    ))
    resolved = service.resolve_trade(trade.id, "alpha", ShadowTradeResult(
        outcome=ShadowOutcome.win,
        exit_price=2415,
        realized_r=3,
        max_favorable_excursion_r=3.2,
        max_adverse_excursion_r=0.4,
    ), "market-replay")
    updated = service.get_experiment(experiment.id, "alpha")
    assert resolved.outcome == ShadowOutcome.win
    assert updated is not None
    assert updated.sample_size == 1
    assert updated.win_rate == 1
    assert updated.expectancy_r == 3
    assert updated.promotion_eligible is False
    assert "minimum_sample_size_not_reached" in updated.rejection_reasons


def test_experiment_must_run_before_shadow_trade():
    service = ExecutiveShadowTradingService()
    experiment = service.create_experiment(ExperimentCreate(
        workspace_id="alpha",
        name="Draft",
        strategy_id="smc",
        hypothesis="Test",
        minimum_sample_size=20,
    ))
    with pytest.raises(ValueError, match="must be running"):
        service.create_trade(ShadowTradeCreate(
            workspace_id="alpha",
            experiment_id=experiment.id,
            strategy_id="smc",
            symbol="EURUSD",
            session="new_york",
            market_regime="trend",
            direction=ShadowDirection.short,
            entry_price=1.10,
            stop_price=1.11,
            target_price=1.08,
            confidence=0.6,
        ))


def test_workspace_and_account_profile_isolation():
    service = ExecutiveShadowTradingService()
    experiment = running_experiment(service)
    assert service.get_experiment(experiment.id, "other") is None
    with pytest.raises(ValueError, match="not permitted"):
        service.create_trade(ShadowTradeCreate(
            workspace_id="alpha",
            experiment_id=experiment.id,
            strategy_id="ict-xau-london",
            account_profile_id="live-account",
            symbol="XAUUSD",
            session="london",
            market_regime="reversal",
            direction=ShadowDirection.long,
            entry_price=2400,
            stop_price=2395,
            target_price=2410,
            confidence=0.7,
        ))


def test_invalid_trade_geometry_rejected():
    with pytest.raises(ValueError, match="stop < entry < target"):
        ShadowTradeCreate(
            workspace_id="alpha",
            experiment_id=uuid4(),
            strategy_id="smc",
            symbol="XAUUSD",
            session="london",
            market_regime="trend",
            direction=ShadowDirection.long,
            entry_price=2400,
            stop_price=2405,
            target_price=2410,
            confidence=0.5,
        )


def test_resolved_trade_cannot_be_resolved_twice():
    service = ExecutiveShadowTradingService()
    experiment = running_experiment(service)
    trade = service.create_trade(ShadowTradeCreate(
        workspace_id="alpha",
        experiment_id=experiment.id,
        strategy_id="ict-xau-london",
        account_profile_id="ftmo-100k-shadow",
        symbol="XAUUSD",
        session="london",
        market_regime="range",
        direction=ShadowDirection.short,
        entry_price=2400,
        stop_price=2405,
        target_price=2390,
        confidence=0.55,
    ))
    result = ShadowTradeResult(
        outcome=ShadowOutcome.loss,
        exit_price=2405,
        realized_r=-1,
        max_favorable_excursion_r=0.2,
        max_adverse_excursion_r=1,
    )
    service.resolve_trade(trade.id, "alpha", result, "replay")
    with pytest.raises(ValueError, match="already been resolved"):
        service.resolve_trade(trade.id, "alpha", result, "replay")
