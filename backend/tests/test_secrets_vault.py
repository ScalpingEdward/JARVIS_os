from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.secrets_vault.models import (
    LeaseCreate, LeaseDecision, LeaseState, RotationPlanCreate, RotationState,
    SecretMutation, SecretReferenceCreate, SecretState,
)
from app.secrets_vault.service import SecretsVaultService


def secret_payload() -> SecretReferenceCreate:
    return SecretReferenceCreate(
        workspace_id="workspace-1", owner_id="owner-1", secret_key="openai.primary",
        provider="environment", reference="env:OPENAI_API_KEY",
        allowed_modules=["ai-connector-hub"], allowed_purposes=["model-routing"],
    )


def test_secret_reference_and_workspace_isolation():
    service = SecretsVaultService()
    secret = service.create_secret(secret_payload())
    assert secret.state == SecretState.ACTIVE
    assert service.get_secret(secret.id, "other-workspace") is None
    assert secret.reference == "env:OPENAI_API_KEY"


def test_lease_requires_allowed_module_and_purpose():
    service = SecretsVaultService()
    secret = service.create_secret(secret_payload())
    with pytest.raises(ValueError):
        service.create_lease(LeaseCreate(
            workspace_id="workspace-1", owner_id="owner-1", requester_id="agent-1",
            secret_id=secret.id, source_module="desktop-intelligence", purpose="model-routing",
        ))
    lease = service.create_lease(LeaseCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="agent-1",
        secret_id=secret.id, source_module="ai-connector-hub", purpose="model-routing",
    ))
    assert lease.state == LeaseState.PENDING


def test_owner_approval_issues_reference_not_value():
    service = SecretsVaultService()
    secret = service.create_secret(secret_payload())
    lease = service.create_lease(LeaseCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="agent-1",
        secret_id=secret.id, source_module="ai-connector-hub", purpose="model-routing",
    ))
    assert service.decide_lease(lease.id, "workspace-1", LeaseDecision(requester_id="wrong-owner", approved=True)) is None
    approved = service.decide_lease(lease.id, "workspace-1", LeaseDecision(requester_id="owner-1", approved=True))
    assert approved is not None and approved.state == LeaseState.ACTIVE
    assert approved.issued_reference == "env:OPENAI_API_KEY"


def test_secret_revocation_revokes_active_leases():
    service = SecretsVaultService()
    secret = service.create_secret(secret_payload())
    lease = service.create_lease(LeaseCreate(
        workspace_id="workspace-1", owner_id="owner-1", requester_id="agent-1",
        secret_id=secret.id, source_module="ai-connector-hub", purpose="model-routing",
    ))
    service.decide_lease(lease.id, "workspace-1", LeaseDecision(requester_id="owner-1", approved=True))
    revoked = service.set_secret_state(secret.id, "workspace-1", SecretMutation(requester_id="owner-1"), SecretState.REVOKED)
    assert revoked is not None and revoked.state == SecretState.REVOKED
    assert service.leases[lease.id].state == LeaseState.REVOKED


def test_rotation_is_planning_only_and_refreshes_due_date():
    service = SecretsVaultService()
    secret = service.create_secret(secret_payload())
    old_due = secret.next_rotation_at
    plan = service.create_rotation(RotationPlanCreate(
        workspace_id="workspace-1", owner_id="owner-1", secret_id=secret.id,
        reason="scheduled rotation", scheduled_for=datetime.now(timezone.utc) + timedelta(days=1),
    ))
    approved = service.set_rotation_state(plan.id, "workspace-1", SecretMutation(requester_id="owner-1"), RotationState.APPROVED)
    assert approved is not None and approved.state == RotationState.APPROVED
    completed = service.set_rotation_state(plan.id, "workspace-1", SecretMutation(requester_id="owner-1"), RotationState.COMPLETED)
    assert completed is not None and completed.state == RotationState.COMPLETED
    assert service.secrets[secret.id].next_rotation_at >= old_due


def test_safety_rejects_plaintext_export_sync_and_automatic_behaviour():
    base = secret_payload().model_dump()
    with pytest.raises(ValidationError):
        SecretReferenceCreate.model_validate({**base, "plaintext_value": "secret"})
    with pytest.raises(ValidationError):
        SecretReferenceCreate.model_validate({**base, "export_secret": True})
    with pytest.raises(ValidationError):
        SecretReferenceCreate.model_validate({**base, "automatic_external_sync": True})
    with pytest.raises(ValidationError):
        LeaseCreate(
            workspace_id="workspace-1", owner_id="owner-1", requester_id="agent-1",
            secret_id="00000000-0000-0000-0000-000000000001", source_module="ai-connector-hub",
            purpose="model-routing", reveal_value=True,
        )
    with pytest.raises(ValidationError):
        RotationPlanCreate(
            workspace_id="workspace-1", owner_id="owner-1",
            secret_id="00000000-0000-0000-0000-000000000001", reason="rotate",
            scheduled_for=datetime.now(timezone.utc), rotate_automatically=True,
        )


def test_status_safe_defaults():
    status = SecretsVaultService().status()
    assert status.version == "9.2"
    assert status.plaintext_storage_enabled is False
    assert status.secret_export_enabled is False
    assert status.automatic_rotation_enabled is False
    assert status.automatic_lease_renewal_enabled is False
