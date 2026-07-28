MODULE_VERSION="21.142"
MODULE_NAME="recovery-stability-observation-primary-route-confidence-governance"
SUCCESS_STATE="stable"
FAIL_CLOSED_STATES=("blocked","degraded")
MIN_PRIMARY_ROUTE_CONFIDENCE=.85
REQUIRED_SAMPLE_FIELDS=("primary_available","latency_ms","receipt_reconciliation","worker_heartbeat_ok","gateway_healthy","adapter_healthy","confidence","freshness")
PROTECTED_OPERATIONS=("trade-execute","order-submit","fund-move","credential-mutate","permission-expand")
