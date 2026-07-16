from app.predictive_intelligence.models import ForecastRequest, MarketRegime, MarketSignal, WhatIfRequest
from app.predictive_intelligence.service import predictive_intelligence_service


def setup_function() -> None:
    predictive_intelligence_service.reset()


def test_forecast_ranks_best_market_and_remains_human_gated() -> None:
    report = predictive_intelligence_service.generate(
        ForecastRequest(
            signals=[
                MarketSignal(
                    symbol="XAUUSD",
                    structure_score=0.92,
                    orderflow_score=0.88,
                    liquidity_score=0.86,
                    volatility_score=0.55,
                    news_risk=0.2,
                    confidence=0.9,
                    regime=MarketRegime.trending,
                ),
                MarketSignal(
                    symbol="EURUSD",
                    structure_score=0.55,
                    orderflow_score=0.5,
                    liquidity_score=0.6,
                    volatility_score=0.45,
                    news_risk=0.35,
                    confidence=0.62,
                    regime=MarketRegime.ranging,
                ),
            ]
        )
    )
    assert report.owner_name == "MASTER Brano"
    assert report.opportunities[0].symbol == "XAUUSD"
    assert report.opportunities[0].rank == 1
    assert report.requires_human_approval is True
    assert report.automatic_execution is False
    assert report.automatic_order_execution is False
    assert len(report.execution_plan) == 4


def test_what_if_is_advisory_and_models_shock() -> None:
    result = predictive_intelligence_service.what_if(
        WhatIfRequest(event="CPI comes in higher than expected", affected_symbols=["XAUUSD", "NAS100"], shock_strength=0.8)
    )
    assert len(result.impacts) == 2
    assert all(item.volatility_impact == 0.8 for item in result.impacts)
    assert result.requires_human_approval is True
    assert result.automatic_execution is False


def test_status_counts_reports() -> None:
    assert predictive_intelligence_service.status().reports == 0
    predictive_intelligence_service.generate(
        ForecastRequest(
            signals=[
                MarketSignal(
                    symbol="BTCUSD",
                    structure_score=0.7,
                    orderflow_score=0.72,
                    liquidity_score=0.65,
                    volatility_score=0.8,
                    news_risk=0.3,
                    confidence=0.74,
                    regime=MarketRegime.volatile,
                )
            ]
        )
    )
    assert predictive_intelligence_service.status().reports == 1
    assert predictive_intelligence_service.status().automatic_order_execution is False
