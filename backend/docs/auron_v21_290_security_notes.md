# Telegram Bridge Security Notes

- A Telegram chat is not trusted until a pairing code has been verified.
- Chat ID and Telegram user ID must both match the stored binding.
- Telegram update IDs are idempotency keys.
- Text and voice ingestion are separated from conversation routing and provider calls.
- No bot token, webhook registration, file download, transcription or outbound message is performed in v21.290.
