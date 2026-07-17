import pytest
from pydantic import ValidationError

from app.strategy_coach.models import PlaybookCreate
from app.strategy_coach.service import StrategyCoachService


def payload(**overrides) -> PlaybookCreate:
    values = {
        "name": "XAUUSD A-grade playbook",
        "symbol": "xauusd",
        "timeframe": "m15",
        "win_rate_pct": 60,
        "average_r": 1.5,
        "profit_factor": 1.8,
        "best_setups": ["FVG", "liquidity sweep", "FVG"],
        "recurring_mistakes": [],
    }
    values.update(overrides)
    return PlaybookCreate(**values)


def test_create_playbook_normalizes_and_scores() -> None:
    service = StrategyCoachService()
    playbook = service.create(payload())
    assert playbook.symbol == "XAUUSD"
    assert playbook.timeframe == "M15"
    assert playbook.approved_setups == ["fvg", "liquidity sweep"]
    assert playbook.readiness_score >= 80
    assert playbook.live_use_recommended is True


def test_recurring_mistakes_reduce_score_and_create_rules() -> None:
    service = StrategyCoachService()
    playbook = service.create(payload(recurring_mistakes=["late entry", "revenge trade"]))
    assert playbook.live_use_recommended is False
    assert "late entry" in playbook.blocked_mistakes
    assert any("late entry" in item for item in playbook.pre_trade_checklist)
    assert any(action.category == "discipline" for action in playbook.improvement_actions)


def test_negative_expectancy_blocks_live_recommendation() -> None:
    service = StrategyCoachService()
    playbook = service.create(payload(win_rate_pct=35, average_r=-0.2, profit_factor=0.8))
    assert playbook.live_use_recommended is False
    assert any(action.category == "expectancy" for action in playbook.improvement_actions)
    assert any(action.category == "profit-factor" for action in playbook.improvement_actions)


def test_playbooks_can_be_listed_and_retrieved() -> None:
    service = StrategyCoachService()
    playbook = service.create(payload())
    assert service.get(playbook.id) == playbook
    assert service.list_all() == [playbook]


def test_automatic_execution_and_missing_approval_are_rejected() -> None:
    with pytest.raises(ValidationError):
        payload(automatic_execution=True)
    with pytest.raises(ValidationError):
        payload(human_approved=False)
