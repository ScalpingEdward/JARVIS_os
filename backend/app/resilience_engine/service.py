from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    AdmissionRecord, AdmissionRequest, AuditRecord, CircuitState, Decision,
    MetricsRecord, Mutation, Outcome, OutcomeRecord, OutcomeRequest, PolicyCreate,
    PolicyRecord, PolicyState, ResilienceStatus,
)


class ResilienceService:
    def __init__(self) -> None:
        self.policies: dict[UUID, PolicyRecord] = {}
        self.admissions: dict[UUID, AdmissionRecord] = {}
        self.outcomes: dict[UUID, OutcomeRecord] = {}
        self.audit: list[AuditRecord] = []
        self.request_times: dict[tuple[UUID, str], list[datetime]] = defaultdict(list)
        self.retry_times: dict[UUID, list[datetime]] = defaultdict(list)
        self.failure_times: dict[UUID, list[datetime]] = defaultdict(list)
        self.half_open_calls: dict[UUID, int] = defaultdict(int)

    @staticmethod
    def _utc(value: datetime | None = None) -> datetime:
        value = value or datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _audit(self, workspace_id: str, action: str, entity_type: str, entity_id: UUID | None, actor_id: str, **details) -> None:
        self.audit.append(AuditRecord(
            workspace_id=workspace_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            details=details,
        ))

    @staticmethod
    def _prune(values: list[datetime], cutoff: datetime) -> None:
        values[:] = [value for value in values if value >= cutoff]

    def _refresh_circuit(self, policy: PolicyRecord, now: datetime) -> None:
        if policy.circuit_state == CircuitState.OPEN and policy.circuit_opened_at:
            if now >= policy.circuit_opened_at + timedelta(seconds=policy.open_seconds):
                policy.circuit_state = CircuitState.HALF_OPEN
                self.half_open_calls[policy.id] = 0
                policy.updated_at = now

    def status(self) -> ResilienceStatus:
        now = self._utc()
        for policy in self.policies.values():
            self._refresh_circuit(policy, now)
        return ResilienceStatus(
            policies=len(self.policies),
            admissions=len(self.admissions),
            outcomes=len(self.outcomes),
            open_circuits=sum(p.circuit_state == CircuitState.OPEN for p in self.policies.values()),
        )

    def create_policy(self, payload: PolicyCreate) -> PolicyRecord:
        if any(
            item.workspace_id == payload.workspace_id
            and item.policy_key == payload.policy_key
            and item.state != PolicyState.RETIRED
            for item in self.policies.values()
        ):
            raise ValueError("active resilience policy key already exists")
        data = payload.model_dump(exclude={
            "human_approved", "automatic_activation", "execute_request", "external_provider"
        })
        item = PolicyRecord(**data)
        self.policies[item.id] = item
        self._audit(item.workspace_id, "policy.created", "policy", item.id, item.owner_id)
        return item

    def list_policies(self, workspace_id: str) -> list[PolicyRecord]:
        now = self._utc()
        items = [item for item in self.policies.values() if item.workspace_id == workspace_id]
        for item in items:
            self._refresh_circuit(item, now)
        return items

    def get_policy(self, policy_id: UUID, workspace_id: str) -> PolicyRecord | None:
        item = self.policies.get(policy_id)
        if not item or item.workspace_id != workspace_id:
            return None
        self._refresh_circuit(item, self._utc())
        return item

    def set_policy_state(self, policy_id: UUID, workspace_id: str, payload: Mutation, state: PolicyState) -> PolicyRecord | None:
        item = self.policies.get(policy_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = self._utc()
        self._audit(workspace_id, f"policy.{state.value}", "policy", item.id, payload.requester_id, reason=payload.reason)
        return item

    def reset_circuit(self, policy_id: UUID, workspace_id: str, payload: Mutation) -> PolicyRecord | None:
        item = self.policies.get(policy_id)
        if not item or item.workspace_id != workspace_id or item.owner_id != payload.requester_id:
            return None
        item.circuit_state = CircuitState.CLOSED
        item.circuit_opened_at = None
        self.failure_times[item.id].clear()
        self.half_open_calls[item.id] = 0
        item.updated_at = self._utc()
        self._audit(workspace_id, "circuit.reset", "policy", item.id, payload.requester_id, reason=payload.reason)
        return item

    def evaluate(self, payload: AdmissionRequest) -> AdmissionRecord:
        policy = self.policies.get(payload.policy_id)
        if not policy or policy.workspace_id != payload.workspace_id or policy.state != PolicyState.ACTIVE:
            raise ValueError("active workspace resilience policy not found")
        now = self._utc(payload.evaluation_time)
        self._refresh_circuit(policy, now)
        decision = Decision.ALLOW
        reason = "admission allowed"
        retry_after = 0
        reserved = False

        if policy.circuit_state == CircuitState.OPEN:
            decision = Decision.CIRCUIT_OPEN
            reason = "circuit is open"
            if policy.circuit_opened_at:
                remaining = policy.circuit_opened_at + timedelta(seconds=policy.open_seconds) - now
                retry_after = max(1, int(remaining.total_seconds()))
        elif policy.circuit_state == CircuitState.HALF_OPEN and self.half_open_calls[policy.id] >= policy.half_open_max_calls:
            decision = Decision.CIRCUIT_OPEN
            reason = "half-open probe limit reached"
        elif policy.active_calls >= policy.bulkhead_max_concurrency:
            decision = Decision.BULKHEAD_FULL
            reason = "bulkhead concurrency is full"
        else:
            key = (policy.id, payload.subject_key)
            cutoff = now - timedelta(seconds=policy.window_seconds)
            self._prune(self.request_times[key], cutoff)
            capacity = policy.requests_per_window + policy.burst_capacity
            if len(self.request_times[key]) >= capacity:
                decision = Decision.RATE_LIMITED
                reason = "rate limit exceeded"
                oldest = min(self.request_times[key])
                retry_after = max(1, int((oldest + timedelta(seconds=policy.window_seconds) - now).total_seconds()))
            elif payload.is_retry:
                retry_cutoff = now - timedelta(seconds=policy.retry_window_seconds)
                self._prune(self.retry_times[policy.id], retry_cutoff)
                if len(self.retry_times[policy.id]) >= policy.retry_budget:
                    decision = Decision.RETRY_BUDGET_EXHAUSTED
                    reason = "retry budget exhausted"
                else:
                    self.retry_times[policy.id].append(now)

        if decision == Decision.ALLOW:
            self.request_times[(policy.id, payload.subject_key)].append(now)
            policy.active_calls += 1
            reserved = True
            if policy.circuit_state == CircuitState.HALF_OPEN:
                self.half_open_calls[policy.id] += 1
            policy.updated_at = now

        record = AdmissionRecord(
            workspace_id=payload.workspace_id,
            policy_id=policy.id,
            subject_key=payload.subject_key,
            correlation_id=payload.correlation_id,
            decision=decision,
            retry_after_seconds=retry_after,
            reason=reason,
            reserved_slot=reserved,
            evaluated_at=now,
        )
        self.admissions[record.id] = record
        self._audit(payload.workspace_id, "admission.evaluated", "admission", record.id, payload.requester_id, decision=decision.value)
        return record

    def record_outcome(self, payload: OutcomeRequest) -> OutcomeRecord:
        admission = self.admissions.get(payload.admission_id)
        if not admission or admission.workspace_id != payload.workspace_id:
            raise ValueError("workspace admission not found")
        policy = self.policies.get(admission.policy_id)
        if not policy:
            raise ValueError("resilience policy not found")
        if any(item.admission_id == admission.id for item in self.outcomes.values()):
            raise ValueError("outcome already recorded for admission")
        now = self._utc()
        if admission.reserved_slot:
            policy.active_calls = max(0, policy.active_calls - 1)
            admission.reserved_slot = False

        if payload.outcome == Outcome.SUCCESS:
            if policy.circuit_state == CircuitState.HALF_OPEN:
                policy.circuit_state = CircuitState.CLOSED
                policy.circuit_opened_at = None
                self.failure_times[policy.id].clear()
                self.half_open_calls[policy.id] = 0
        elif payload.outcome in {Outcome.FAILURE, Outcome.TIMEOUT}:
            cutoff = now - timedelta(seconds=policy.failure_window_seconds)
            self._prune(self.failure_times[policy.id], cutoff)
            self.failure_times[policy.id].append(now)
            if policy.circuit_state == CircuitState.HALF_OPEN or len(self.failure_times[policy.id]) >= policy.failure_threshold:
                policy.circuit_state = CircuitState.OPEN
                policy.circuit_opened_at = now
                self.half_open_calls[policy.id] = 0

        policy.updated_at = now
        item = OutcomeRecord(
            workspace_id=payload.workspace_id,
            policy_id=policy.id,
            admission_id=admission.id,
            outcome=payload.outcome,
            latency_ms=payload.latency_ms,
            reason=payload.reason,
            recorded_at=now,
        )
        self.outcomes[item.id] = item
        self._audit(payload.workspace_id, "outcome.recorded", "outcome", item.id, payload.requester_id, outcome=payload.outcome.value)
        return item

    def metrics(self, workspace_id: str) -> MetricsRecord:
        policies = [item for item in self.policies.values() if item.workspace_id == workspace_id]
        policy_ids = {item.id for item in policies}
        admissions = [item for item in self.admissions.values() if item.workspace_id == workspace_id]
        outcomes = [item for item in self.outcomes.values() if item.workspace_id == workspace_id]
        return MetricsRecord(
            workspace_id=workspace_id,
            policies=len(policies),
            active_policies=sum(item.state == PolicyState.ACTIVE for item in policies),
            open_circuits=sum(item.circuit_state == CircuitState.OPEN for item in policies),
            allowed=sum(item.decision == Decision.ALLOW for item in admissions),
            rate_limited=sum(item.decision == Decision.RATE_LIMITED for item in admissions),
            circuit_rejected=sum(item.decision == Decision.CIRCUIT_OPEN for item in admissions),
            bulkhead_rejected=sum(item.decision == Decision.BULKHEAD_FULL for item in admissions),
            retry_rejected=sum(item.decision == Decision.RETRY_BUDGET_EXHAUSTED for item in admissions),
            successes=sum(item.policy_id in policy_ids and item.outcome == Outcome.SUCCESS for item in outcomes),
            failures=sum(item.policy_id in policy_ids and item.outcome == Outcome.FAILURE for item in outcomes),
            timeouts=sum(item.policy_id in policy_ids and item.outcome == Outcome.TIMEOUT for item in outcomes),
        )

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]


resilience_service = ResilienceService()
