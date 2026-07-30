# AURON v21.247

AURON v21.247 adds governed conversational memory learning.

## Added
- Detects likely durable preferences, goals, plans and priorities in ordinary conversation.
- Creates a session-scoped pending memory candidate instead of silently writing long-term memory.
- AURON asks: `Soll ich mir das merken?`
- `Ja merk dir das` promotes the latest pending candidate into operator/workspace-scoped long-term memory.
- `Nein`, `Nicht merken` or `Vergiss es` rejects the candidate.
- Only one pending candidate is kept per session; newer candidates replace older pending candidates.
- New `GET /auron/demo1/v21.247/memory-candidate` endpoint exposes the current pending candidate.
- Command-center status shows `MEMORY · CONFIRM?` while a candidate awaits a decision.
- Existing v21.246 relevance-ranked retrieval remains active.
- Financial/high-risk actions remain approval-gated.

## Design boundary
AURON does not silently convert ordinary conversation into permanent memory. Durable memory requires explicit operator confirmation.

## Checkpoint URL
`http://127.0.0.1:8000/auron/demo1/v21.247/command-center`
