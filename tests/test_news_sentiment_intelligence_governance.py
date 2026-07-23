import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_64_news_sentiment_intelligence_governance.models import (
    NewsSentimentAction,
    NewsSentimentCreate,
    NewsSentimentPolicy,
    NewsSentimentState,
    NewsSignal,
)
from backend.app.phoenix.v21_64_news_sentiment_intelligence_governance.service import (
    GovernanceError,
    NewsSentimentGovernanceService,
)


def signal(**overrides):
    data = {
        "signal_id": "signal-1", "source_type": "wire", "entity": "XAUUSD", "topic": "rates",
        "sentiment": 20, "relevance": 90, "credibility": 90, "freshness": 95,
        "novelty": 75, "market_impact": 45, "manipulation_risk": 5,
    }
    data.update(overrides)
    return NewsSignal(**data)


def payload(**overrides):
    data = {
        "workspace_id": "workspace-a", "source_key": "news-source-1", "subject": "gold-macro",
        "signals": [signal()], "evidence_refs": ["wire:item-1"],
        "policy": NewsSentimentPolicy(stable_cycles_required=2),
    }
    data.update(overrides)
    return NewsSentimentCreate(**data)


def advance(service, record_id):
    actions = [
        ("prepare-evidence", {}), ("score", {}), ("prepare-policy", {}),
        ("request-review", {}), ("approve", {"approval_token": "approval-1"}),
        ("activate", {"operation_receipt": "activate-1"}),
    ]
    for action, extra in actions:
        service.act(record_id, "workspace-a", NewsSentimentAction(action=action, actor="operator", **extra))


def test_full_news_sentiment_lifecycle():
    service = NewsSentimentGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    for _ in range(2):
        service.act(record.record_id, "workspace-a", NewsSentimentAction(action="observe", actor="monitor", signals=[signal(sentiment=22)]))
    service.act(record.record_id, "workspace-a", NewsSentimentAction(action="confirm-stable", actor="operator", operation_receipt="stable-1"))
    assert record.state == NewsSentimentState.STABLE
    assert record.quality_score > 0
    assert service.audit


def test_narrative_shift_and_escalation():
    service = NewsSentimentGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    service.act(record.record_id, "workspace-a", NewsSentimentAction(action="observe", actor="monitor", signals=[signal(sentiment=-70)]))
    assert record.state == NewsSentimentState.NARRATIVE_SHIFT
    service.act(record.record_id, "workspace-a", NewsSentimentAction(action="observe", actor="monitor", signals=[signal(signal_id="signal-2", market_impact=95, manipulation_risk=80)]))
    assert record.state == NewsSentimentState.ESCALATED


def test_replay_risk_brain_duplicates_isolation_and_validation():
    service = NewsSentimentGovernanceService()
    first = service.create(payload())
    advance(service, first.record_id)
    second = service.create(payload(source_key="news-source-2"))
    for action in ["prepare-evidence", "score", "prepare-policy", "request-review"]:
        service.act(second.record_id, "workspace-a", NewsSentimentAction(action=action, actor="operator"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "workspace-a", NewsSentimentAction(action="approve", actor="operator", approval_token="approval-1"))
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(first.record_id, "workspace-b")
    blocked = service.create(payload(source_key="news-source-3", risk_brain_blocked=True))
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(blocked.record_id, "workspace-a", NewsSentimentAction(action="prepare-evidence", actor="operator"))
    with pytest.raises(ValidationError):
        NewsSentimentCreate(workspace_id="w", source_key="s", subject="x", signals=[signal(), signal()])
