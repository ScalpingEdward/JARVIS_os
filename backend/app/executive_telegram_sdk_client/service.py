from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TelegramSdkClientAssessment,
    TelegramSdkClientAssessmentCreate,
    TelegramSdkClientScores,
    TelegramSdkClientState,
    TelegramSdkClientStatusResponse,
)


class ExecutiveTelegramSdkClientService:
    def __init__(self) -> None:
        self._records: dict[UUID, TelegramSdkClientAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._client_versions: set[tuple[str, str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TelegramSdkClientAssessmentCreate) -> TelegramSdkClientAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        client_key = (
            payload.workspace_id,
            payload.client_id,
            payload.config.sdk_package,
            payload.config.sdk_version,
        )
        if source_key in self._source_keys:
            raise ValueError("Duplicate Telegram SDK client source key")
        if client_key in self._client_versions:
            raise ValueError("Duplicate Telegram SDK client configuration")

        policy = payload.policy
        config = payload.config
        reasons: list[str] = []

        package_allowed = (
            config.transport_type == "telethon"
            and config.sdk_package in policy.allowed_telethon_packages
        ) or (
            config.transport_type == "bot-api"
            and config.sdk_package in policy.allowed_bot_api_packages
        )
        telethon_refs = bool(config.session_reference and config.api_id_reference and config.api_hash_reference)
        bot_refs = bool(config.bot_token_reference)
        required_refs_present = telethon_refs if config.transport_type == "telethon" else bot_refs
        secrets_isolated = (
            required_refs_present
            and config.references_resolved
            and not config.raw_secret_values_present
            and not config.session_file_embedded
        )
        dependency_ready = config.dependency_installed and config.import_verified
        factory_ready = config.client_factory_verified
        runtime_safe = (
            config.read_only_mode
            and config.timeout_seconds <= policy.maximum_timeout_seconds
            and config.connection_retries <= policy.maximum_connection_retries
        )

        if not payload.risk_brain_clear:
            state, action = TelegramSdkClientState.blocked, "block-telegram-sdk-client"
            reasons.append("Risk Brain blocks Telegram SDK client configuration")
        elif payload.transport_state not in {"reconnect-required", "transport-ready", "dispatched"}:
            state, action = TelegramSdkClientState.blocked, "complete-telegram-transport-governance"
            reasons.append("Telegram transport governance has not authorized SDK client preparation")
        elif not package_allowed:
            state, action = TelegramSdkClientState.configuration_required, "select-approved-telegram-sdk-package"
            reasons.append("Configured SDK package is not allowed for the selected transport type")
        elif policy.require_resolved_secret_references and not secrets_isolated:
            state, action = TelegramSdkClientState.configuration_required, "resolve-isolated-telegram-runtime-references"
            reasons.append("Telegram runtime secrets must be resolved through isolated references")
        elif policy.prohibit_raw_secret_values and config.raw_secret_values_present:
            state, action = TelegramSdkClientState.blocked, "remove-raw-telegram-secrets"
            reasons.append("Raw Telegram secret values are prohibited in runtime configuration")
        elif policy.prohibit_embedded_session_file and config.session_file_embedded:
            state, action = TelegramSdkClientState.blocked, "remove-embedded-telegram-session"
            reasons.append("Embedded Telegram session files are prohibited")
        elif policy.require_dependency_installed and not dependency_ready:
            state, action = TelegramSdkClientState.dependency_unavailable, "install-and-verify-telegram-sdk"
            reasons.append("Telegram SDK dependency is unavailable or cannot be imported")
        elif policy.require_factory_verification and not factory_ready:
            state, action = TelegramSdkClientState.configuration_required, "verify-telegram-client-factory"
            reasons.append("Telegram SDK client factory has not been verified")
        elif policy.require_read_only_mode and not runtime_safe:
            state, action = TelegramSdkClientState.blocked, "enforce-read-only-bounded-runtime"
            reasons.append("Telegram SDK runtime is not read-only or exceeds timeout/retry policy")
        else:
            state, action = TelegramSdkClientState.client_ready, "accept-telegram-sdk-client-config"
            reasons.append("Telegram SDK client configuration passed package, secret, dependency and runtime gates")

        dispatchable = state == TelegramSdkClientState.client_ready
        if dispatchable:
            state = TelegramSdkClientState.dispatched
            action = "dispatch-sdk-client-config-to-v18-60"
            reasons.append("Governed SDK client configuration is ready for Telegram transport execution")

        secret_score = 100 if secrets_isolated else 0
        dependency_score = 100 if dependency_ready else 0
        factory_score = 100 if factory_ready else 0
        runtime_score = 100 if runtime_safe else 0
        config_score = round(
            100
            * sum(
                [
                    package_allowed,
                    required_refs_present,
                    config.references_resolved,
                    not config.raw_secret_values_present,
                    not config.session_file_embedded,
                ]
            )
            / 5
        )
        confidence = round(
            (secret_score + dependency_score + factory_score + runtime_score + config_score) / 5
        )

        record = TelegramSdkClientAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            transport_assessment_id=payload.transport_assessment_id,
            client_id=payload.client_id,
            transport_type=config.transport_type,
            sdk_package=config.sdk_package,
            sdk_version=config.sdk_version,
            state=state,
            dispatchable=dispatchable,
            target_module="executive-telegram-transport" if dispatchable else None,
            recommended_action=action,
            scores=TelegramSdkClientScores(
                secret_isolation=secret_score,
                dependency_readiness=dependency_score,
                factory_readiness=factory_score,
                runtime_safety=runtime_score,
                configuration_quality=config_score,
                client_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._client_versions.add(client_key)
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                assessment_id=record.id,
                actor_id=payload.actor_id,
                action=action,
            )
        )
        return record

    def status(self, workspace_id: str) -> TelegramSdkClientStatusResponse:
        items = self.list_assessments(workspace_id)
        return TelegramSdkClientStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            latest_state=items[-1].state if items else None,
        )

    def list_assessments(self, workspace_id: str) -> list[TelegramSdkClientAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> TelegramSdkClientAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_telegram_sdk_client_service = ExecutiveTelegramSdkClientService()
