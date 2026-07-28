"""Stable constants for PHOENIX v21.146."""
MODULE_VERSION = "21.146"
MODULE_NAME = "baseline-consumer-eligibility-controlled-rollout-governance"
ALLOWED_CONSUMERS = (
    "adapter-selection",
    "worker-selection",
    "dispatch-planning",
    "failover-health",
    "recovery-readiness",
)
DEFAULT_MAX_STAGE = 3
MAX_ALLOWED_STAGE = 5
MAX_BLAST_RADIUS = 0.35
MAX_RESIDUAL_RISK = 0.25
SUCCESS_STATE = "active"
FAIL_CLOSED_STATE = "blocked"
AUTONOMOUS_ROUTING_MUTATION = False
AUTONOMOUS_POLICY_MUTATION = False
AUTONOMOUS_PERMISSION_MUTATION = False
AUTONOMOUS_EXECUTION = False
