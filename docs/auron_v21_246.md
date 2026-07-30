# AURON v21.246

AURON v21.246 adds relevance-ranked long-term memory retrieval.

## Added
- Ranks stored operator facts against the current command instead of loading every fact into dialogue context.
- Uses lexical overlap, stored priority and recency as deterministic ranking signals.
- Caps retrieved long-term facts at six per request.
- Falls back to the newest high-priority facts when no strong lexical match exists.
- Adds `GET /auron/demo1/v21.246/memory-retrieval?q=...` for inspecting retrieval results and scores.
- Adds retrieval metadata to dialogue responses: `retrieved_fact_count` and `retrieved_facts`.
- Keeps v21.244 explicit remember/recall/forget commands intact.
- Keeps command-input clearing and persistent conversation context intact.
- Financial/high-risk execution remains approval-gated.

## Why
As AURON accumulates more memory, sending all stored facts to the model becomes noisy and expensive. v21.246 selects the facts most likely to matter for the current question.

## Checkpoint
No local restart is required yet. Merge modules first and test the accumulated checkpoint later.
