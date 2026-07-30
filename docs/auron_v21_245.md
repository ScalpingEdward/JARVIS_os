# AURON v21.245

AURON v21.245 makes explicit long-term memory part of normal conversation context.

## Added
- Normal dialogue automatically loads operator/workspace-scoped long-term facts from v21.244.
- Configured OpenAI/Anthropic dialogue generation receives both recent conversation turns and long-term facts.
- Long-term facts are instructed to be used only when relevant; AURON must not invent memories.
- New `/auron/demo1/v21.245/memory-context` inspection endpoint.
- Command center shows both recent context-turn count and long-term fact count.
- Existing remember/recall/forget commands remain available.
- Existing command-input clearing behavior remains active.
- Financial/high-risk execution remains approval-gated.

## Runtime
Checkpoint URL after merge/pull:
`http://127.0.0.1:8000/auron/demo1/v21.245/command-center`
