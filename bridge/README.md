# AURON MT5 Bridge

Connects a real, running MetaTrader 5 terminal to AURON, so the trade-risk
pipeline (`dynamic_risk_engine`, `prepare-live-order`, etc.) can use real
account balances, live ticks, and real contract specs instead of
caller-supplied placeholders.

**Read-only.** This script only reads from MT5 (`account_info`,
`positions_get`, `orders_get`, `history_deals_get`, `symbol_info`,
`symbol_info_tick`). It never calls `order_send` or `order_check`. AURON's
`mt5_bridge` module refuses to register anything that isn't `read_only=True`.

## Requirements

- Windows (the `MetaTrader5` Python package is Windows-only)
- A MetaTrader 5 terminal installed and **logged in** to the account you
  want AURON to see
- Python 3.10+ on that same machine
- Network access from that machine to wherever AURON's backend is running

## Setup

1. On the Windows machine with MT5, install dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Make sure the MT5 terminal is open and logged in.

3. Run the pusher:

   ```
   python mt5_pusher.py ^
       --backend-url http://<your-auron-host>:8000 ^
       --account-login 12345678 ^
       --server "YourBroker-Server" ^
       --broker "YourBroker" ^
       --symbols XAUUSD,EURUSD ^
       --interval 5
   ```

   Replace `--backend-url` with wherever AURON is actually reachable from
   this machine -- `http://localhost:8000` if AURON runs on the same
   machine, or your Docker host's address/hostname if AURON runs in a
   container reachable over your network (see `docs/n8n-instagram-setup.md`
   for the same kind of local-network reasoning applied to n8n).

4. First run registers a new terminal with AURON and saves the returned
   `terminal_id` to `mt5_bridge_state.json` next to the script. Subsequent
   runs reuse it -- delete that file if you ever want to register fresh
   (e.g. after changing account/server).

5. Leave it running. It pushes a snapshot (account state, positions,
   pending orders, recent deals, ticks, and symbol specs for the symbols
   you listed) every `--interval` seconds, plus a heartbeat each cycle.

## Connecting it to the accounts registry

Once ticks are flowing, `trade_risk_pipeline` can look up live quotes and
contract specs automatically (see the master plan entries on the live-quote
and contract-spec gaps) -- **provided** the `login` and `server` on the
AURON-side trading account (`POST /v1/accounts`) match `--account-login`
and `--server` here exactly. That's the same `(login, server)` match
`account_state_sync` uses to sync balances.

## Adding more symbols later

Just restart the script with an updated `--symbols` list; nothing needs to
change on the AURON side. Symbol specs and ticks are replaced by symbol
each ingest, not accumulated, so there's no cleanup needed either.

## Stopping

Ctrl+C. The terminal record on the AURON side will show as `stale` after
30 seconds without a heartbeat, and `disconnected` after 2 minutes -- it
doesn't need to be explicitly deregistered.
