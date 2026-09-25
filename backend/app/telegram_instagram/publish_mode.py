"""Whether a tap on "Freigeben" posts, or only prepares.

Off by default, and deliberately an environment switch rather than a
constant: the first real post to Brano's own account is a one-way step, so
it is turned on once the path has been walked end to end, not because a
deploy happened to include this file.
"""

from __future__ import annotations

import os


def auto_publish_enabled() -> bool:
    return os.getenv("AURON_AUTO_PUBLISH_ON_APPROVAL", "false").lower() in ("1", "true", "yes")
