# AURON v21.244

AURON v21.244 adds explicit long-term memory commands and improves the command-entry UX.

## Added
- `Merk dir ...` / `Remember that ...` writes an operator-scoped long-term fact.
- `Was hast du dir gemerkt?` / `What do you remember?` recalls explicit facts.
- `Vergiss ...` / `Forget ...` removes matching explicit facts.
- Broad `Vergiss alles` is not executed silently; AURON asks for a specific target.
- Long-term facts are stored in the existing SQL-backed memory service and scoped by workspace/operator, not by browser session.
- The command input is cleared and focused immediately after Enter/Run, so the previous command no longer remains in the text field.
- Existing v21.243 conversation context remains active for ordinary dialogue.
- Existing financial/high-risk approval gating remains unchanged.

## Runtime
Open after merge/pull:
`http://127.0.0.1:8000/auron/demo1/v21.244/command-center`
