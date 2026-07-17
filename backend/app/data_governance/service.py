from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    ActionState, AuditRecord, ConsentCreate, ConsentRecord, ConsentState,
    DataAssetCreate, DataAssetRecord, GovernanceActionCreate,
    GovernanceActionRecord, GovernanceStatus, HoldState, LegalHoldCreate,
    LegalHoldRecord, Mutation, PolicyState, PrivacyRequestCreate,
    PrivacyRequestRecord, RequestState, RetentionPolicyCreate,
    RetentionPolicyRecord,
)


class DataGovernanceService:
    def __init__(self) -> None:
        self.policies: dict[UUID, RetentionPolicyRecord] = {}
        self.assets: dict[UUID, DataAssetRecord] = {}
        self.holds: dict[UUID, LegalHoldRecord] = {}
        self.consents: dict[UUID, ConsentRecord] = {}
        self.requests: dict[UUID, PrivacyRequestRecord] = {}
        self.actions: dict[UUID, GovernanceActionRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details: object) -> None:
        self.audit.append(AuditRecord(
            workspace_id=workspace_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            details=details,
        ))

    def _expire(self) -> None:
        now = datetime.now(timezone.utc)
        for consent in self.consents.values():
            if consent.state == ConsentState.GRANTED and consent.expires_at and consent.expires_at <= now:
                consent.state = ConsentState.EXPIRED
        for hold in self.holds.values():
            if hold.state == HoldState.ACTIVE and hold.expires_at and hold.expires_at <= now:
                hold.state = HoldState.RELEASED
                hold.released_at = now

    def status(self) -> GovernanceStatus:
        self._expire()
        return GovernanceStatus(
            policies=len(self.policies),
            assets=len(self.assets),
            active_holds=sum(1 for item in self.holds.values() if item.state == HoldState.ACTIVE),
            consents=len(self.consents),
            privacy_requests=len(self.requests),
            planned_actions=sum(1 for item in self.actions.values() if item.state in {ActionState.PLANNED, ActionState.APPROVED, ActionState.BLOCKED}),
        )

    def create_policy(self, payload: RetentionPolicyCreate) -> RetentionPolicyRecord:
        if any(item.workspace_id == payload.workspace_id and item.policy_key == payload.policy_key and item.state != PolicyState.RETIRED for item in self.policies.values()):
            raise ValueError("active policy key already exists")
        item = RetentionPolicyRecord(**payload.model_dump())
        self.policies[item.id] = item
        self._audit(item.workspace_id, "policy.created", "retention_policy", item.id, item.owner_id)
        return item

    def list_policies(self, workspace_id: str) -> list[RetentionPolicyRecord]:
        return [item for item in self.policies.values() if item.workspace_id == workspace_id]

    def set_policy_state(self, policy_id: UUID, workspace_id: str, payload: Mutation, state: PolicyState) -> RetentionPolicyRecord | None:
        item = self.policies.get(policy_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"policy.{state.value}", "retention_policy", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_asset(self, payload: DataAssetCreate) -> DataAssetRecord:
        if any(item.workspace_id == payload.workspace_id and item.asset_key == payload.asset_key for item in self.assets.values()):
            raise ValueError("asset key already exists")
        expires_at = None
        if payload.policy_id:
            policy = self.policies.get(payload.policy_id)
            if not policy or policy.workspace_id != payload.workspace_id or policy.state != PolicyState.ACTIVE:
                raise ValueError("active workspace policy not found")
            if policy.target_modules and payload.source_module not in policy.target_modules:
                raise ValueError("policy does not cover source module")
            if policy.data_classes and payload.data_class not in policy.data_classes:
                raise ValueError("policy does not cover data class")
            expires_at = datetime.now(timezone.utc) + timedelta(days=policy.retention_days)
        item = DataAssetRecord(**payload.model_dump(), expires_at=expires_at)
        self.assets[item.id] = item
        self._audit(item.workspace_id, "asset.registered", "data_asset", item.id, item.owner_id, data_class=item.data_class.value)
        return item

    def list_assets(self, workspace_id: str) -> list[DataAssetRecord]:
        return [item for item in self.assets.values() if item.workspace_id == workspace_id]

    def create_hold(self, payload: LegalHoldCreate) -> LegalHoldRecord:
        assets = [self.assets.get(asset_id) for asset_id in payload.asset_ids]
        if any(asset is None or asset.workspace_id != payload.workspace_id for asset in assets):
            raise ValueError("all held assets must exist in the workspace")
        if any(item.workspace_id == payload.workspace_id and item.hold_key == payload.hold_key and item.state == HoldState.ACTIVE for item in self.holds.values()):
            raise ValueError("active hold key already exists")
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
        item = LegalHoldRecord(**payload.model_dump(), expires_at=expires_at)
        self.holds[item.id] = item
        self._audit(item.workspace_id, "hold.created", "legal_hold", item.id, item.owner_id, asset_count=len(item.asset_ids))
        return item

    def list_holds(self, workspace_id: str) -> list[LegalHoldRecord]:
        self._expire()
        return [item for item in self.holds.values() if item.workspace_id == workspace_id]

    def release_hold(self, hold_id: UUID, workspace_id: str, payload: Mutation) -> LegalHoldRecord | None:
        item = self.holds.get(hold_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id or item.state != HoldState.ACTIVE:
            return None
        item.state = HoldState.RELEASED
        item.released_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "hold.released", "legal_hold", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_consent(self, payload: ConsentCreate) -> ConsentRecord:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.valid_days) if payload.valid_days else None
        item = ConsentRecord(**payload.model_dump(), expires_at=expires_at)
        self.consents[item.id] = item
        self._audit(item.workspace_id, "consent.granted", "consent", item.id, item.owner_id, purpose=item.purpose)
        return item

    def list_consents(self, workspace_id: str) -> list[ConsentRecord]:
        self._expire()
        return [item for item in self.consents.values() if item.workspace_id == workspace_id]

    def withdraw_consent(self, consent_id: UUID, workspace_id: str, payload: Mutation) -> ConsentRecord | None:
        item = self.consents.get(consent_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id or item.state != ConsentState.GRANTED:
            return None
        item.state = ConsentState.WITHDRAWN
        item.withdrawn_at = datetime.now(timezone.utc)
        self._audit(workspace_id, "consent.withdrawn", "consent", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_request(self, payload: PrivacyRequestCreate) -> PrivacyRequestRecord:
        item = PrivacyRequestRecord(**payload.model_dump())
        self.requests[item.id] = item
        self._audit(item.workspace_id, "privacy_request.created", "privacy_request", item.id, item.requester_id, request_type=item.request_type.value)
        return item

    def list_requests(self, workspace_id: str) -> list[PrivacyRequestRecord]:
        return [item for item in self.requests.values() if item.workspace_id == workspace_id]

    def decide_request(self, request_id: UUID, workspace_id: str, payload: Mutation, approve: bool) -> PrivacyRequestRecord | None:
        item = self.requests.get(request_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id or item.state != RequestState.PENDING:
            return None
        item.state = RequestState.APPROVED if approve else RequestState.REJECTED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"privacy_request.{item.state.value}", "privacy_request", item.id, payload.requester_id, reason=payload.reason)
        return item

    def create_action(self, payload: GovernanceActionCreate) -> GovernanceActionRecord:
        asset = self.assets.get(payload.asset_id)
        if not asset or asset.workspace_id != payload.workspace_id:
            raise ValueError("workspace asset not found")
        blockers: list[str] = []
        active_holds = [hold for hold in self.holds.values() if hold.workspace_id == payload.workspace_id and hold.state == HoldState.ACTIVE and payload.asset_id in hold.asset_ids]
        if active_holds and payload.action_type.value in {"delete", "anonymize"}:
            blockers.append("active_legal_hold")
        item = GovernanceActionRecord(**payload.model_dump(), blockers=blockers, state=ActionState.BLOCKED if blockers else ActionState.PLANNED)
        self.actions[item.id] = item
        self._audit(item.workspace_id, "governance_action.created", "governance_action", item.id, item.owner_id, blockers=blockers)
        return item

    def list_actions(self, workspace_id: str) -> list[GovernanceActionRecord]:
        return [item for item in self.actions.values() if item.workspace_id == workspace_id]

    def set_action_state(self, action_id: UUID, workspace_id: str, payload: Mutation, state: ActionState) -> GovernanceActionRecord | None:
        item = self.actions.get(action_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        if state == ActionState.COMPLETED and item.blockers:
            return None
        item.state = state
        if state == ActionState.COMPLETED:
            item.completed_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"governance_action.{state.value}", "governance_action", item.id, payload.requester_id, reason=payload.reason)
        return item

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


data_governance_service = DataGovernanceService()
