"""Shared authentication for every endpoint where "this was a real
decision by Brano" actually matters -- setup approval/rejection, Instagram
content approval, and anywhere else a direct API call currently proves
nothing about who actually made the call.

The gap this closes, found by an external test pass rather than this
codebase's own reasoning: the Telegram approval paths
(telegram_approvals.handle_update) already verify a real, HMAC-signed
callback token plus a chat_id allowlist -- a caller genuinely has to be
Brano's own Telegram chat to make a decision that way. The raw HTTP
endpoints underneath them (POST /pending/{id}/decision,
POST /candidates/{id}/decision) had no equivalent protection at all: any
caller who could reach the API could approve or reject anything by simply
asserting `decided_by="brano"` in a JSON body, with nothing to verify
that claim. Telegram's own protection was real; the API's was not.

This does not replace Telegram's own token verification -- that stays
exactly as strict as it already is, for that specific path. This adds
the same basic bar to the *other* path into the same consequential
action: a shared secret, checked before the request is allowed to reach
setup_submission.decide() or instagram_content.decide() at all.

Fails closed exactly like every other secret-backed check in this
codebase: if AURON_OPERATOR_TOKEN is not configured, every request this
dependency guards is refused, not silently allowed through.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def _configured_token() -> str | None:
    return os.getenv("AURON_OPERATOR_TOKEN")


def require_operator_token(x_auron_operator_token: str | None = Header(default=None)) -> None:
    """FastAPI dependency -- add via `Depends(require_operator_token)` to
    any endpoint where a caller must prove they are actually Brano (or
    whoever else holds this secret), not just claim to be.
    """
    expected = _configured_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="AURON_OPERATOR_TOKEN is not configured -- this endpoint is refused, "
            "not silently allowed, until a real operator secret is set.",
        )
    if not x_auron_operator_token or not hmac.compare_digest(x_auron_operator_token, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Auron-Operator-Token header")
