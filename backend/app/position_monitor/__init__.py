"""Periodic re-assessment of live broker positions for break-even and
trailing-stop, using data mt5_bridge already has -- no new credentials,
no new external dependency.

The gap this closes: nothing in this backend runs on its own. Every
"scheduler"-named module (temporal_scheduler, execution/scheduler.py,
workers, automation_runtime before this session's change) is a pull-based
state machine waiting for an external caller. Once a real position exists
(after the separate, human-reviewed execute() step this session never
touches), nothing was watching it -- break-even and trailing-stop were
real, tested, reachable APIs that only ever did anything if a human
manually POSTed fresh price data to them, repeatedly, by hand.

This module is that missing periodic caller, and nothing more. It never
modifies a stop-loss, never closes a position, never dispatches a command.
It only ever calls executive_mt5_break_even_scale_out.create() and
executive_mt5_position_stream_trailing_stop.assess() -- both of which only
*propose* what should happen next. Their own separate execute() steps,
already gated behind human review exactly like everywhere else, are
completely unchanged.

Trailing genuinely activates and computes a real proposed stop once the
underlying mt5_bridge connection actually is healthy: connected (the same
MT5ConnectionState this terminal already exposes, driven by heartbeat/
ingest freshness) and free of a detected sequence gap (see
MT5SnapshotIngest.sequence -- a per-cycle counter the pusher now sends,
letting the backend tell "still getting pushes" apart from "getting them
without a dropped cycle in between"). When the terminal really is stale
or disconnected, or a gap really was detected, trailing still correctly
and honestly reports why, rather than fabricating health it does not have.

A precise correction to an earlier version of this note: break-even's own
gate checks for trailing_state == "trailing-active", which is trailing's
own FULLY-EXECUTED terminal state (reached only after human approval,
broker acknowledgment, and reconciliation) -- not "trailing is currently
functioning". Trailing reaching approval-required (a real, computed
proposal) is genuine progress and is not the same thing. Break-even
correctly continues to wait for trailing to be fully, humanly executed
first, in both directions -- this is deliberate sequencing in
break_even_scale_out's own original design, not a remaining gap this
session left unclosed.
"""
