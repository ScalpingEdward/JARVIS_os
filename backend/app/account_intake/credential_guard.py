"""The one check that must run before anything else in this package: does
this message look like it contains a credential? If so, refuse
immediately, and never let the raw text reach an AI model, a log line, or
storage of any kind.

This is deliberately a blunt, over-inclusive keyword check, not an
attempt to cleverly locate and strip out just the password while keeping
the rest. A false positive (a message wrongly flagged) costs the person
one extra reply asking them to resend without whatever tripped it -- a
false negative (a real password that slips through) could put it in an AI
provider's request logs, this module's own audit trail, or a chat
history that is not end-to-end encrypted. That asymmetry is why this
errs hard toward refusing.
"""

from __future__ import annotations

import re

#: Deliberately broad and multilingual (German is Brano's own primary
#: language for this system) -- err toward over-refusing, never under.
_CREDENTIAL_TERMS = (
    "password", "passwort", "kennwort", "pwd", "pw:", "pw ",
    "secret", "geheim", "zugangsdaten", "credentials", "login-daten",
)

#: A bare, unlabeled long alphanumeric token is also worth catching --
#: someone might paste a password without ever using the word "password"
#: at all. This is intentionally permissive (it will also flag things
#: that are not passwords, like a long broker server hostname) --
#: over-refusing is the correct failure mode here, not under-refusing.
_LONG_TOKEN_PATTERN = re.compile(r"\b(?=\w*\d)(?=\w*[A-Za-z])[A-Za-z0-9!@#$%^&*_\-]{10,}\b")


def contains_credential_language(text: str) -> bool:
    """True if this text should never be forwarded anywhere as-is."""
    lowered = text.lower()
    if any(term in lowered for term in _CREDENTIAL_TERMS):
        return True
    return bool(_LONG_TOKEN_PATTERN.search(text))


#: The one message ever shown for a refusal -- never echoes any part of
#: the original text back, on purpose.
CREDENTIAL_REFUSAL_MESSAGE = (
    "I don't process passwords or anything that looks like one through chat, ever -- "
    "not even to discard it afterward. Enter the account's password directly on the "
    "MT5 terminal itself; that's a separate, local step this backend never sees. "
    "Just tell me the broker, the account/login number, the server, and which "
    "strategy to run, and I'll take it from there."
)
