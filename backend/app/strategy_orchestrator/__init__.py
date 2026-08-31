"""Strategy orchestrator — evaluates assigned strategies for all accounts with compliance.

Brings together the three building blocks:
1. Accounts registry (which accounts exist, which strategies are assigned)
2. Strategies (evaluate market snapshots → generate setups)
3. Compliance (filter out setups that would violate account rules)

The orchestrator evaluates all assigned strategies for all active accounts,
applies compliance filtering, and returns only setups that are safe to execute.
"""
