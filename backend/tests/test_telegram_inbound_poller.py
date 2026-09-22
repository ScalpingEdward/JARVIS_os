"""Long polling for button taps: routing and the update loop, against a
mocked Telegram. The handlers themselves are the modules' own and tested
there; here the question is only whether a tap reaches the right one."""

from __future__ import annotations

import asyncio
import json

import httpx

from app.telegram_inbound import poller as poller_module
from app.telegram_inbound.poller import TelegramPoller, route_for


def _tap(data: str, update_id: int = 1) -> dict:
    return {"update_id": update_id,
            "callback_query": {"id": f"q{update_id}", "data": data,
                               "message": {"chat": {"id": 42}}}}


def test_each_action_letter_reaches_exactly_its_module():
    assert route_for(_tap("x:p:sig")) is poller_module._instagram
    assert route_for(_tap("x:d:sig")) is poller_module._instagram
    assert route_for(_tap("x:a:sig")) is poller_module._setups
    assert route_for(_tap("x:r:sig")) is poller_module._setups
    assert route_for(_tap("x:x:sig")) is poller_module._live_orders
    assert route_for(_tap("x:c:sig")) is poller_module._live_orders


def test_anything_that_is_not_our_tap_goes_nowhere():
    assert route_for({"update_id": 1, "message": {"text": "hallo"}}) is None
    assert route_for(_tap("garbage")) is None
    assert route_for(_tap("x:z:sig")) is None


def _run(coro):
    return asyncio.run(coro)


def test_updates_are_dispatched_and_the_offset_moves_past_them(monkeypatch):
    seen: list[dict] = []
    monkeypatch.setitem(poller_module.ROUTES, "p", lambda update: seen.append(update))
    calls: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content or b"{}")
        calls.append((method, body))
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": [_tap("id:p:sig", 7)]})
        return httpx.Response(200, json={"ok": True, "result": True})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        p = TelegramPoller(bot_token="t", client=client)
        assert await p.poll_once() == 1
        await p.poll_once()
        await client.aclose()

    _run(scenario())

    assert [u["update_id"] for u in seen] == [7, 7]  # mock returns the same update twice
    get_updates = [body for method, body in calls if method == "getUpdates"]
    assert "offset" not in get_updates[0]
    assert get_updates[1]["offset"] == 8
    assert ("answerCallbackQuery", {"callback_query_id": "q7"}) in calls


def test_a_rejected_tap_does_not_stop_the_loop_or_block_the_queue(monkeypatch):
    def boom(update):
        raise RuntimeError("callback from a chat that is not allowed to decide")

    monkeypatch.setitem(poller_module.ROUTES, "p", boom)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": [_tap("id:p:sig", 3)]})
        return httpx.Response(200, json={"ok": True, "result": True})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        p = TelegramPoller(bot_token="t", client=client)
        await p.poll_once()
        await client.aclose()
        return p._offset

    assert _run(scenario()) == 4
