import secrets
from datetime import datetime, timedelta, timezone
from time import perf_counter
from urllib.parse import urlencode
from uuid import UUID

from ..connectors.models import ConnectorCreate, ConnectorState
from ..connectors.service import connector_service
from .models import (
    AuthMethod,
    ConnectionTestResult,
    OAuthCallbackRequest,
    OAuthStartRequest,
    OAuthStartResponse,
    PermissionConfirmation,
    SetupCreate,
    SetupPlatformStatus,
    SetupRecord,
    SetupState,
)


class ConnectorSetupService:
    def __init__(self) -> None:
        self._setups: dict[UUID, SetupRecord] = {}

    def reset(self) -> None:
        self._setups.clear()

    def create(self, payload: SetupCreate) -> SetupRecord:
        state = SetupState.awaiting_user
        record = SetupRecord(**payload.model_dump(), state=state)
        self._setups[record.id] = record
        return record

    def list_all(self) -> list[SetupRecord]:
        return list(self._setups.values())

    def get(self, setup_id: UUID) -> SetupRecord | None:
        return self._setups.get(setup_id)

    def confirm_permissions(self, setup_id: UUID, payload: PermissionConfirmation) -> SetupRecord | None:
        record = self.get(setup_id)
        if record is None:
            return None
        if payload.permissions != record.permissions:
            raise ValueError("Confirmed permissions must match requested permissions")
        record.permissions_confirmed = True
        record.updated_at = datetime.now(timezone.utc)
        return record

    def start_oauth(self, setup_id: UUID, payload: OAuthStartRequest) -> OAuthStartResponse | None:
        record = self.get(setup_id)
        if record is None:
            return None
        if record.auth_method != AuthMethod.oauth2:
            raise ValueError("Setup does not use OAuth2")
        if not record.permissions_confirmed:
            raise ValueError("Permissions must be confirmed first")
        state = secrets.token_urlsafe(32)
        record.oauth_state = state
        record.oauth_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        record.state = SetupState.authorizing
        record.updated_at = datetime.now(timezone.utc)
        base_url = record.metadata.get("authorization_url", "https://accounts.example.invalid/oauth/authorize")
        query = urlencode({"state": state, "redirect_uri": payload.redirect_uri, "scope": " ".join(payload.scopes)})
        return OAuthStartResponse(authorization_url=f"{base_url}?{query}", state=state)

    def complete_oauth(self, setup_id: UUID, payload: OAuthCallbackRequest) -> SetupRecord | None:
        record = self.get(setup_id)
        if record is None:
            return None
        now = datetime.now(timezone.utc)
        if record.oauth_state != payload.state:
            raise ValueError("Invalid OAuth state")
        if record.oauth_expires_at is None or record.oauth_expires_at < now:
            raise ValueError("OAuth state expired")
        # The authorization code is deliberately not persisted. A production token
        # exchange writes tokens to the external secret store and retains only refs.
        record.oauth_state = None
        record.oauth_expires_at = None
        record.state = SetupState.testing
        record.secret_refs = list(dict.fromkeys([*record.secret_refs, f"env:PHOENIX_{record.kind.value.upper()}_OAUTH_TOKEN"]))
        record.updated_at = now
        return record

    def test_connection(self, setup_id: UUID) -> SetupRecord | None:
        record = self.get(setup_id)
        if record is None:
            return None
        started = perf_counter()
        missing_requirements: list[str] = []
        if not record.permissions_confirmed:
            missing_requirements.append("permissions not confirmed")
        if record.auth_method in {AuthMethod.environment_secret, AuthMethod.oauth2} and not record.secret_refs:
            missing_requirements.append("secret reference missing")
        if record.auth_method == AuthMethod.local_path and not record.metadata.get("root_path"):
            missing_requirements.append("root_path missing")
        if record.auth_method == AuthMethod.bridge and not record.metadata.get("base_url"):
            missing_requirements.append("base_url missing")

        latency = max(1, int((perf_counter() - started) * 1000))
        if missing_requirements:
            result = ConnectionTestResult(ok=False, message=", ".join(missing_requirements), latency_ms=latency)
            record.state = SetupState.failed
            record.error = result.message
        else:
            result = ConnectionTestResult(ok=True, message="Configuration validation passed", latency_ms=latency)
            record.state = SetupState.ready
            record.error = None
        record.last_test = result
        record.updated_at = datetime.now(timezone.utc)
        return record

    def finalize(self, setup_id: UUID) -> SetupRecord | None:
        record = self.get(setup_id)
        if record is None:
            return None
        if record.state != SetupState.ready or record.last_test is None or not record.last_test.ok:
            raise ValueError("A successful connection test is required")
        connector = connector_service.create(
            ConnectorCreate(
                name=record.name,
                kind=record.kind,
                permissions=record.permissions,
                secret_refs=record.secret_refs,
                metadata=record.metadata,
            )
        )
        connector.state = ConnectorState.connecting
        record.connector_id = connector.id
        record.updated_at = datetime.now(timezone.utc)
        return record

    def status(self) -> SetupPlatformStatus:
        records = self.list_all()
        return SetupPlatformStatus(
            total=len(records),
            ready=sum(item.state == SetupState.ready for item in records),
            awaiting_user=sum(item.state in {SetupState.draft, SetupState.awaiting_user, SetupState.authorizing} for item in records),
            failed=sum(item.state == SetupState.failed for item in records),
        )


connector_setup_service = ConnectorSetupService()
