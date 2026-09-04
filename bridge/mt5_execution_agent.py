"""
AURON MT5 Execution Agent
==========================

*** THIS SCRIPT CAN PLACE REAL ORDERS ON A REAL MT5 ACCOUNT. ***

Runs locally, on the same Windows machine as a logged-in MetaTrader 5
terminal (same as mt5_pusher.py). AURON's own backend runs in a Docker
container and cannot load the Windows-only MetaTrader5 package, so it
cannot place a real order itself -- this script is the one piece that can.

What it does, every cycle:
  1. Polls AURON for orders in state "preflight-ready" for one workspace
     (account). Every such order has ALREADY passed every deterministic
     check AURON's own code enforces (quote freshness, price deviation,
     volume/stop validity, risk limits) AND already has human_approved=True
     set on the AURON side -- this script makes no trading decisions of
     its own. It only executes what AURON has already fully authorized.
  2. For each one, calls the real MetaTrader5 API: symbol_info,
     symbol_info_tick, order_check, then order_send.
  3. Reports the real broker response back to AURON, verbatim. AURON does
     the same classification (executed / partial fill / rejected /
     reconciliation-required) it would if it had called order_send itself.

Safety:
  - Requires --i-understand-this-places-real-orders on every run. There is
    no way to silence or skip this.
  - Only ever acts on orders already in "preflight-ready" state for the
    workspace you point it at -- it cannot create, approve, or modify an
    order, only execute one AURON already fully authorized.
  - If MetaTrader5.order_send() itself fails or errors, the raw error is
    reported back to AURON as a failed report, never silently retried.

Requirements (same machine as mt5_pusher.py):
    pip install MetaTrader5 requests

Usage:
    python mt5_execution_agent.py \\
        --backend-url http://localhost:8000 \\
        --workspace-id <your AURON account_id> \\
        --i-understand-this-places-real-orders \\
        --interval 5
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import MetaTrader5 as mt5
except ImportError:
    print(
        "The MetaTrader5 package is not installed or not usable on this machine.\n"
        "This script only works on Windows, with a MetaTrader 5 terminal installed.\n"
        "Install it with: pip install MetaTrader5",
        file=sys.stderr,
    )
    raise

try:
    import requests
except ImportError:
    print("Missing dependency. Install it with: pip install requests", file=sys.stderr)
    raise


TYPE_MAP = {
    ("market", "buy"): "ORDER_TYPE_BUY",
    ("market", "sell"): "ORDER_TYPE_SELL",
    ("limit", "buy"): "ORDER_TYPE_BUY_LIMIT",
    ("limit", "sell"): "ORDER_TYPE_SELL_LIMIT",
    ("stop", "buy"): "ORDER_TYPE_BUY_STOP",
    ("stop", "sell"): "ORDER_TYPE_SELL_STOP",
}


def build_mt5_request(order: dict) -> dict:
    """Mirrors executive_mt5_live_order_executor/native_executor.py's
    build_request exactly, so a remote-executed order and a (hypothetical)
    locally-executed one behave identically."""
    req = order["request"]
    is_buy = req["side"] == "buy"
    order_type_name = TYPE_MAP[(req["order_type"], req["side"])]
    order_type = getattr(mt5, order_type_name)

    price = req.get("requested_price")
    if req["order_type"] == "market":
        price = req["quote_ask"] if is_buy else req["quote_bid"]

    request = {
        "action": mt5.TRADE_ACTION_DEAL if req["order_type"] == "market" else mt5.TRADE_ACTION_PENDING,
        "symbol": req["symbol"],
        "volume": req["volume"],
        "type": order_type,
        "price": price,
        "deviation": req["max_deviation_points"],
        "magic": req.get("magic", 0),
        "comment": req.get("comment", "AURON"),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    if req.get("stop_loss") is not None:
        request["sl"] = req["stop_loss"]
    if req.get("take_profit") is not None:
        request["tp"] = req["take_profit"]
    return request


class AuronClient:
    def __init__(self, backend_url: str) -> None:
        self.base = backend_url.rstrip("/") + "/v1/executive-mt5-live-order-executor"
        self.session = requests.Session()

    def pending_execution(self, workspace_id: str) -> list[dict]:
        response = self.session.get(f"{self.base}/orders/pending-execution", params={"workspace_id": workspace_id}, timeout=10)
        response.raise_for_status()
        return response.json()

    def report_execution(self, workspace_id: str, record_id: str, report: dict) -> None:
        response = self.session.post(
            f"{self.base}/orders/{record_id}/report-execution", params={"workspace_id": workspace_id}, json=report, timeout=10
        )
        response.raise_for_status()


def execute_one(order: dict) -> dict:
    """Calls the real MT5 API for one already-fully-authorized order and
    returns a report dict AURON's report-execution endpoint expects.
    Never raises -- any failure becomes a failed-looking report instead,
    so the caller always has something concrete to send back."""
    symbol = order["request"]["symbol"]
    try:
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return {"broker_comment": f"symbol_info/tick unavailable for {symbol}", "filled_volume": 0}

        native_request = build_mt5_request(order)
        check = mt5.order_check(native_request)
        if check is None or getattr(check, "retcode", 1) not in (0, 10009):
            return {
                "broker_retcode": getattr(check, "retcode", None),
                "broker_comment": getattr(check, "comment", "order_check rejected"),
                "filled_volume": 0,
            }

        result = mt5.order_send(native_request)
        if result is None:
            return {"broker_comment": f"order_send returned None: {mt5.last_error()}", "filled_volume": 0}

        return {
            "broker_retcode": getattr(result, "retcode", None),
            "broker_order_id": getattr(result, "order", None),
            "broker_deal_id": getattr(result, "deal", None),
            "broker_comment": getattr(result, "comment", None),
            "filled_volume": float(getattr(result, "volume", 0) or 0),
            "average_price": getattr(result, "price", None),
        }
    except Exception as exc:  # noqa: BLE001 -- report whatever happened, never crash the agent loop
        return {"broker_comment": f"execution agent error: {exc}", "filled_volume": 0}


def process_pending(client: "AuronClient", workspace_id: str, already_executed: dict) -> None:
    """One polling cycle's worth of work -- pulled out of main() so the
    critical safety property (order_send called at most once per record,
    even across many cycles of a failing report) is directly testable."""
    pending = client.pending_execution(workspace_id)
    for order in pending:
        order_id = order["id"]
        if order_id in already_executed:
            report = already_executed[order_id]
            print(f"[re-reporting] {order_id} (already executed this run, only retrying the report)")
        else:
            print(f"[executing] {order_id} {order['request']['symbol']} {order['request']['side']} {order['request']['volume']}")
            report = execute_one(order)
            already_executed[order_id] = report
        try:
            client.report_execution(workspace_id, order_id, report)
            print(f"[reported] {order_id} -> {report}")
        except requests.HTTPError as exc:
            print(f"[warn] report-execution rejected for {order_id}, will retry the report (not re-execute): {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--workspace-id", required=True, help="The AURON account_id to execute orders for.")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument(
        "--i-understand-this-places-real-orders",
        action="store_true",
        required=True,
        help="Required. This script places real orders on your MT5 account when AURON has a preflight-ready order waiting.",
    )
    args = parser.parse_args()

    if not mt5.initialize():
        print(f"mt5.initialize() failed: {mt5.last_error()}", file=sys.stderr)
        sys.exit(1)

    client = AuronClient(args.backend_url)
    # Every record.id is executed AT MOST ONCE per agent run, no matter how
    # many polling cycles it takes to successfully report the result back.
    # A failed *report* is retried with the cached result; order_send()
    # itself is never called a second time for the same record.
    already_executed: dict[str, dict] = {}

    print(f"*** LIVE EXECUTION AGENT RUNNING for workspace {args.workspace_id} ***")
    print("Any preflight-ready, human-approved order for this account will be sent to the real broker.")
    print(f"Polling every {args.interval}s. Ctrl+C to stop.\n")

    try:
        while True:
            start = time.monotonic()
            try:
                process_pending(client, args.workspace_id, already_executed)
            except requests.RequestException as exc:
                print(f"[warn] AURON communication failed, will retry next cycle: {exc}", file=sys.stderr)
            elapsed = time.monotonic() - start
            time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
