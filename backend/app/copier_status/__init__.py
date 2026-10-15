"""What the signal copiers report: balance, equity and profit per Telegram group.

Each copier profile (one MT5 account, see signal_copier/profiles.py) pushes
its whole status every minute; the latest one per profile is kept, nothing
older. Read-only towards MT5 -- this module stores and adds up, it trades
nothing and steers nothing.
"""
