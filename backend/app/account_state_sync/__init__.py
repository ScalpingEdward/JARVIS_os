"""Account state synchronization from MT5 terminals into the accounts registry.

Bridges the read-only MT5 bridge (/v1/mt5) and the persistent accounts registry
(/v1/accounts) -- finds each registered account's MT5 terminal by (login, server)
match, extracts the broker snapshot (balance, equity), and pushes it into the
registry where compliance/breach-detection runs automatically.
"""
