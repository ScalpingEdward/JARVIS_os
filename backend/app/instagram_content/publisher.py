from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .models import EditInstruction, MediaItem, PostFormat


class N8nInstagramPublisherError(RuntimeError):
    pass


@dataclass(frozen=True)
class N8nInstagramPublisherConfig:
    """Points at your own n8n container over the shared local Docker network.

    Defaults assume both this API and n8n are attached to the same
    `jarvis_shared` external network (see docker-compose.yml), so `n8n` here
    resolves via Docker's internal DNS -- no tunnel, no public exposure, no
    third-party automation SaaS involved.
    """

    webhook_url: str = os.getenv("N8N_INSTAGRAM_WEBHOOK_URL", "http://n8n:5678/webhook/instagram-post")
    timeout_seconds: float = 15.0


class N8nInstagramPublisher:
    """The only component allowed to trigger a real Instagram post.

    This is called exactly once, and only after a candidate has status
    'approved' (enforced by InstagramContentService, not here -- this class
    has no opinion about approval, it only executes what it is told).

    Sends the full media list, the format decision (single/carousel/reel),
    and the edit plan (target aspect ratio, color-grade preset, trim
    guidance) to n8n. AURON does not perform the actual image/video
    processing or hold Drive/Meta credentials -- n8n's own workflow is
    responsible for executing the edit plan and calling the Graph API.
    """

    def __init__(self, config: N8nInstagramPublisherConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or N8nInstagramPublisherConfig()
        self._client = client

    def publish(
        self,
        media_items: list[MediaItem],
        post_format: PostFormat,
        edit_plan: list[EditInstruction],
        caption: str,
        request_id: str,
    ) -> str:
        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                self.config.webhook_url,
                json={
                    "request_id": request_id,
                    "post_format": post_format.value,
                    "media_items": [item.model_dump(mode="json") for item in media_items],
                    "edit_plan": [instruction.model_dump(mode="json") for instruction in edit_plan],
                    "caption": caption,
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise N8nInstagramPublisherError(
                    f"n8n webhook returned {response.status_code}: {response.text[:500]}"
                )
            data = response.json()
            media_id = data.get("media_id")
            if not media_id:
                raise N8nInstagramPublisherError("n8n webhook response did not include a media_id")
            return str(media_id)
        except httpx.HTTPError as exc:
            raise N8nInstagramPublisherError(f"Could not reach n8n webhook: {exc}") from exc
        finally:
            if should_close:
                client.close()
