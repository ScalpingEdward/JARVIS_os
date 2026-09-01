from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx


class TelegramDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramDeliveryConfig:
    """Bot token and chat id come from the environment, never a request
    payload or a default -- same discipline as every other credential-
    backed component in this build."""

    bot_token: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN"))
    chat_id: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))
    timeout_seconds: float = 10.0


class TelegramDeliveryClient:
    """The one component allowed to actually push a message to Telegram --
    a real, bounded HTTPS call to the Telegram Bot API, not a simulation.
    Fails closed: no bot token or chat id, a transport error, or an API
    error response all raise rather than silently pretending delivery
    succeeded.
    """

    def __init__(self, config: TelegramDeliveryConfig | None = None, client: httpx.Client | None = None) -> None:
        self.config = config or TelegramDeliveryConfig()
        self._client = client

    def send(self, title: str, message: str) -> None:
        if not self.config.bot_token or not self.config.chat_id:
            raise TelegramDeliveryError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set -- AURON cannot deliver to Telegram without them."
            )

        text = f"*{title}*\n{message}" if title else message
        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage",
                json={"chat_id": self.config.chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise TelegramDeliveryError(f"Telegram API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            if not data.get("ok"):
                raise TelegramDeliveryError(f"Telegram API reported failure: {data}")
        except httpx.HTTPError as exc:
            raise TelegramDeliveryError(f"Could not reach the Telegram API: {exc}") from exc
        finally:
            if should_close:
                client.close()
