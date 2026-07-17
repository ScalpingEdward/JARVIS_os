from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .models import (
    ApprovalCreate, ApprovalRecord, ConfigEntryCreate, ConfigEntryRecord, ConfigFeatureStatus,
    ConfigState, Environment, EvaluationRequest, EvaluationResult, FeatureFlagCreate,
    FeatureFlagRecord, FlagState, MetricsRecord, Mutation,
)


class ConfigFeatureService:
    def __init__(self) -> None:
        self.flags: dict[UUID, FeatureFlagRecord] = {}
        self.configs: dict[UUID, ConfigEntryRecord] = {}
        self.approvals: list[ApprovalRecord] = []
        self.audit: list[dict] = []

    def status(self) -> ConfigFeatureStatus:
        return ConfigFeatureStatus()

    def _audit(self, workspace_id: str, action: str, actor_id: str, entity_id: UUID | None = None) -> None:
        self.audit.append({"workspace_id": workspace_id, "action": action, "actor_id": actor_id, "entity_id": str(entity_id) if entity_id else None, "created_at": datetime.now(timezone.utc)})

    def create_flag(self, payload: FeatureFlagCreate) -> FeatureFlagRecord:
        if any(x.workspace_id == payload.workspace_id and x.flag_key == payload.flag_key and x.environment == payload.environment for x in self.flags.values()):
            raise ValueError("feature flag key already exists in environment")
        item = FeatureFlagRecord(**payload.model_dump())
        self.flags[item.id] = item
        self._audit(item.workspace_id, "flag.created", item.owner_id, item.id)
        return item

    def list_flags(self, workspace_id: str, state: FlagState | None = None) -> list[FeatureFlagRecord]:
        return [x for x in self.flags.values() if x.workspace_id == workspace_id and (state is None or x.state == state)]

    def get_flag(self, flag_id: UUID, workspace_id: str) -> FeatureFlagRecord | None:
        item = self.flags.get(flag_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_flag_state(self, flag_id: UUID, workspace_id: str, payload: Mutation, target: FlagState) -> FeatureFlagRecord | None:
        item = self.get_flag(flag_id, workspace_id)
        if not item or item.owner_id != payload.requester_id:
            return None
        allowed = {
            FlagState.DRAFT: {FlagState.REVIEW, FlagState.ARCHIVED},
            FlagState.REVIEW: {FlagState.APPROVED, FlagState.DRAFT, FlagState.ARCHIVED},
            FlagState.APPROVED: {FlagState.ACTIVE, FlagState.DISABLED, FlagState.ARCHIVED},
            FlagState.ACTIVE: {FlagState.DISABLED, FlagState.ARCHIVED},
            FlagState.DISABLED: {FlagState.ACTIVE, FlagState.ARCHIVED},
            FlagState.ARCHIVED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid feature flag transition")
        if target == FlagState.APPROVED and item.approval_count < item.required_approvals:
            raise ValueError("required approvals are missing")
        if target == FlagState.ACTIVE:
            for dependency_key in item.dependency_flag_keys:
                dependency = next((x for x in self.flags.values() if x.workspace_id == workspace_id and x.environment == item.environment and x.flag_key == dependency_key), None)
                if dependency is None or dependency.state != FlagState.ACTIVE:
                    raise ValueError(f"dependency flag is not active: {dependency_key}")
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"flag.{target.value}", payload.requester_id, item.id)
        return item

    def approve_flag(self, payload: ApprovalCreate) -> ApprovalRecord:
        item = self.get_flag(payload.flag_id, payload.workspace_id)
        if item is None or item.state != FlagState.REVIEW:
            raise ValueError("feature flag is not available for review")
        if item.owner_id == payload.requester_id:
            raise ValueError("owner self-approval is blocked")
        if any(x.flag_id == payload.flag_id and x.requester_id == payload.requester_id for x in self.approvals):
            raise ValueError("reviewer already approved this flag")
        approval = ApprovalRecord(**payload.model_dump())
        self.approvals.append(approval)
        item.approval_count += 1
        self._audit(payload.workspace_id, "flag.approved-by-reviewer", payload.requester_id, item.id)
        return approval

    def evaluate(self, payload: EvaluationRequest) -> EvaluationResult:
        item = next((x for x in self.flags.values() if x.workspace_id == payload.workspace_id and x.flag_key == payload.flag_key and x.environment == payload.environment), None)
        if item is None:
            raise ValueError("feature flag not found")
        if item.state != FlagState.ACTIVE:
            return EvaluationResult(flag_key=item.flag_key, enabled=False, value=item.disabled_value, reason="flag-not-active")
        if item.expires_at and item.expires_at <= datetime.now(timezone.utc):
            return EvaluationResult(flag_key=item.flag_key, enabled=False, value=item.disabled_value, reason="flag-expired")
        if payload.subject_id in item.target_user_ids:
            return EvaluationResult(flag_key=item.flag_key, enabled=True, value=item.enabled_value, reason="explicit-target")
        bucket = int(sha256(f"{item.flag_key}:{payload.subject_id}".encode()).hexdigest()[:8], 16) % 100
        enabled = bucket < item.rollout_percentage
        return EvaluationResult(flag_key=item.flag_key, enabled=enabled, value=item.enabled_value if enabled else item.disabled_value, reason="percentage-rollout")

    def create_config(self, payload: ConfigEntryCreate) -> ConfigEntryRecord:
        previous = [x for x in self.configs.values() if x.workspace_id == payload.workspace_id and x.namespace == payload.namespace and x.key == payload.key and x.environment == payload.environment]
        version = max((x.version for x in previous), default=0) + 1
        item = ConfigEntryRecord(**payload.model_dump(), version=version)
        self.configs[item.id] = item
        self._audit(item.workspace_id, "config.created", item.owner_id, item.id)
        return item

    def list_configs(self, workspace_id: str, environment: Environment | None = None) -> list[ConfigEntryRecord]:
        return [x for x in self.configs.values() if x.workspace_id == workspace_id and (environment is None or x.environment == environment)]

    def set_config_state(self, config_id: UUID, workspace_id: str, payload: Mutation, target: ConfigState) -> ConfigEntryRecord | None:
        item = self.configs.get(config_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        allowed = {
            ConfigState.DRAFT: {ConfigState.REVIEW, ConfigState.RETIRED},
            ConfigState.REVIEW: {ConfigState.APPROVED, ConfigState.DRAFT, ConfigState.RETIRED},
            ConfigState.APPROVED: {ConfigState.ACTIVE, ConfigState.RETIRED},
            ConfigState.ACTIVE: {ConfigState.RETIRED},
            ConfigState.RETIRED: set(),
        }
        if target not in allowed[item.state]:
            raise ValueError("invalid configuration transition")
        if target == ConfigState.APPROVED and item.approval_count < item.required_approvals:
            raise ValueError("required approvals are missing")
        item.state = target
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, f"config.{target.value}", payload.requester_id, item.id)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        flags = self.list_flags(workspace_id)
        configs = self.list_configs(workspace_id)
        return MetricsRecord(workspace_id=workspace_id, flags=len(flags), active_flags=sum(x.state == FlagState.ACTIVE for x in flags), pending_review=sum(x.state == FlagState.REVIEW for x in flags), configs=len(configs), active_configs=sum(x.state == ConfigState.ACTIVE for x in configs))

    def list_audit(self, workspace_id: str) -> list[dict]:
        return [x for x in self.audit if x["workspace_id"] == workspace_id]


config_feature_service = ConfigFeatureService()
