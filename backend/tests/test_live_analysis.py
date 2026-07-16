from app.live_analysis.models import Bias, Decision, LiveAnalysisRequest, MarketContext, PersonalStats
from app.live_analysis.service import live_analysis_service


def setup_function() -> None:
    live_analysis_service.reset()


def test_strong_aligned_setup_is_valid_and_advisory_only() -> None:
    result = live_analysis_service.evaluate(
        LiveAnalysisRequest(
            context=MarketContext(
                symbol="XAUUSD", timeframe="M15", higher_timeframe_bias=Bias.bullish,
                liquidity_sweep=True, structure_shift=True, fair_value_gap=True,
                order_block=True, premium_discount_aligned=True, risk_reward=4.0,
                spread_points=18, daily_drawdown_percent=0.8, open_trades=1,
            )
        )
    )
    assert result.decision == Decision.valid
    assert result.score >= 80
    assert result.advisory_only is True
    assert result.human_approval_required is True
    assert result.automatic_order_execution is False


def test_risk_gates_reject_setup() -> None:
    result = live_analysis_service.evaluate(
        LiveAnalysisRequest(
            context=MarketContext(
                symbol="EURUSD", timeframe="M5", risk_reward=1.2,
                spread_points=80, news_minutes=5, daily_drawdown_percent=4,
                open_trades=3,
            )
        )
    )
    assert result.decision == Decision.rejected
    assert "spread above limit" in result.blockers
    assert "high-impact news window" in result.blockers
    assert result.confidence_percent <= 49


def test_personal_history_adjusts_score_only_with_enough_samples() -> None:
    payload = LiveAnalysisRequest(
        context=MarketContext(
            symbol="GBPUSD", timeframe="M15", higher_timeframe_bias=Bias.bullish,
            liquidity_sweep=True, structure_shift=True, fair_value_gap=True,
            risk_reward=3,
        ),
        personal_stats=PersonalStats(sample_size=40, win_rate=62, average_rr=2.8, matching_setup_win_rate=80),
    )
    result = live_analysis_service.evaluate(payload)
    assert result.personal_adjustment > 0


def test_status_counts_decisions() -> None:
    live_analysis_service.evaluate(LiveAnalysisRequest(context=MarketContext(symbol="BTCUSD", timeframe="H1")))
    status = live_analysis_service.status()
    assert status.analyses == 1
    assert status.automatic_order_execution is False
