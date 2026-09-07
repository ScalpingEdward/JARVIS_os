"""Signed callback tokens for the two inline buttons.

Telegram's callback_data is plain text the tapper's client sends back
verbatim -- it is not something Telegram signs or vouches for. Anyone who can
message the bot can, in principle, send an arbitrary callback_data string.
The chat_id allowlist (see service.py) is the primary defense: only the one
configured chat ever sees these buttons or can trigger a callback at all.
This signature is defense in depth on top of that: it stops a forged or
replayed token from a leaked webhook URL or a bug in the allowlist check.
"""

from __future__ import annotations

import hmac
from hashlib import sha256
from uuid import UUID

APPROVE = "a"
REJECT = "r"
_ACTIONS = {APPROVE, REJECT}
_SIG_LEN = 12


class TokenError(ValueError):
    pass


def _mac(secret: str, approval_request_id: UUID, action: str) -> str:
    msg = f"{approval_request_id}|{action}".encode()
    return hmac.new(secret.encode(), msg, sha256).hexdigest()[:_SIG_LEN]


def make_token(secret: str, approval_request_id: UUID, action: str) -> str:
    if action not in _ACTIONS:
        raise TokenError(f"unknown action {action!r}")
    return f"{approval_request_id}:{action}:{_mac(secret, approval_request_id, action)}"


def verify_token(secret: str, raw: str) -> tuple[UUID, str]:
    """Constant-time verification. Raises TokenError on any mismatch."""
    parts = (raw or "").split(":")
    if len(parts) != 3:
        raise TokenError("malformed callback token")
    id_part, action, sig = parts
    try:
        approval_request_id = UUID(id_part)
    except ValueError as exc:
        raise TokenError("malformed approval id in token") from exc
    if action not in _ACTIONS:
        raise TokenError(f"unknown action {action!r}")
    expected = _mac(secret, approval_request_id, action)
    if not hmac.compare_digest(sig, expected):
        raise TokenError("callback signature mismatch")
    return approval_request_id, action
