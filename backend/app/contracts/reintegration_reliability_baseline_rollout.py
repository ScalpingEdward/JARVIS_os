"""Stable constants for PHOENIX v21.155."""
MODULE_VERSION = "21.155"
MODULE_NAME = "reintegration-reliability-baseline-commit-controlled-consumer-rollout-governance"
ALLOWED_CONSUMERS = (
    "adapter-selection",
    "worker-selection",
    "dispatch-planning",
    "failover-health",
    "recovery-readiness",
)
ADMISSION_STATE = "approved-preview"
REVIEW_STATE = "review-required"
COMMITTED_STATE = "committed"
STAGED_STATE = "staged"
ACTIVE_STATE = "active"
FAIL_CLOSED_STATE = "blocked"
DEFAULT_MAX_STAGE = 3
AUTONOMOUS_BASELINE_MUTATION = False
AUTONOMOUS_CONSUMER_ACTIVATION = False
AUTONOMOUS_ROUTING_MUTATION = False
