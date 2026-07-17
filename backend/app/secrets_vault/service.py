from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AuditRecord,
    LeaseCreate,
    LeaseDecision,
    LeaseRecord,
    LeaseState,
    RotationPlanCreate,
    RotationPlanRecord,
    RotationState,
    SecretMutation,
    SecretReferenceCreate,
    SecretReferenceRecord,
    SecretState,
    VaultStatus,
)


class SecretsVaultService:
    def __init__(self) -> None:
        self.secrets: dict[UUID, SecretReferenceRecord] = {}
        self.leases: dict[UUID, LeaseRecord] = {}
        self.rotations: dict[UUID, RotationPlanRecord] = {}
        self.audit: list[AuditRecord] = []

    def status(self) -> VaultStatus:
        self._expire()
        return VaultStatus(
            active_secrets=sum(x.state == SecretState.ACTIVE for x in self.secrets.values()),
            active_leases=sum(x.state == LeaseState.ACTIVE for x in self.leases.values()),
            rotation_plans=len(self.rotations),
        )

    def _log(self, workspace_id: str, action: str, actor_id: str, subject_id: UUID, **details: object) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, action=action, actor_id=actor_id, subject_id=str(subject_id), details=details))

    def create_secret(self, payload: SecretReferenceCreate) -> SecretReferenceRecord:
        if any(x.workspace_id == payload.workspace_id and x.secret_key == payload.secret_key for x in self.secrets.values()):
            raise ValueError("secret key already exists in workspace")
        now = datetime.now(timezone.utc)
        item = SecretReferenceRecord(
            **payload.model_dump(exclude={"plaintext_value", "export_secret", "automatic_external_sync", "human_approved"}),
            next_rotation_at=now + timedelta(days=payload.rotation_interval_days),
        )
        self.secrets[item.id] = item
        self._log(item.workspace_id, "secret.created", item.owner_id, item.id, provider=item.provider)
        return item

    def list_secrets(self, workspace_id: str) -> list[SecretReferenceRecord]:
        self._expire()
        return [x for x in self.secrets.values() if x.workspace_id == workspace_id]

    def get_secret(self, secret_id: UUID, workspace_id: str) -> SecretReferenceRecord | None:
        self._expire()
        item = self.secrets.get(secret_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_secret_state(self, secret_id: UUID, workspace_id: str, payload: SecretMutation, state: SecretState) -> SecretReferenceRecord | None:
        item = self.get_secret(secret_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._log(workspace_id, f"secret.{state.value}", payload.requester_id, item.id, reason=payload.reason)
        if state == SecretState.REVOKED:
            for lease in self.leases.values():
                if lease.secret_id == item.id and lease.state in {LeaseState.PENDING, LeaseState.ACTIVE}:
                    lease.state = LeaseState.REVOKED
                    lease.revoked_at = datetime.now(timezone.utc)
        return item

    def create_lease(self, payload: LeaseCreate) -> LeaseRecord:
        secret = self.get_secret(payload.secret_id, payload.workspace_id)
        if not secret or secret.state != SecretState.ACTIVE:
            raise ValueError("active secret reference not found")
        if secret.allowed_modules and payload.source_module not in secret.allowed_modules:
            raise ValueError("module is not allowed to request this secret")
        if secret.allowed_purposes and payload.purpose not in secret.allowed_purposes:
            raise ValueError("purpose is not allowed for this secret")
        item = LeaseRecord(
            **payload.model_dump(exclude={"human_approved", "reveal_value", "auto_renew", "execute_external_action", "ttl_minutes"}),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.ttl_minutes),
        )
        self.leases[item.id] = item
        self._log(item.workspace_id, "lease.requested", item.requester_id, item.id, secret_id=str(item.secret_id))
        return item

    def list_leases(self, workspace_id: str) -> list[LeaseRecord]:
        self._expire()
        return [x for x in self.leases.values() if x.workspace_id == workspace_id]

    def decide_lease(self, lease_id: UUID, workspace_id: str, payload: LeaseDecision) -> LeaseRecord | None:
        self._expire()
        item = self.leases.get(lease_id)
        if not item or item.workspace_id != workspace_id or item.state != LeaseState.PENDING:
            return None
        secret = self.secrets.get(item.secret_id)
        if not secret or secret.owner_id != payload.requester_id:
            return None
        if payload.approved:
            item.state = LeaseState.ACTIVE
            item.approved_by = payload.requester_id
            item.issued_reference = secret.reference
            action = "lease.approved"
        else:
            item.state = LeaseState.REJECTED
            action = "lease.rejected"
        self._log(workspace_id, action, payload.requester_id, item.id, reason=payload.reason)
        return item

    def revoke_lease(self, lease_id: UUID, workspace_id: str, payload: SecretMutation) -> LeaseRecord | None:
        item = self.leases.get(lease_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if item.state not in {LeaseState.PENDING, LeaseState.ACTIVE}:
            return None
        item.state = LeaseState.REVOKED
        item.revoked_at = datetime.now(timezone.utc)
        self._log(workspace_id, "lease.revoked", payload.requester_id, item.id, reason=payload.reason)
        return item

    def create_rotation(self, payload: RotationPlanCreate) -> RotationPlanRecord:
        secret = self.get_secret(payload.secret_id, payload.workspace_id)
        if not secret or secret.owner_id != payload.owner_id:
            raise ValueError("owned secret reference not found")
        item = RotationPlanRecord(**payload.model_dump(exclude={"human_approved", "rotate_automatically"}))
        self.rotations[item.id] = item
        self._log(item.workspace_id, "rotation.planned", item.owner_id, item.id, secret_id=str(item.secret_id))
        return item

    def list_rotations(self, workspace_id: str) -> list[RotationPlanRecord]:
        return [x for x in self.rotations.values() if x.workspace_id == workspace_id]

    def set_rotation_state(self, rotation_id: UUID, workspace_id: str, payload: SecretMutation, state: RotationState) -> RotationPlanRecord | None:
        item = self.rotations.get(rotation_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        if state == RotationState.APPROVED:
            item.approved_by = payload.requester_id
        if state == RotationState.COMPLETED:
            item.completed_by = payload.requester_id
            secret = self.secrets.get(item.secret_id)
            if secret:
                now = datetime.now(timezone.utc)
                secret.last_rotated_at = now
                secret.next_rotation_at = now + timedelta(days=secret.rotation_interval_days)
                secret.state = SecretState.ACTIVE
        self._log(workspace_id, f"rotation.{state.value}", payload.requester_id, item.id, reason=payload.reason)
        return item

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [x for x in self.audit if x.workspace_id == workspace_id]

    def _expire(self) -> None:
        now = datetime.now(timezone.utc)
        for secret in self.secrets.values():
            if secret.state == SecretState.ACTIVE and secret.next_rotation_at <= now:
                secret.state = SecretState.ROTATION_DUE
        for lease in self.leases.values():
            if lease.state in {LeaseState.PENDING, LeaseState.ACTIVE} and lease.expires_at <= now:
                lease.state = LeaseState.EXPIRED
                lease.issued_reference = None


secrets_vault_service = SecretsVaultService()
