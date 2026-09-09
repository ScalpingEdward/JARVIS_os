"""Tests for the operator-token gate on consequential decision endpoints --
the fix for the external test pass's first finding: a direct API call
could approve/reject content with nothing verifying the caller was
actually Brano."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.accounts.models import AccountType, StrategyAssignmentCreate, TradingAccountCreate
from app.accounts.service import account_registry_service
from app.main import app
from app.setup_submission.models import SetupSubmissionRequest
from app.setup_submission.service import setup_submission_service
from app.strategies.models import FairValueGap, HTFBias, MarketSnapshot, OrderBlock, OrderBlockType

client = TestClient(app)


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="EURUSD", current_price=1.10000, bid=1.09995, ask=1.10005, spread=0.00010,
        htf_bias=HTFBias.bullish, session="london",
        order_blocks=[OrderBlock(type=OrderBlockType.bullish, high=1.10010, low=1.09990, open=1.09990, close=1.10000)],
        fvgs=[FairValueGap(side="bullish", top=1.10020, bottom=1.09980)],
    )


def _submit_one_setup() -> str:
    account_registry_service.reset()
    setup_submission_service.reset()
    account = account_registry_service.register_account(TradingAccountCreate(
        label="Demo", account_type=AccountType.demo, broker="Test",
        login="1", server="S", currency="USD", initial_balance=100_000.0,
    ))
    account_registry_service.assign_strategy(account.id, StrategyAssignmentCreate(
        strategy_id="scalping_3tp", strategy_name="scalping_3tp", allocation_pct=100.0, enabled=True,
    ))
    report = setup_submission_service.submit(SetupSubmissionRequest(snapshot=_snapshot()))
    return report.submitted_setups[0].approval_request_id


def test_setup_decision_without_a_token_is_refused(monkeypatch):
    monkeypatch.setenv("AURON_OPERATOR_TOKEN", "real-secret")
    approval_id = _submit_one_setup()
    resp = client.post(
        f"/v1/setup-submission/pending/{approval_id}/decision",
        json={"decision": "approved", "decided_by": "brano"},
    )
    assert resp.status_code == 401


def test_setup_decision_with_the_wrong_token_is_refused(monkeypatch):
    monkeypatch.setenv("AURON_OPERATOR_TOKEN", "real-secret")
    approval_id = _submit_one_setup()
    resp = client.post(
        f"/v1/setup-submission/pending/{approval_id}/decision",
        json={"decision": "approved", "decided_by": "brano"},
        headers={"X-Auron-Operator-Token": "guessed-wrong"},
    )
    assert resp.status_code == 401


def test_setup_decision_with_the_correct_token_succeeds(monkeypatch):
    monkeypatch.setenv("AURON_OPERATOR_TOKEN", "real-secret")
    approval_id = _submit_one_setup()
    resp = client.post(
        f"/v1/setup-submission/pending/{approval_id}/decision",
        json={"decision": "approved", "decided_by": "brano"},
        headers={"X-Auron-Operator-Token": "real-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "approved"


def test_setup_decision_fails_closed_when_no_token_is_configured_at_all(monkeypatch):
    """The whole point: an unconfigured secret must refuse everything,
    never silently allow it through."""
    monkeypatch.delenv("AURON_OPERATOR_TOKEN", raising=False)
    approval_id = _submit_one_setup()
    resp = client.post(
        f"/v1/setup-submission/pending/{approval_id}/decision",
        json={"decision": "approved", "decided_by": "brano"},
        headers={"X-Auron-Operator-Token": "anything-at-all"},
    )
    assert resp.status_code == 503


def test_instagram_decision_without_a_token_is_refused(monkeypatch):
    from app.instagram_content.media_pool_service import media_pool_service

    monkeypatch.setenv("AURON_OPERATOR_TOKEN", "real-secret")
    media_pool_service.reset()
    created = client.post("/v1/instagram/candidates", json={
        "media_items": [{"media_ref": "drive://x", "media_type": "image", "aesthetic_score": 0.9}],
        "caption_draft": "Build in silence.",
    })
    candidate_id = created.json()["id"]

    resp = client.post(
        f"/v1/instagram/candidates/{candidate_id}/decision",
        json={"approved": True, "reason": "Looks good"},
    )
    assert resp.status_code == 401


def test_instagram_decision_with_the_correct_token_succeeds(monkeypatch):
    from app.instagram_content.media_pool_service import media_pool_service

    monkeypatch.setenv("AURON_OPERATOR_TOKEN", "real-secret")
    media_pool_service.reset()
    created = client.post("/v1/instagram/candidates", json={
        "media_items": [{"media_ref": "drive://x", "media_type": "image", "aesthetic_score": 0.9}],
        "caption_draft": "Build in silence.",
    })
    candidate_id = created.json()["id"]

    resp = client.post(
        f"/v1/instagram/candidates/{candidate_id}/decision",
        json={"approved": True, "reason": "Looks good"},
        headers={"X-Auron-Operator-Token": "real-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_the_telegram_approval_path_is_unaffected():
    """The fix must not touch the Telegram path's own, separate,
    already-real protection (HMAC callback token + chat allowlist) --
    setup_submission_service.decide() called directly (not through the
    HTTP decision route) has no operator-token dependency at all, exactly
    as before."""
    import inspect
    from app.setup_submission.service import SetupSubmissionService

    sig = inspect.signature(SetupSubmissionService.decide)
    assert "operator_token" not in sig.parameters
    assert "token" not in sig.parameters
