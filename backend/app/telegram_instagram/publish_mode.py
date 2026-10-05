"""Whether a tap on "Freigeben" posts, or only prepares.

Posting by API and adding the music afterwards was the premise of the
automatic path, and it held for photos: Brano checked in September that
Instagram's edit screen lets him put audio on a post that is already up.

On 2026-10-05 he checked the same thing for a Reel that AURON had just
posted, and it does not. A Reel published through the Graph API offers no
music in its edit screen at all. The music can only be chosen while
posting -- which, for a Reel, means posting from the app by hand, or
handing the Graph API an `audio_id`. That second way needs the
"Instagram API with Facebook Login" token type; this account runs on
Instagram Login, so it does not exist yet.

Music is mandatory atmosphere here, not a nice-to-have. So nothing
publishes itself until AURON can actually choose the audio: the files and
the caption go to the phone instead, and Brano posts with music. The
switch below stays, because that is the day it flips back -- not a deploy.
"""

from __future__ import annotations

import os


def auto_publish_enabled() -> bool:
    return os.getenv("AURON_AUTO_PUBLISH_ON_APPROVAL", "false").lower() in ("1", "true", "yes")


def can_choose_audio() -> bool:
    """Whether AURON can attach music itself -- an `audio_id` on a Reel,
    which the Graph API only accepts from a Facebook-Login token. Until
    then, publishing automatically means publishing silently."""
    return os.getenv("AURON_INSTAGRAM_LOGIN_TYPE", "instagram").lower() == "facebook"


def auto_publish_refusal(post_format: str) -> str | None:
    """Why this post must not be published automatically, or None when it
    may be. Worded for the log and for the message to Brano."""
    if not auto_publish_enabled():
        return "automatic publishing is switched off"
    if can_choose_audio():
        return None
    if post_format == "reel":
        return (
            "a Reel posted through the API cannot have music added afterwards -- "
            "its edit screen offers none"
        )
    return "no API can attach music to a photo or a carousel"
