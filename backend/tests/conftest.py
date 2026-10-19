"""Test-wide settings, applied before any app module is imported.

Two stores default to files that are tracked in git (data/workflows.json and
.phoenix/demo1_approval_inbox.json); every test run used to rewrite them. Tests write to a
throwaway directory instead -- the real files are only touched by the running app.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="auron-tests-")
os.environ.setdefault("JARVIS_WORKFLOW_STORE", os.path.join(_tmp, "workflows.json"))
os.environ.setdefault("PHOENIX_DEMO1_APPROVAL_INBOX_PATH", os.path.join(_tmp, "demo1_approval_inbox.json"))

# No test may reach a real MetaTrader terminal. On Brano's laptop the MetaTrader5 package is
# installed (the copier uses it), so code that imports it would build a REAL order executor --
# test_executive_mt5_live_order_executor did, and failed only because it never connected.
# Tests that need MT5 behaviour inject a fake; an import of the real package fails here.
import sys  # noqa: E402

sys.modules["MetaTrader5"] = None
