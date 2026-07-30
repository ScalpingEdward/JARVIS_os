# AURON v21.242

AURON is the operator-facing identity replacing PHOENIX in the new conversational command center.

## Added
- `/auron/demo1/v21.242/command-center`
- `/auron/demo1/v21.242/dialogue`
- Conversational fallback for commands that do not map to Demo 1 capabilities
- Existing v21.238 intent routing remains the execution boundary for supported tools
- Cleaner operator-facing summaries instead of verbose internal routing text
- Browser voice selection biased toward natural German voices, preferring Microsoft Conrad/Natural when available
- High-risk and financial execution still requires human approval

## Voice
The browser implementation selects the best installed German voice. Priority is Microsoft Conrad / Natural, then other Microsoft Natural voices, then Google German voices. Speech rate is slightly reduced and pitch slightly lowered for a calmer operator voice.

## Safety boundary
Conversation does not create new execution authority. Unsupported commands can be answered conversationally, but only already-governed capabilities are executed. Financial/high-risk autonomous execution remains disabled.
