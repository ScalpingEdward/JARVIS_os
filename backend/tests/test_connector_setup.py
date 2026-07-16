import pytest

from app.connector_setup.models import (
    AuthMethod,
    OAuthCallbackRequest,
    OAuthStartRequest,
    PermissionConfirmation,
    SetupCreate,
    SetupState,
)
from app.connector_setup.service import connector_setup_service
from app.connectors.models import ConnectorKind, ConnectorPermission
from app.connectors.service import connector_service


@pytest.fixture(autouse=True)
def reset_services() -> None:
    connector_setup_service.reset()
    connector_service.reset()


def test_raw_secret_is_rejected() -> None:
    with pytest.raises(ValueError):
        SetupCreate(
            name="Telegram",
            kind=ConnectorKind.telegram,
            permissions={ConnectorPermission.read},
            auth_method=AuthMethod.environment_secret,
            secret_refs=["plain-text-token"],
        )


def test_local_path_setup_can_be_finalized() -> None:
    setup = connector_setup_service.create(
        SetupCreate(
            name="Obsidian",
            kind=ConnectorKind.obsidian,
            permissions={ConnectorPermission.read, ConnectorPermission.write},
            auth_method=AuthMethod.local_path,
            metadata={"root_path": "/vault"},
        )
    )
    connector_setup_service.confirm_permissions(
        setup.id,
        PermissionConfirmation(
            permissions={ConnectorPermission.read, ConnectorPermission.write},
            confirmed_by="human",
        ),
    )
    tested = connector_setup_service.test_connection(setup.id)
    assert tested is not None
    assert tested.state == SetupState.ready
    finalized = connector_setup_service.finalize(setup.id)
    assert finalized is not None
    assert finalized.connector_id is not None


def test_oauth_state_is_required_and_code_not_stored() -> None:
    setup = connector_setup_service.create(
        SetupCreate(
            name="Gmail",
            kind=ConnectorKind.gmail,
            permissions={ConnectorPermission.read},
            auth_method=AuthMethod.oauth2,
            metadata={"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth"},
        )
    )
    connector_setup_service.confirm_permissions(
        setup.id,
        PermissionConfirmation(permissions={ConnectorPermission.read}, confirmed_by="human"),
    )
    started = connector_setup_service.start_oauth(
        setup.id,
        OAuthStartRequest(redirect_uri="https://localhost/oauth/callback", scopes=["gmail.readonly"]),
    )
    assert started is not None
    with pytest.raises(ValueError):
        connector_setup_service.complete_oauth(setup.id, OAuthCallbackRequest(state="x" * 16, code="secret-code"))
    completed = connector_setup_service.complete_oauth(
        setup.id,
        OAuthCallbackRequest(state=started.state, code="secret-code"),
    )
    assert completed is not None
    assert completed.state == SetupState.testing
    assert all(ref.startswith("env:") for ref in completed.secret_refs)
    assert "secret-code" not in completed.model_dump_json()


def test_cannot_finalize_without_successful_test() -> None:
    setup = connector_setup_service.create(
        SetupCreate(
            name="MT5 bridge",
            kind=ConnectorKind.mt5,
            permissions={ConnectorPermission.read},
            auth_method=AuthMethod.bridge,
            metadata={},
        )
    )
    connector_setup_service.confirm_permissions(
        setup.id,
        PermissionConfirmation(permissions={ConnectorPermission.read}, confirmed_by="human"),
    )
    tested = connector_setup_service.test_connection(setup.id)
    assert tested is not None
    assert tested.state == SetupState.failed
    with pytest.raises(ValueError):
        connector_setup_service.finalize(setup.id)
