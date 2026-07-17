import pytest
from pydantic import ValidationError

from app.identity_access.models import (
    AccessCheckRequest, DelegationCreate, IdentityCreate, IdentityMutation,
    IdentityType, Permission, RoleAssignmentCreate, RoleCreate,
)
from app.identity_access.service import IdentityAccessService


def identity_payload(key: str, owner: str = "owner-1", workspace: str = "workspace-1") -> IdentityCreate:
    return IdentityCreate(
        workspace_id=workspace,
        owner_id=owner,
        identity_key=key,
        display_name=key.title(),
        identity_type=IdentityType.HUMAN,
    )


def role_payload() -> RoleCreate:
    return RoleCreate(
        workspace_id="workspace-1",
        owner_id="owner-1",
        role_key="task-operator",
        name="Task Operator",
        permissions=[Permission(resource="task-engine", actions=["start", "pause"])],
        maximum_risk="medium",
    )


def test_role_assignment_and_access_check():
    service = IdentityAccessService()
    identity = service.create_identity(identity_payload("operator-1"))
    role = service.create_role(role_payload())
    service.create_assignment(RoleAssignmentCreate(
        workspace_id="workspace-1", owner_id="owner-1",
        identity_id=identity.id, role_id=role.id, valid_minutes=60,
    ))
    allowed = service.check_access(AccessCheckRequest(
        workspace_id="workspace-1", identity_id=identity.id,
        resource="task-engine", action="start",
    ))
    denied = service.check_access(AccessCheckRequest(
        workspace_id="workspace-1", identity_id=identity.id,
        resource="task-engine", action="delete",
    ))
    assert allowed.allowed is True
    assert role.id in allowed.matched_role_ids
    assert denied.allowed is False


def test_delegation_requires_role_and_acceptance():
    service = IdentityAccessService()
    delegator = service.create_identity(identity_payload("delegator"))
    delegate = service.create_identity(identity_payload("delegate"))
    role = service.create_role(role_payload())
    service.create_assignment(RoleAssignmentCreate(
        workspace_id="workspace-1", owner_id="owner-1",
        identity_id=delegator.id, role_id=role.id,
    ))
    delegation = service.create_delegation(DelegationCreate(
        workspace_id="workspace-1", owner_id="owner-1",
        delegator_identity_id=delegator.id,
        delegate_identity_id=delegate.id,
        role_id=role.id,
        reason="temporary coverage",
    ))
    assert delegation.state.value == "pending"
    accepted = service.accept_delegation(
        delegation.id, "workspace-1", IdentityMutation(requester_id="owner-1")
    )
    assert accepted is not None
    assert accepted.state.value == "active"
    decision = service.check_access(AccessCheckRequest(
        workspace_id="workspace-1", identity_id=delegate.id,
        resource="task-engine", action="pause",
    ))
    assert decision.allowed is True


def test_delegator_must_hold_role():
    service = IdentityAccessService()
    delegator = service.create_identity(identity_payload("delegator"))
    delegate = service.create_identity(identity_payload("delegate"))
    role = service.create_role(role_payload())
    with pytest.raises(ValueError):
        service.create_delegation(DelegationCreate(
            workspace_id="workspace-1", owner_id="owner-1",
            delegator_identity_id=delegator.id,
            delegate_identity_id=delegate.id,
            role_id=role.id,
            reason="invalid delegation",
        ))


def test_workspace_and_owner_isolation():
    service = IdentityAccessService()
    identity = service.create_identity(identity_payload("operator-1"))
    assert service.get_identity(identity.id, "other-workspace") is None
    assert service.set_identity_state(
        identity.id, "workspace-1", IdentityMutation(requester_id="wrong-owner"),
        identity.state,
    ) is None


def test_least_privilege_and_safety_rejections():
    with pytest.raises(ValidationError):
        RoleCreate(
            workspace_id="workspace-1", owner_id="owner-1",
            role_key="admin", name="Admin",
            permissions=[Permission(resource="*", actions=["*"])],
        )
    with pytest.raises(ValidationError):
        IdentityCreate(
            workspace_id="workspace-1", owner_id="owner-1",
            identity_key="external", display_name="External",
            identity_type=IdentityType.SERVICE,
            external_identity_sync=True,
        )
    with pytest.raises(ValidationError):
        AccessCheckRequest(
            workspace_id="workspace-1",
            identity_id="00000000-0000-0000-0000-000000000001",
            resource="task-engine", action="start", execute_action=True,
        )


def test_status_safe_defaults():
    status = IdentityAccessService().status()
    assert status.version == "9.1"
    assert status.credential_capture_enabled is False
    assert status.external_identity_sync_enabled is False
    assert status.wildcard_permissions_enabled is False
    assert status.delegation_chaining_enabled is False
    assert status.access_checks_execute_actions is False
    assert status.least_privilege_enforced is True
