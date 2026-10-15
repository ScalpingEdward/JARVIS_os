"""A file's bytes from Drive, without AURON holding a Drive credential.

n8n holds it. Its "AURON - Drive File Fetch" workflow answers
GET ?id=<drive id> with the file, and refuses anything without the shared
X-Auron-Secret header -- port 5678 is reachable from the LAN, so without the
check anyone there could pull any file from the connected Drive.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

#: Telegram's bot upload limit is 50 MB, and nothing AURON fetches this way
#: needs to be larger: photos are a few MB, big videos are processed locally.
DEFAULT_MAX_BYTES = 48 * 1024 * 1024


class DriveFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class DriveFetchConfig:
    url: str = field(default_factory=lambda: os.getenv(
        "AURON_DRIVE_FETCH_URL", "http://n8n:5678/webhook/auron-drive-file"))
    secret: str | None = field(default_factory=lambda: os.getenv("AURON_DRIVE_FETCH_SECRET"))
    timeout_seconds: float = 180.0


def fetch_drive_file(
    client: httpx.Client,
    media_ref: str,
    config: DriveFetchConfig | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> bytes:
    config = config or DriveFetchConfig()
    if not config.secret:
        raise DriveFetchError("AURON_DRIVE_FETCH_SECRET is not set -- cannot ask n8n for the file")
    chunks: list[bytes] = []
    size = 0
    try:
        with client.stream(
            "GET", config.url, params={"id": media_ref},
            headers={"X-Auron-Secret": config.secret}, timeout=config.timeout_seconds,
        ) as response:
            if response.status_code != 200:
                response.read()
                raise DriveFetchError(
                    f"n8n fetch for {media_ref} answered {response.status_code}: {response.text[:200]}"
                )
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise DriveFetchError(f"{media_ref} is larger than {max_bytes // 2**20} MB")
                chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise DriveFetchError(f"could not reach n8n for {media_ref}: {exc}") from exc
    data = b"".join(chunks)
    # An unknown id comes back as an empty 200 from n8n's Drive node, not as
    # an error -- the emptiness is the only signal there is.
    if not data:
        raise DriveFetchError(f"n8n returned no bytes for {media_ref}")
    return data
