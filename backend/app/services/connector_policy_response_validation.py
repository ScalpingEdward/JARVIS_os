from __future__ import annotations

import html
import re
from copy import deepcopy
from hashlib import sha256
from typing import Any, Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.connector_policy_response_validation import (
    ConnectorPolicyAction,
    ConnectorPolicyCreate,
    ConnectorPolicyRecord,
    ConnectorPolicyState,
    ConnectorResponseAcceptAction,
    ConnectorResponseEnvelope,
    ConnectorResponseRecord,
    ConnectorResponseState,
)


class ConnectorPolicyResponseValidationService:
    SENSITIVE_MARKERS = {"token", "secret", "password", "authorization", "api_key", "private_key", "seed_phrase"}

    def __init__(self) -> None:
        self._policies: Dict[Tuple[str, str], ConnectorPolicyRecord] = {}
        self._responses: Dict[Tuple[str, str], ConnectorResponseRecord] = {}
        self._sources: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[dict] = []

    def status(self) -> dict:
        return {
            "module": "connector-policy-response-sanitization-validation",
            "version": "21.121",
            "policy_profiles_enabled": True,
            "response_sanitization_enabled": True,
            "schema_validation_enabled": True,
            "secret_redaction_enabled": True,
            "raw_response_forwarding_enabled": False,
            "write_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create_policy(self, payload: ConnectorPolicyCreate) -> ConnectorPolicyRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._sources:
            raise ValueError("duplicate source_key for workspace")
        flags = self._policy_risk_flags(payload)
        record = ConnectorPolicyRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=ConnectorPolicyState.BLOCKED if "risk-brain-hard-block" in flags else ConnectorPolicyState.REVIEW_REQUIRED,
            profile=payload.profile, risk_flags=flags,
        )
        self._policies[(payload.workspace_id, record.record_id)] = record
        self._sources.add(source)
        self._audit_event(record.workspace_id, record.record_id, "policy-create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list_policies(self, workspace_id: str) -> List[ConnectorPolicyRecord]:
        return [record for (ws, _), record in self._policies.items() if ws == workspace_id]

    def get_policy(self, workspace_id: str, record_id: str) -> ConnectorPolicyRecord:
        try:
            return self._policies[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("policy record not found") from exc

    def act_policy(self, record_id: str, payload: ConnectorPolicyAction) -> ConnectorPolicyRecord:
        receipt = (payload.workspace_id, payload.operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get_policy(payload.workspace_id, record_id)
        transitions = {
            "approve": ConnectorPolicyState.APPROVED,
            "activate": ConnectorPolicyState.ACTIVE,
            "suspend": ConnectorPolicyState.SUSPENDED,
            "revoke": ConnectorPolicyState.REVOKED,
            "archive": ConnectorPolicyState.ARCHIVED,
        }
        if payload.action not in transitions:
            raise ValueError("unsupported action")
        if payload.action == "approve" and record.risk_flags:
            raise ValueError("unresolved policy findings block approval")
        if payload.action == "activate" and record.state != ConnectorPolicyState.APPROVED:
            raise ValueError("human approval required before activation")
        updated = record.model_copy(update={
            "state": transitions[payload.action],
            "approved_by": payload.actor if payload.action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._policies[(payload.workspace_id, record_id)] = updated
        self._operations.add(receipt)
        self._audit_event(payload.workspace_id, record_id, payload.action, payload.actor, payload.operation_id)
        return updated

    def ingest_response(self, envelope: ConnectorResponseEnvelope) -> ConnectorResponseRecord:
        receipt = (envelope.workspace_id, envelope.operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        policy = self.get_policy(envelope.workspace_id, envelope.policy_record_id)
        if policy.state != ConnectorPolicyState.ACTIVE:
            raise ValueError("active connector policy required")
        profile = policy.profile
        if envelope.connector_id != profile.connector_id:
            raise ValueError("connector identity mismatch")
        if envelope.content_type.split(";", 1)[0].strip() not in profile.allowed_content_types:
            raise ValueError("content type not allowed")
        if envelope.response_bytes > profile.max_response_bytes:
            raise ValueError("response exceeds policy size limit")

        sanitized, redacted, removed, errors = self._sanitize_and_validate(envelope.payload, profile)
        state = ConnectorResponseState.VALIDATED if not errors else ConnectorResponseState.REJECTED
        raw = f"{envelope.workspace_id}|{envelope.operation_id}|{envelope.connector_id}|{sorted(sanitized.items())}|{sorted(errors)}"
        response = ConnectorResponseRecord(
            response_id=str(uuid4()), workspace_id=envelope.workspace_id,
            policy_record_id=envelope.policy_record_id, connector_id=envelope.connector_id,
            state=state, sanitized_payload=sanitized, removed_fields=removed,
            redacted_fields=redacted, validation_errors=errors,
            receipt_digest=sha256(raw.encode()).hexdigest(),
        )
        self._responses[(envelope.workspace_id, response.response_id)] = response
        self._operations.add(receipt)
        self._audit_event(envelope.workspace_id, response.response_id, "response-ingest", envelope.connector_id, envelope.operation_id)
        return response

    def accept_response(self, response_id: str, payload: ConnectorResponseAcceptAction) -> ConnectorResponseRecord:
        receipt = (payload.workspace_id, payload.operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        response = self.get_response(payload.workspace_id, response_id)
        if response.state != ConnectorResponseState.VALIDATED:
            raise ValueError("only validated responses can be accepted")
        updated = response.model_copy(update={"state": ConnectorResponseState.ACCEPTED})
        self._responses[(payload.workspace_id, response_id)] = updated
        self._operations.add(receipt)
        self._audit_event(payload.workspace_id, response_id, "response-accept", payload.actor, payload.operation_id)
        return updated

    def get_response(self, workspace_id: str, response_id: str) -> ConnectorResponseRecord:
        try:
            return self._responses[(workspace_id, response_id)]
        except KeyError as exc:
            raise KeyError("response record not found") from exc

    def list_responses(self, workspace_id: str) -> List[ConnectorResponseRecord]:
        return [record for (ws, _), record in self._responses.items() if ws == workspace_id]

    def audit(self, workspace_id: str) -> List[dict]:
        return [event for event in self._audit if event["workspace_id"] == workspace_id]

    def _policy_risk_flags(self, payload: ConnectorPolicyCreate) -> List[str]:
        profile = payload.profile
        flags: List[str] = []
        deny_lower = {field.lower() for field in profile.deny_fields}
        redact_lower = {field.lower() for field in profile.redact_fields}
        if not self.SENSITIVE_MARKERS.intersection(deny_lower | redact_lower):
            flags.append("sensitive-field-protection-missing")
        if profile.max_response_bytes > 5_242_880:
            flags.append("large-response-review-required")
        if profile.allow_unknown_fields and profile.criticality >= 0.9:
            flags += ["critical-unknown-fields-enabled", "risk-brain-hard-block"]
        if not profile.require_schema_validation and profile.criticality >= 0.9:
            flags += ["critical-schema-validation-disabled", "risk-brain-hard-block"]
        return sorted(set(flags))

    def _sanitize_and_validate(self, payload: Dict[str, Any], profile) -> tuple[Dict[str, Any], List[str], List[str], List[str]]:
        sanitized = deepcopy(payload)
        redacted: List[str] = []
        removed: List[str] = []
        errors: List[str] = []
        deny = {field.lower() for field in profile.deny_fields}
        redact = {field.lower() for field in profile.redact_fields}
        allowed = set(profile.allowed_top_level_fields)

        for key in list(sanitized.keys()):
            lower = key.lower()
            if lower in deny:
                sanitized.pop(key, None); removed.append(key); continue
            if lower in redact:
                sanitized[key] = "[REDACTED]"; redacted.append(key); continue
            if allowed and key not in allowed and not profile.allow_unknown_fields:
                sanitized.pop(key, None); removed.append(key)

        for field in profile.required_fields:
            if field not in sanitized:
                errors.append(f"missing-required-field:{field}")

        for key, value in list(sanitized.items()):
            sanitized[key], field_errors = self._sanitize_value(value, profile, key)
            errors.extend(field_errors)

        return sanitized, sorted(redacted), sorted(removed), sorted(set(errors))

    def _sanitize_value(self, value: Any, profile, path: str) -> tuple[Any, List[str]]:
        errors: List[str] = []
        if isinstance(value, str):
            clean = re.sub(r"<[^>]+>", "", value) if profile.strip_html else value
            clean = html.unescape(clean)
            if len(clean) > profile.max_string_length:
                errors.append(f"string-too-long:{path}")
                clean = clean[:profile.max_string_length]
            return clean, errors
        if isinstance(value, list):
            if len(value) > profile.max_collection_items:
                errors.append(f"collection-too-large:{path}")
                value = value[:profile.max_collection_items]
            output = []
            for index, item in enumerate(value):
                cleaned, child_errors = self._sanitize_value(item, profile, f"{path}[{index}]")
                output.append(cleaned); errors.extend(child_errors)
            return output, errors
        if isinstance(value, dict):
            output: Dict[str, Any] = {}
            for key, item in value.items():
                lower = key.lower()
                if lower in {field.lower() for field in profile.deny_fields}:
                    continue
                if lower in {field.lower() for field in profile.redact_fields}:
                    output[key] = "[REDACTED]"; continue
                cleaned, child_errors = self._sanitize_value(item, profile, f"{path}.{key}")
                output[key] = cleaned; errors.extend(child_errors)
            return output, errors
        return value, errors

    def _audit_event(self, workspace_id: str, object_id: str, action: str, actor: str, operation_id: str) -> None:
        raw = f"{workspace_id}|{object_id}|{action}|{actor}|{operation_id}"
        self._audit.append({
            "workspace_id": workspace_id, "object_id": object_id, "action": action,
            "actor": actor, "operation_id": operation_id,
            "event_digest": sha256(raw.encode()).hexdigest(),
        })


connector_policy_response_validation_service = ConnectorPolicyResponseValidationService()
