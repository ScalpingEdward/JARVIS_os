from __future__ import annotations

import json

import httpx
import pytest

from app.account_intake.credential_guard import CREDENTIAL_REFUSAL_MESSAGE, contains_credential_language
from app.account_intake.models import AccountIntakeRefusal, AccountProposal
from app.account_intake.service import AccountIntakeConfig, AccountIntakeError, AccountIntakeService
from app.accounts.models import AccountType, TradingAccountCreate
from app.accounts.service import AccountRegistryService


# -- credential_guard: the check that must run before anything else --------


@pytest.mark.parametrize("text", [
    "Hey Auron, here's a new login and password for another trading account",
    "hier hast du neue login und PASSWORT fur ein weiteren trading account",
    "mein Kennwort ist Xk9mQ2vLp",
    "credentials: user=trader1 pass=Xk9$mQ2vLp8",
    "pw: Xk9mQ2vLp8Rt",
])
def test_credential_language_is_detected(text):
    assert contains_credential_language(text) is True


@pytest.mark.parametrize("text", [
    "Neues Konto: Broker PUPrime, Login 20481337, Server PUPrime-Demo, Strategie VWAP",
    "Add account: broker ICMarkets, login 55512345, server ICMarketsSC-Demo02, strategy vwap_pullback",
    "mein neues Trading Konto: IC Markets, Kontonummer 87654321, Server Live-01, VWAP bitte",
    "trade XAUUSD with vwap_pullback on my demo account",
])
def test_clean_account_instructions_are_not_flagged(text):
    assert contains_credential_language(text) is False


def test_refusal_message_never_echoes_the_original_text():
    assert "password" not in CREDENTIAL_REFUSAL_MESSAGE.lower() or "never" in CREDENTIAL_REFUSAL_MESSAGE.lower()
    assert "MT5 terminal" in CREDENTIAL_REFUSAL_MESSAGE


# -- AccountIntakeService.propose(): the credential check runs first -------


