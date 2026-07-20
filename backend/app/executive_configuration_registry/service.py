from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    ConfigurationAssessment,
    ConfigurationAssessmentCreate,
    ConfigurationState,
    ConfigurationStatusResponse,
)


class ExecutiveConfigurationRegistryService:
    def __init__(self) -> None:
        self._records: dict[UUID, ConfigurationAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._configuration_versions: set[tuple[str, str, int]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ConfigurationAssessmentCreate) -> ConfigurationAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        version_key = (payload.workspace_id, payload.configuration_key, payload.version)
        if source_key in self._source_keys:
            raise ValueError("Duplicate configuration source key")
        if version_key in self._configuration_versions:
            raise ValueError("Duplicate configuration key and version")

        o, p = payload.observation, payload.policy
        reasons: list[str] = []
        secrets_resolved = all(item.resolved and not item.expired for item in o.secret_references)
        secret_scopes_valid = all(item.scope_verified for item in o.secret_references)
        rotation_due = any(item.rotation_due for item in o.secret_references)
        schema_valid = o.schema_registered and o.schema_version_supported
        structure_valid = o.inheritance_resolved and o.feature_flags_valid and o.runtime_overrides_valid
        persisted = o.persisted and o.checksum_verified
        drifted = o.checksum_verified and not o.runtime_checksum_verified

        if not payload.risk_brain_clear:
            state, action = ConfigurationState.blocked, "block-configuration-activation"
            reasons.append("Risk Brain blocks configuration activation")
        elif p.require_policy_authorization and o.policy_state not in {"policy-approved", "ready-for-dispatch", "dry-run-only"}:
            state, action = ConfigurationState.blocked, "complete-policy-authorization"
            reasons.append("Policy Engine has not authorized configuration activation")
        elif p.prohibit_raw_secrets and o.raw_secrets_present:
            state, action = ConfigurationState.blocked, "remove-raw-configuration-secrets"
            reasons.append("Raw secrets are prohibited in configuration payloads")
        elif (p.require_registered_schema or p.require_supported_schema_version) and not schema_valid:
            state, action = ConfigurationState.schema_invalid, "register-or-upgrade-configuration-schema"
            reasons.append("Configuration schema is missing or unsupported")
        elif not structure_valid:
            state, action = ConfigurationState.configuration_required, "resolve-inheritance-flags-and-overrides"
            reasons.append("Configuration inheritance, feature flags or overrides are invalid")
        elif p.require_persistence and not persisted:
            state, action = ConfigurationState.configuration_required, "persist-and-checksum-configuration"
            reasons.append("Configuration persistence or checksum evidence is incomplete")
        elif p.require_secret_resolution and not secrets_resolved:
            state, action = ConfigurationState.secret_reference_missing, "resolve-or-rotate-secret-references"
            reasons.append("One or more secret references are unresolved or expired")
        elif p.require_secret_scope_verification and not secret_scopes_valid:
            state, action = ConfigurationState.secret_reference_missing, "verify-secret-reference-scopes"
            reasons.append("One or more secret-reference scopes are unverified")
        elif drifted:
            state, action = ConfigurationState.configuration_drift, "reconcile-runtime-configuration-drift"
            reasons.append("Runtime checksum differs from the registered configuration")
        elif rotation_due:
            state, action = ConfigurationState.reload_required, "rotate-secrets-and-reload-runtime"
            reasons.append("Secret rotation is due before runtime activation")
        elif p.require_reload_ack and not o.reload_acknowledged:
            state, action = ConfigurationState.reload_required, "reload-and-acknowledge-runtime"
            reasons.append("Runtime reload has not been acknowledged")
        elif p.require_rollback_checkpoint and not o.rollback_checkpoint_available:
            state, action = ConfigurationState.configuration_valid, "create-rollback-checkpoint"
            reasons.append("Configuration is valid but rollback evidence is unavailable")
        else:
            state, action = ConfigurationState.runtime_ready, "permit-policy-governed-runtime-use"
            reasons.append("Configuration, secret references and runtime state are valid")

        record = ConfigurationAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            configuration_id=payload.configuration_id,
            configuration_key=payload.configuration_key,
            version=payload.version,
            schema_version=payload.schema_version,
            scope=payload.scope,
            environment=payload.environment,
            target_module=payload.target_module,
            state=state,
            runtime_ready=state == ConfigurationState.runtime_ready,
            reload_required=state == ConfigurationState.reload_required,
            rollback_available=o.rollback_checkpoint_available,
            recommended_action=action,
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._configuration_versions.add(version_key)
        self._audit.append(AuditRecord(
            workspace_id=record.workspace_id,
            assessment_id=record.id,
            configuration_id=record.configuration_id,
            actor_id=record.actor_id,
            action=f"configuration-{record.state.value}",
        ))
        return record

    def get(self, record_id: UUID, workspace_id: str) -> ConfigurationAssessment | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_configurations(self, workspace_id: str) -> list[ConfigurationAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> ConfigurationStatusResponse:
        items = self.list_configurations(workspace_id)
        bad = {
            ConfigurationState.schema_invalid,
            ConfigurationState.secret_reference_missing,
            ConfigurationState.configuration_drift,
            ConfigurationState.blocked,
        }
        return ConfigurationStatusResponse(
            workspace_id=workspace_id,
            configurations=len(items),
            runtime_ready=sum(item.runtime_ready for item in items),
            drifted_or_invalid=sum(item.state in bad for item in items),
            latest_state=items[-1].state if items else None,
        )


executive_configuration_registry_service = ExecutiveConfigurationRegistryService()
