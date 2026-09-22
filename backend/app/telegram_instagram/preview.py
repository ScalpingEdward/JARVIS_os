"""The post itself, on the phone, before the buttons.

The first approval card said so honestly: "No preview image -- AURON holds
no Drive credentials." That made it a card nobody could decide on. The
bytes come from two places, and neither needs AURON to hold a credential:

* a processed video is already on this disk -- cut, graded, 1080x1920 --
  and is exactly what would be posted, so that is what is shown;
* anything else lives only in Drive, and n8n (which does hold the Drive
  credential) hands it over through its secret-protected fetch webhook.

Photos are shrunk before sending: the phone needs to judge the frame, not
receive a 4 MB original per slide. Every item is numbered in the order it
would be posted, so the "2 raus" button below refers to something visible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageOps

from app.instagram_content.drive_fetch import DriveFetchConfig, DriveFetchError, fetch_drive_file
from app.instagram_content.media_pool_service import media_pool_service
from app.instagram_content.media_processing import output_dir
from app.instagram_content.models import ContentCandidate, MediaItem, MediaType
from app.notification_hub.telegram_delivery import TelegramDeliveryConfig

#: Telegram's upload limit for a bot is 50 MB; stay clear of it.
MAX_UPLOAD_BYTES = 48 * 1024 * 1024
_PREVIEW_EDGE_PX = 1600


class PreviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreviewMedia:
    kind: str  # "photo" or "video"
    filename: str
    data: bytes


class PostPreviewSender:
    def __init__(
        self,
        config: DriveFetchConfig | None = None,
        telegram: TelegramDeliveryConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or DriveFetchConfig()
        self.telegram = telegram or TelegramDeliveryConfig()
        self._client = client

    # ------------------------------------------------------------ fetching
    def _processed_file(self, media_ref: str) -> Path | None:
        for pool_item in media_pool_service.list_all():
            if pool_item.media_ref == media_ref and pool_item.processed_file:
                path = output_dir() / pool_item.processed_file
                return path if path.is_file() else None
        return None

    def _fetch_from_drive(self, client: httpx.Client, media_ref: str) -> bytes:
        try:
            return fetch_drive_file(client, media_ref, self.config, max_bytes=MAX_UPLOAD_BYTES)
        except DriveFetchError as exc:
            raise PreviewError(str(exc)) from exc

    @staticmethod
    def _shrink_photo(data: bytes) -> bytes:
        try:
            image = ImageOps.exif_transpose(Image.open(BytesIO(data)))
            image.thumbnail((_PREVIEW_EDGE_PX, _PREVIEW_EDGE_PX))
            buffer = BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=85)
            return buffer.getvalue()
        except Exception as exc:  # noqa: BLE001 -- anything Pillow cannot read is not a photo we can show
            raise PreviewError(f"could not read the photo: {exc}") from exc

    def media_for(self, client: httpx.Client, item: MediaItem, position: int) -> PreviewMedia:
        # The processed file, graded in Brano's look, is what would be
        # posted -- so it is what gets shown whenever it exists.
        processed = self._processed_file(item.media_ref)
        if item.media_type == MediaType.video:
            if processed is not None and processed.stat().st_size <= MAX_UPLOAD_BYTES:
                return PreviewMedia("video", f"{position}.mp4", processed.read_bytes())
            return PreviewMedia("video", f"{position}.mp4", self._fetch_from_drive(client, item.media_ref))
        raw = processed.read_bytes() if processed is not None else self._fetch_from_drive(client, item.media_ref)
        return PreviewMedia("photo", f"{position}.jpg", self._shrink_photo(raw))

    # ------------------------------------------------------------- sending
    def _call(self, client: httpx.Client, method: str, data: dict, files: dict) -> dict:
        response = client.post(
            f"https://api.telegram.org/bot{self.telegram.bot_token}/{method}",
            data=data, files=files, timeout=self.config.timeout_seconds,
        )
        body = response.json() if response.content else {}
        if response.status_code >= 400 or not body.get("ok"):
            raise PreviewError(f"Telegram {method} failed: {response.status_code} {str(body)[:300]}")
        return body

    def send(self, candidate: ContentCandidate) -> int:
        """Send every item, numbered, in posting order. Returns how many
        were sent. Raises PreviewError if the post cannot be shown -- the
        caller decides what the card says about that."""
        if not self.telegram.bot_token or not self.telegram.chat_id:
            raise PreviewError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set")
        items = candidate.media_items[:10]
        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            media = [self.media_for(client, item, i + 1) for i, item in enumerate(items)]
            chat = {"chat_id": self.telegram.chat_id}
            if len(media) == 1:
                only = media[0]
                method = "sendVideo" if only.kind == "video" else "sendPhoto"
                self._call(client, method, {**chat, "caption": "1"},
                           {only.kind: (only.filename, only.data)})
            else:
                group = [
                    {"type": m.kind, "media": f"attach://f{i}", "caption": str(i + 1),
                     **({"supports_streaming": True} if m.kind == "video" else {})}
                    for i, m in enumerate(media)
                ]
                files = {f"f{i}": (m.filename, m.data) for i, m in enumerate(media)}
                self._call(client, "sendMediaGroup", {**chat, "media": json.dumps(group)}, files)
            return len(media)
        except httpx.HTTPError as exc:
            raise PreviewError(f"network error while sending the preview: {exc}") from exc
        finally:
            if should_close:
                client.close()
