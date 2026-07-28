"""Stable contract constants for PHOENIX v21.141."""
MODULE_VERSION = "21.141"
MODULE_NAME = "governed-primary-recovery-reconciliation-completion-attestation"
ALLOWED_OPERATIONS = ("GET", "HEAD")
TERMINAL_SUCCESS_STATE = "attested"
FAIL_CLOSED_STATE = "mismatch"
REQUIRED_BINDINGS = (
    "permit_id",
    "recovery_plan_digest",
    "primary_adapter_id",
    "primary_worker_id",
    "gateway_id",
    "receipt_id",
    "response_digest",
)
FORBIDDEN_SIDE_EFFECTS = (
    "write",
    "credential-mutation",
    "permission-mutation",
    "fund-movement",
    "order-execution",
    "trading-execution",
    "repository-mutation",
    "route-mutation",
)
