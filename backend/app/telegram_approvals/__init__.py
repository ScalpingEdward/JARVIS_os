"""Telegram inline-button approvals for setup_submission.

Sends a pending SubmittedSetup as a real Telegram message with Approve/Reject
inline buttons, and receives the tap back through a webhook, calling
setup_submission's decide() -- the actual human-approval gate the whole
trade_risk_pipeline chain depends on (see setup_submission/service.py).

This is the piece flagged after the first live trade: approval previously
meant a PowerShell command against the API by hand. It still means a human
decides -- the buttons just replace the terminal.
"""
