"""Tests for telegram_approvals.tokens."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.telegram_approvals.tokens import (
    APPROVE,
    REJECT,
    TokenError,
    make_token,
    verify_token,
)

SECRET = "test-secret-not-real"


def test_round_trip_approve():
    approval_id = uuid4()
    token = make_token(SECRET, approval_id, APPROVE)
    got_id, action = verify_token(SECRET, token)
    assert got_id == approval_id
    assert action == APPROVE


def test_round_trip_reject():
    approval_id = uuid4()
    token = make_token(SECRET, approval_id, REJECT)
    assert verify_token(SECRET, token) == (approval_id, REJECT)


def test_make_token_rejects_unknown_action():
    with pytest.raises(TokenError, match="unknown action"):
        make_token(SECRET, uuid4(), "x")


def test_wrong_secret_is_rejected():
    token = make_token(SECRET, uuid4(), APPROVE)
    with pytest.raises(TokenError, match="signature mismatch"):
        verify_token("a-different-secret", token)


def test_tampered_action_is_rejected():
    """Flipping the action byte without re-signing must not verify --
    otherwise a captured Reject token could be replayed as Approve."""
    approval_id = uuid4()
    token = make_token(SECRET, approval_id, REJECT)
    forged = token.replace(f":{REJECT}:", f":{APPROVE}:")
    with pytest.raises(TokenError, match="signature mismatch"):
        verify_token(SECRET, forged)


def test_tampered_id_is_rejected():
    """Swapping in a different approval_request_id without re-signing must
    not verify -- otherwise one signed token could be pointed at any setup."""
    token = make_token(SECRET, uuid4(), APPROVE)
    _, action, sig = token.split(":")
    forged = f"{uuid4()}:{action}:{sig}"
    with pytest.raises(TokenError, match="signature mismatch"):
        verify_token(SECRET, forged)


@pytest.mark.parametrize("raw", ["", "not-a-token", "a:b", "a:b:c:d", ":::"])
def test_malformed_tokens_rejected(raw):
    with pytest.raises(TokenError):
        verify_token(SECRET, raw)


def test_non_uuid_id_part_rejected():
    with pytest.raises(TokenError, match="malformed approval id"):
        verify_token(SECRET, "not-a-uuid:a:deadbeef")


def test_unknown_action_in_token_rejected():
    approval_id = uuid4()
    with pytest.raises(TokenError, match="unknown action"):
        verify_token(SECRET, f"{approval_id}:x:deadbeef")
