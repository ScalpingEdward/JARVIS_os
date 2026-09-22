"""Button taps from Telegram, fetched rather than received.

Every approval module here (setups, live orders, Instagram posts) has a
/webhook route, and none of them ever received anything: a webhook needs
Telegram to reach this laptop from the internet, and nothing is exposed.
Every tap Brano made landed in Telegram's queue and stayed there.

Long polling turns the direction around. This loop asks Telegram for new
updates (getUpdates), so no port is opened and no public URL exists that
could be probed. It is the only consumer of the bot's updates -- Telegram
refuses getUpdates while a webhook is set, and one bot has one queue.

Routing is by the action letter in callback_data, not by trying each
module in turn. The three token alphabets are disjoint by design
(instagram {p, d, 0-9}, setups {a, r}, live orders {x, c}), so the letter names
exactly one module. Trying all three would work too, but every miss would
be written to the other modules' audit logs as a rejected token -- a tap on
a post would show up as an attack on the trading approvals.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable

import httpx

log = logging.getLogger(__name__)

_LONG_POLL_SECONDS = 25
_BACKOFF_SECONDS = 5.0


def _instagram(update: dict) -> object:
    from app.telegram_instagram.service import telegram_instagram_service

    return telegram_instagram_service.handle_update(update)


def _setups(update: dict) -> object:
    from app.telegram_approvals.service import telegram_approval_service

    return telegram_approval_service.handle_update(update)


def _live_orders(update: dict) -> object:
    from app.telegram_live_execution.service import telegram_live_execution_service

    return telegram_live_execution_service.handle_update(update)


ROUTES: dict[str, Callable[[dict], object]] = {
    "p": _instagram,
    "d": _instagram,
    "a": _setups,
    "r": _setups,
    "x": _live_orders,
    "c": _live_orders,
    # "take item N out of the post" on an Instagram card
    **{digit: _instagram for digit in "0123456789"},
}


def route_for(update: dict) -> Callable[[dict], object] | None:
    """The handler a tap belongs to, or None for anything that is not one
    of our button taps (plain messages, foreign or malformed data)."""
    data = ((update.get("callback_query") or {}).get("data")) or ""
    parts = data.split(":")
    if len(parts) != 3:
        return None
    return ROUTES.get(parts[1])


class TelegramPoller:
    def __init__(self, bot_token: str | None = None, client: httpx.AsyncClient | None = None) -> None:
        self._bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self._client = client
        self._task: asyncio.Task | None = None
        self._offset: int | None = None

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._bot_token}/{method}"

    async def dispatch(self, update: dict) -> None:
        """Hand one update to its module. A module rejecting the tap (wrong
        chat, bad signature) is logged and swallowed: one bad update must not
        stop the loop, and must not be re-fetched forever either -- the
        offset moves past it regardless."""
        handler = route_for(update)
        query = update.get("callback_query") or {}
        if handler is not None:
            try:
                await asyncio.to_thread(handler, update)
            except Exception as exc:  # noqa: BLE001 -- the module has already audited it
                log.warning("telegram tap %s rejected: %s", update.get("update_id"), exc)
        if query.get("id"):
            # Stops the spinner on the button. Without it the phone shows the
            # tap as pending for a while, even though it was handled.
            try:
                await self._client.post(self._url("answerCallbackQuery"),
                                        json={"callback_query_id": query["id"]}, timeout=10)
            except httpx.HTTPError:
                pass

    async def poll_once(self) -> int:
        params: dict = {"timeout": _LONG_POLL_SECONDS, "allowed_updates": ["callback_query"]}
        if self._offset is not None:
            params["offset"] = self._offset
        response = await self._client.post(self._url("getUpdates"), json=params,
                                           timeout=_LONG_POLL_SECONDS + 10)
        response.raise_for_status()
        updates = response.json().get("result", [])
        for update in updates:
            await self.dispatch(update)
            self._offset = update["update_id"] + 1
        return len(updates)

    async def _run(self) -> None:
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- network blips must not end the loop
                log.warning("telegram polling failed, retrying in %.0fs: %s", _BACKOFF_SECONDS, exc)
                await asyncio.sleep(_BACKOFF_SECONDS)

    def start(self) -> None:
        if not self._bot_token:
            log.warning("TELEGRAM_POLLING_ENABLED is set but TELEGRAM_BOT_TOKEN is not -- not polling")
            return
        if self._client is None:
            self._client = httpx.AsyncClient()
        self._task = asyncio.create_task(self._run())
        log.info("telegram polling started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            await self._client.aclose()
            self._client = None


telegram_poller = TelegramPoller()
