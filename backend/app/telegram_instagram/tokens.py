"""Signed callback tokens for the Instagram approval buttons.

Deliberately its own secret and its own action alphabet, for the same
reason telegram_live_execution has its own: callback_data is plain text the
tapping client sends back verbatim, so a token minted for one module must
be provably unusable against another. The actions here are {p, d, g, 0-9} --
disjoint from telegram_approvals' {a, r} and telegram_live_execution's
{x, c}, so a leaked token from either of those cannot approve a post, and a
leaked one from here cannot touch a trade.
"""

from __future__ import annotations

import hmac
from hashlib import sha256
from uuid import UUID

PUBLISH_OK = "p"
DECLINE = "d"
#: "I have posted this one in the app myself" -- the end of the
#: half-automatic path for photos and carousels, where the music is picked
#: in Instagram and no API can do it.
POSTED = "g"
#: "Take item N out of this post" -- one digit per position, 0-based. A
#: digit rather than a letter keeps it clear of every other module's
#: alphabet, and ten covers Instagram's own carousel maximum.
REMOVE_ACTIONS = frozenset("0123456789")
_ACTIONS = {PUBLISH_OK, DECLINE, POSTED} | REMOVE_ACTIONS


def remove_action(index: int) -> str:
    if not 0 <= index <= 9:
        raise TokenError(f"no remove action for position {index}")
    return str(index)
_SIG_LEN = 12


class TokenError(ValueError):
    pass


def _mac(secret: str, candidate_id: UUID, action: str) -> str:
    msg = f"instagram|{candidate_id}|{action}".encode()
    return hmac.new(secret.encode(), msg, sha256).hexdigest()[:_SIG_LEN]


def make_token(secret: str, candidate_id: UUID, action: str) -> str:
    if action not in _ACTIONS:
        raise TokenError(f"unknown action {action!r}")
    return f"{candidate_id}:{action}:{_mac(secret, candidate_id, action)}"


def verify_token(secret: str, raw: str) -> tuple[UUID, str]:
    """Constant-time verification. Raises TokenError on any mismatch."""
    parts = (raw or "").split(":")
    if len(parts) != 3:
        raise TokenError("malformed callback token")
    id_part, action, sig = parts
    try:
        candidate_id = UUID(id_part)
    except ValueError as exc:
        raise TokenError("malformed candidate id in token") from exc
    if action not in _ACTIONS:
        raise TokenError(f"unknown action {action!r}")
    if not hmac.compare_digest(sig, _mac(secret, candidate_id, action)):
        raise TokenError("callback signature mismatch")
    return candidate_id, action
