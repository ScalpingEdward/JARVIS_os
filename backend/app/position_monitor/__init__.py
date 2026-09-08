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

An important, honest limitation, found while wiring the Telegram
notification for an actionable break-even state (see service.py's
_notify_if_newly_actionable): break_even_scale_out's own evaluation logic
(not this module's) requires trailing_state == "trailing-active" as a
precondition before it will even look at whether the 1R trigger has been
reached. Since trailing can never honestly report itself as active without
real streaming infrastructure, break-even is -- today -- ALSO structurally
unable to reach an actionable state, by that module's own original design,
not by any choice made here. This monitor still produces real, honest,
continuously-fresh assessment records; they will correctly show
"trailing-required" indefinitely until a real streaming transport exists.
The notification logic itself is unit-tested directly and is ready to
fire the day that changes.
"""