def _service_with_fake_extraction(json_payload: dict, *, accounts=None) -> AccountIntakeService:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": json.dumps(json_payload)}],
        })

    return AccountIntakeService(
        config=AccountIntakeConfig(api_key="test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        accounts=accounts,
    )


def test_propose_refuses_a_message_with_credential_language_before_any_extraction():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{}"}]})

    svc = AccountIntakeService(
        config=AccountIntakeConfig(api_key="test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = svc.propose("here's the login and password: hunter2xyz", "brano")
    assert isinstance(result, AccountIntakeRefusal)
    assert calls == [], "the Anthropic API must never be called when credential language is present"


def test_propose_extracts_clean_fields_into_a_proposal():
    svc = _service_with_fake_extraction({
        "label": "PUPrime Demo", "broker": "PUPrime", "login": "20481337",
        "server": "PUPrime-Demo", "account_type": "demo", "currency": "USD",
        "initial_balance": None, "strategy_id": "vwap_pullback",
    })
    result = svc.propose("new demo account, broker PUPrime, login 20481337, server PUPrime-Demo, vwap", "brano")
    assert isinstance(result, AccountProposal)
    assert result.fields.broker == "PUPrime"
    assert result.fields.login == "20481337"
    assert result.fields.strategy_id == "vwap_pullback"
    assert result.missing_fields == []
    assert result.confirmed is False


def test_propose_flags_missing_required_fields_without_refusing():
    svc = _service_with_fake_extraction({
        "label": "New Account", "broker": "", "login": "12345",
        "server": "", "account_type": "demo",
    })
    result = svc.propose("add an account, login 12345", "brano")
    assert isinstance(result, AccountProposal)
    assert "broker" in result.missing_fields
    assert "server" in result.missing_fields


def test_propose_fails_closed_without_an_api_key():
    svc = AccountIntakeService(config=AccountIntakeConfig(api_key=None))
    with pytest.raises(AccountIntakeError, match="ANTHROPIC_API_KEY"):
        svc.propose("add a new demo account, broker X, login 1, server Y", "brano")


# -- confirm(): the only place a real account gets created ------------------


def test_confirm_registers_a_real_account_and_assigns_the_strategy(tmp_path):
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    svc = _service_with_fake_extraction({
        "label": "PUPrime Demo", "broker": "PUPrime", "login": "20481337",
        "server": "PUPrime-Demo", "account_type": "demo", "currency": "USD",
        "initial_balance": 50000, "strategy_id": "vwap_pullback",
    }, accounts=accounts)
    proposal = svc.propose("new demo account for vwap", "brano")

    record = svc.confirm(proposal.id, "brano")
    assert record.broker == "PUPrime"
    assert record.login == "20481337"
    assert record.account_type == AccountType.demo
    assert record.initial_balance == 50000

    assignments = accounts.list_assignments(record.id)
    assert any(a.strategy_id == "vwap_pullback" for a in assignments)


def test_confirm_refuses_a_second_confirmation_of_the_same_proposal(tmp_path):
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    svc = _service_with_fake_extraction({
        "label": "X", "broker": "PUPrime", "login": "1", "server": "S", "account_type": "demo",
    }, accounts=accounts)
    proposal = svc.propose("new account", "brano")
    svc.confirm(proposal.id, "brano")
    with pytest.raises(AccountIntakeError, match="already confirmed"):
        svc.confirm(proposal.id, "brano")


def test_confirm_refuses_when_required_fields_are_missing(tmp_path):
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    svc = _service_with_fake_extraction({
        "label": "X", "broker": "", "login": "1", "server": "S", "account_type": "demo",
    }, accounts=accounts)
    proposal = svc.propose("new account", "brano")
    with pytest.raises(AccountIntakeError, match="missing required fields"):
        svc.confirm(proposal.id, "brano")


def test_confirm_refuses_a_different_requester_than_who_proposed(tmp_path):
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    svc = _service_with_fake_extraction({
        "label": "X", "broker": "PUPrime", "login": "1", "server": "S", "account_type": "demo",
    }, accounts=accounts)
    proposal = svc.propose("new account", "brano")
    with pytest.raises(AccountIntakeError, match="Only the person who requested"):
        svc.confirm(proposal.id, "someone-else")


def test_confirm_refuses_an_unknown_proposal_id():
    svc = AccountIntakeService(config=AccountIntakeConfig(api_key="test-key"))
    import uuid
    with pytest.raises(AccountIntakeError, match="No such proposal"):
        svc.confirm(uuid.uuid4(), "brano")


def test_an_invalid_account_type_is_refused_not_silently_defaulted(tmp_path):
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    svc = _service_with_fake_extraction({
        "label": "X", "broker": "PUPrime", "login": "1", "server": "S", "account_type": "swiss-bank",
    }, accounts=accounts)
    proposal = svc.propose("new account", "brano")
    with pytest.raises(AccountIntakeError, match="not a real account type"):
        svc.confirm(proposal.id, "brano")


def test_an_unknown_strategy_id_is_silently_skipped_not_a_hard_failure(tmp_path):
    """A misheard/misspelled strategy name should not block the account
    itself from being created -- Brano can assign the right strategy
    separately afterward."""
    accounts = AccountRegistryService(db_path=tmp_path / "accounts.db")
    svc = _service_with_fake_extraction({
        "label": "X", "broker": "PUPrime", "login": "1", "server": "S",
        "account_type": "demo", "strategy_id": "not-a-real-strategy",
    }, accounts=accounts)
    proposal = svc.propose("new account", "brano")
    record = svc.confirm(proposal.id, "brano")  # must not raise
    assert accounts.list_assignments(record.id) == []


# -- API level ----------------------------------------------------------------


def test_propose_endpoint_refuses_credential_language_with_200_not_an_error():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/v1/account-intake/propose", json={
        "text": "here's the login and password: hunter2xyz",
        "requester_id": "brano",
    })
    assert resp.status_code == 200
    assert "reason" in resp.json()


def test_get_unknown_proposal_returns_404():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    import uuid
    resp = client.get(f"/v1/account-intake/proposals/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_status_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/v1/account-intake/status")
    assert resp.status_code == 200
    assert "api_key_configured" in resp.json()
