from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TelethonBootstrapAssessment,
    TelethonBootstrapAssessmentCreate,
    TelethonBootstrapScores,
    TelethonBootstrapState,
    TelethonBootstrapStatusResponse,
)


class ExecutiveTelethonClientBootstrapService:
    def __init__(self) -> None:
        self._records: dict[UUID, TelethonBootstrapAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._client_sessions: set[tuple[str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TelethonBootstrapAssessmentCreate) -> TelethonBootstrapAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        client_key = (payload.workspace_id, payload.client_id, payload.session_reference)
        if source_key in self._source_keys:
            raise ValueError("Duplicate Telethon bootstrap source key")
        if client_key in self._client_sessions:
            raise ValueError("Duplicate Telethon client session bootstrap")

        observation = payload.observation
        policy = payload.policy
        reasons: list[str] = []
        session_integrity = payload.session_reference_resolved and not payload.raw_session_embedded
        identity_matches = (
            payload.expected_account_id is None
            or payload.expected_account_id == payload.observed_account_id
        )
        runtime_safe = (
            observation.read_only_verified
            and observation.dry_run_only
            and not observation.write_method_exposed
            and observation.latency_ms <= policy.maximum_latency_ms
            and observation.reconnects <= policy.maximum_reconnects
            and observation.flood_wait_seconds <= policy.maximum_flood_wait_seconds
        )
        dry_run_complete = (
            observation.client_instantiated
            and observation.session_loaded
            and observation.connected
            and observation.update_handler_registered
            and observation.media_download_probe_succeeded
        )

        if not payload.risk_brain_clear:
            state, action = TelethonBootstrapState.blocked, "block-telethon-bootstrap"
            reasons.append("Risk Brain blocks Telethon client bootstrap")
        elif payload.sdk_client_state not in {"client-ready", "dispatched"}:
            state, action = TelethonBootstrapState.blocked, "complete-sdk-client-governance"
            reasons.append("Telegram SDK client governance has not authorized Telethon bootstrap")
        elif not session_integrity:
            state, action = TelethonBootstrapState.bootstrap_required, "resolve-isolated-telethon-session"
            reasons.append("Telethon bootstrap requires a resolved isolated session reference")
        elif policy.require_authorized_session and not observation.authorized:
            state, action = TelethonBootstrapState.authentication_required, "complete-telethon-session-authorization"
            reasons.append("Telethon session is not authorized")
        elif policy.require_identity_verification and (not observation.identity_verified or not identity_matches):
            state, action = TelethonBootstrapState.authentication_required, "verify-telethon-account-identity"
            reasons.append("Telethon account identity was not verified or does not match")
        elif policy.prohibit_write_methods and observation.write_method_exposed:
            state, action = TelethonBootstrapState.blocked, "remove-telethon-write-capability"
            reasons.append("Write-capable Telethon runtime is prohibited")
        elif policy.require_read_only_runtime and not runtime_safe:
            state, action = TelethonBootstrapState.blocked, "enforce-read-only-bounded-telethon-runtime"
            reasons.append("Telethon runtime violates read-only, latency, reconnect or flood-wait policy")
        elif policy.require_dry_run and not dry_run_complete:
            state, action = TelethonBootstrapState.dry_run_failed, "repeat-bounded-telethon-dry-run"
            reasons.append("Telethon dry-run connectivity or media probe is incomplete")
        else:
            state, action = TelethonBootstrapState.runtime_ready, "accept-telethon-runtime"
            reasons.append("Telethon client passed session, identity, dry-run and read-only gates")

        dispatchable = state == TelethonBootstrapState.runtime_ready
        if dispatchable:
            state = TelethonBootstrapState.dispatched
            action = "dispatch-telethon-runtime-to-v18-60"
            reasons.append("Governed Telethon runtime is ready for transport execution")

        session_score = 100 if session_integrity else 0
        instantiation_score = 100 if observation.client_instantiated and observation.session_loaded else 0
        authentication_score = 100 if observation.authorized and observation.identity_verified and identity_matches else 0
        safety_score = 100 if runtime_safe else 0
        dry_run_score = 100 if dry_run_complete else 0
        confidence = round((session_score + instantiation_score + authentication_score + safety_score + dry_run_score) / 5)

        record = TelethonBootstrapAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            sdk_client_assessment_id=payload.sdk_client_assessment_id,
            client_id=payload.client_id,
            state=state,
            dispatchable=dispatchable,
            target_module="executive-telegram-transport" if dispatchable else None,
            recommended_action=action,
            scores=TelethonBootstrapScores(
                session_integrity=session_score,
                instantiation_quality=instantiation_score,
                authentication_quality=authentication_score,
                read_only_safety=safety_score,
                dry_run_quality=dry_run_score,
                bootstrap_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._client_sessions.add(client_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def status(self, workspace_id: str) -> TelethonBootstrapStatusResponse:
        items = self.list_assessments(workspace_id)
        return TelethonBootstrapStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def list_assessments(self, workspace_id: str) -> list[TelethonBootstrapAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> TelethonBootstrapAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_telethon_client_bootstrap_service = ExecutiveTelethonClientBootstrapService()
