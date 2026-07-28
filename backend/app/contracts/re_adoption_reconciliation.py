"""Stable constants for PHOENIX v21.159."""
MODULE_VERSION = "21.159"
MODULE_NAME = "re-adoption-receipt-reconciliation-coordinated-recovery-completion-governance"
ADMISSION_STATE = "recovery-ready"
REVIEW_STATE = "review-required"
SUCCESS_STATE = "completed"
FAIL_CLOSED_STATE = "incomplete"
RECEIPT_REQUIRED_STATE = "adopted"
REQUIRED_BINDINGS = (
    "workspace_id",
    "consumer_id",
    "baseline_id",
    "baseline_version",
    "baseline_digest",
    "source_digest",
)
AUTONOMOUS_CONSUMER_MUTATION = False
AUTONOMOUS_BASELINE_MUTATION = False
AUTONOMOUS_ROUTING_MUTATION = False
AUTONOMOUS_POLICY_MUTATION = False
AUTONOMOUS_EXECUTION = False
