"""Signed callback tokens for the final "place the real order" buttons.

Deliberately a separate token namespace from telegram_approvals.tokens,
not a shared one, even though the crypto pattern is identical: this
module's tap ends in a real broker order, that module's tap only ever
records a decision. Two distinct secrets means a leak or misconfiguration
of one never lets a tap forge the other -- the setup-approval secret
alone can never mint something this module's verify_token() accepts,
because the action characters live in disjoint sets and the MAC covers
the action string too.
"""

from __future__ import annotations

import hmac
from hashlib import sha256
from uuid import UUID

EXECUTE = "x"
CANCEL = "c"
_ACTIONS = {EXECUTE, CANCEL}
_SIG_LEN = 12


class TokenError(ValueError):
    pass


def _mac(secret: str, record_id: UUID, action: str) -> str:
    msg = f"{record_id}|{action}".encode()
    return hmac.new(secret.encode(), msg, sha256).hexdigest()[:_SIG_LEN]


def make_token(secret: str, record_id: UUID, action: str) -> str:
    if action not in _ACTIONS:
        raise TokenError(f"unknown action {action!r}")
    return f"{record_id}:{action}:{_mac(secret, record_id, action)}"


def verify_token(secret: str, raw: str) -> tuple[UUID, str]:
    """Constant-time verification. Raises TokenError on any mismatch."""
    parts = (raw or "").split(":")
    if len(parts) != 3:
        raise TokenError("malformed callback token")
    id_part, action, sig = parts
    try:
        record_id = UUID(id_part)
    except ValueError as exc:
        raise TokenError("malformed record id in token") from exc
    if action not in _ACTIONS:
        raise TokenError(f"unknown action {action!r}")
    expected = _mac(secret, record_id, action)
    if not hmac.compare_digest(sig, expected):
        raise TokenError("callback signature mismatch")
    return record_id, action
