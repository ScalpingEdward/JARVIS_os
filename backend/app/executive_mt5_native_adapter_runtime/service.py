from datetime import datetime, timezone
from uuid import UUID

from .adapter import MetaTrader5Adapter, NativeMetaTrader5Adapter
from .models import (
    AdapterRuntimeEvidence,
    NativeAdapterAssessment,
    NativeAdapterAssessmentCreate,
    NativeAdapterAuditRecord,
    NativeAdapterExecuteRequest,
    NativeAdapterState,
    NativeAdapterStatusResponse,
)


class NativeAdapterRuntimeService:
    def __init__(self, adapter: MetaTrader5Adapter | None = None) -> None:
        self._adapter = adapter or NativeMetaTrader5Adapter()
        self._records: dict[UUID, NativeAdapterAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[NativeAdapterAuditRecord] = []

    def _initial_state(self, payload: NativeAdapterAssessmentCreate) -> tuple[NativeAdapterState, str]:
        if payload.risk_brain_blocked:
            return NativeAdapterState.BLOCKED, "Risk Brain hard block is active"
        if not payload.pipeline_active:
            return NativeAdapterState.PIPELINE_REQUIRED, "v18.95 pipeline-active evidence is required"
        if not payload.terminal_path_configured or not payload.credentials_reference_configured:
            return NativeAdapterState.CONFIGURATION_INVALID, "Terminal path and secret reference must be configured"
        if payload.requested_account_login not in payload.allowed_account_logins:
            return NativeAdapterState.ACCOUNT_MISMATCH, "Requested account is not in the allowlist"
        if not payload.account_risk_approved or not payload.prop_rules_approved:
            return NativeAdapterState.BLOCKED, "Account-risk and prop-rule approval are required"
        if not payload.human_approved:
            return NativeAdapterState.APPROVAL_REQUIRED, "Human approval is required before native connection"
        return NativeAdapterState.INITIALIZATION_PENDING, "Native adapter is approved for initialization"

    def create(self, payload: NativeAdapterAssessmentCreate) -> NativeAdapterAssessment:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("Duplicate source_key in workspace")
        state, reason = self._initial_state(payload)
        record = NativeAdapterAssessment(**payload.model_dump(), state=state, reason=reason)
        self._records[record.id] = record
        self._source_keys.add(key)
        self._append_audit(record, payload.actor_id, "create", reason)
        return record

    def _evaluate_evidence(self, record: NativeAdapterAssessment, evidence: AdapterRuntimeEvidence) -> tuple[NativeAdapterState, str]:
        if not evidence.package_available:
            return NativeAdapterState.PACKAGE_UNAVAILABLE, "MetaTrader5 package is unavailable"
        if not evidence.initialized:
            return NativeAdapterState.INITIALIZATION_PENDING, "MetaTrader5 initialize did not complete"
        if not evidence.logged_in:
            return NativeAdapterState.LOGIN_PENDING, "No authenticated MT5 account is available"
        if evidence.account_login != record.requested_account_login:
            return NativeAdapterState.ACCOUNT_MISMATCH, "Connected account does not match the approved login"
        if not evidence.terminal_connected or not evidence.trade_allowed:
            return NativeAdapterState.TERMINAL_UNHEALTHY, "Terminal connection or trading permission is unhealthy"
        missing = sorted(set(record.required_symbols) - set(evidence.visible_symbols))
        if missing:
            return NativeAdapterState.SYMBOL_SYNC_REQUIRED, f"Required symbols are not visible: {', '.join(missing)}"
        return NativeAdapterState.ADAPTER_READY, "Native MetaTrader5 adapter is connected and reconciled"

    def execute(self, record_id: UUID, workspace_id: str, request: NativeAdapterExecuteRequest) -> NativeAdapterAssessment:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("Native adapter assessment not found")
        if request.human_approved is not None:
            record.human_approved = request.human_approved
        if record.risk_brain_blocked:
            record.state = NativeAdapterState.BLOCKED
            record.reason = "Risk Brain hard block is active"
        elif not record.human_approved and request.action != "disconnect":
            record.state = NativeAdapterState.APPROVAL_REQUIRED
            record.reason = "Human approval is required"
        elif request.action == "connect":
            record.evidence = self._adapter.connect(record.requested_account_login, record.required_symbols)
            record.state, record.reason = self._evaluate_evidence(record, record.evidence)
        elif request.action == "heartbeat":
            record.evidence = self._adapter.heartbeat(record.required_symbols)
            record.state, record.reason = self._evaluate_evidence(record, record.evidence)
        else:
            record.evidence = self._adapter.disconnect()
            record.state = NativeAdapterState.DISCONNECTED
            record.reason = "Native adapter disconnected cleanly"
        record.updated_at = datetime.now(timezone.utc)
        self._append_audit(record, request.actor_id, request.action, record.reason or "")
        return record

    def get(self, record_id: UUID, workspace_id: str) -> NativeAdapterAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[NativeAdapterAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> NativeAdapterStatusResponse:
        records = self.list_records(workspace_id)
        return NativeAdapterStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            ready=sum(record.state == NativeAdapterState.ADAPTER_READY for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[NativeAdapterAuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _append_audit(self, record: NativeAdapterAssessment, actor_id: str, action: str, detail: str) -> None:
        self._audit.append(
            NativeAdapterAuditRecord(
                assessment_id=record.id,
                workspace_id=record.workspace_id,
                actor_id=actor_id,
                action=action,
                state=record.state,
                detail=detail,
            )
        )


native_adapter_runtime_service = NativeAdapterRuntimeService()
