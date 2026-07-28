"""Stable constants for PHOENIX v21.147."""
MODULE_VERSION = "21.147"
MODULE_NAME = "baseline-consumer-adoption-receipt-drift-monitoring-governance"
SUPPORTED_CONSUMERS = (
    "adapter-selection",
    "worker-selection",
    "dispatch-planning",
    "failover-health",
    "recovery-readiness",
)
ADOPTION_STATE = "adopted"
DRIFT_STATE = "drift-detected"
DRIFT_REVIEWED_STATE = "drift-reviewed"
FAIL_CLOSED_STATE = "blocked"
AUTONOMOUS_CORRECTION = False
AUTONOMOUS_ROUTING_MUTATION = False
AUTONOMOUS_POLICY_MUTATION = False
