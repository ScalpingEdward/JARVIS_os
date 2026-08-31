"""Setup Submission — bridge between strategy evaluation and the approval gate.

This module takes a :class:`MarketSnapshot`, evaluates every executable account's
enabled strategies against it, and turns each resulting trading setup into an
approval request. It never executes trades: it only submits compliant setups to
the (future) Phoenix approval inbox so a human operator can approve or reject
them through the existing approval-gated execution chain.

For now approval requests are held in memory, keyed by a generated
``approval_request_id`` (UUID4). A later PR will persist them into the real
Phoenix ``demo1_approval_inbox`` format without changing this module's public
contract.
"""
