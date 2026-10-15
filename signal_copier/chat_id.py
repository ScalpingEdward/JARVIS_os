"""Prints the chat id of whoever last wrote to your bot -- that is TELEGRAM_NOTIFY_CHAT_ID.

    python -m signal_copier.chat_id
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is empty in .env -- create a bot with @BotFather first.")
        return
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15) as r:
        updates = json.load(r)["result"]
    chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
             for u in updates if "message" in u}
    if not chats:
        print("Nobody wrote to the bot yet. Open your bot in Telegram, send it 'hi', run this again.")
        return
    for chat_id, name in chats.items():
        print(f"TELEGRAM_NOTIFY_CHAT_ID={chat_id}   ({name})")


if __name__ == "__main__":
    main()
