"""One-off: log in to Telegram, find the channel, show how the last messages parse.

Read-only -- sends nothing, trades nothing. The first run asks for phone
number, login code and (if set) the 2FA password, then keeps the login in
signal_copier/copier.session.

    python -m signal_copier.telegram_check
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

from signal_copier.parser import parse

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")


def _plain(title: str) -> str:
    return re.sub(r"[^a-z0-9()+]+", " ", title.lower()).strip()


async def main() -> None:
    client = TelegramClient(str(HERE / "copier"), int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"])
    await client.start()
    wanted = _plain(os.environ["TELEGRAM_CHANNEL"])
    matches = [d async for d in client.iter_dialogs() if wanted in _plain(d.name or "")]
    if len(matches) != 1:
        print(f"{len(matches)} chats match {wanted!r}:", [d.name for d in matches])
        return
    chat = matches[0]
    print(f"Found: {chat.name}  (id {chat.id})\n")
    async for m in client.iter_messages(chat, limit=30):
        text = (m.message or "").replace("\n", " | ")
        reply = f" reply_to={m.reply_to.reply_to_msg_id}" if m.reply_to else ""
        print(f"#{m.id}{reply}  {m.date:%m-%d %H:%M}  {text[:90]}")
        result = parse(m.message or "")
        if result is not None:
            print(f"      -> {result}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
