"""Extracts a proposed account registration from free text, using a real,
bounded Anthropic call -- same pattern as
instagram_content.caption_writer.AnthropicCaptionWriter, fails closed on
a missing key or a bad response rather than guessing.

credential_guard.contains_credential_language() runs before any of this:
see propose() below -- a message that trips it is refused before the text
reaches this class's own logic, the Anthropic API, or the audit trail.

Nothing here ever registers an account on its own. propose() only ever
produces an AccountProposal for a human to look at; confirm() is the one
and only place a real TradingAccountCreate gets built and sent to
account_registry_service -- and it requires the proposal's own id back,
not a fresh guess at the fields, so there is no path from "AURON heard
something" to "an account now exists" without a human in between.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from uuid import UUID

import httpx

from app.accounts.models import AccountType, StrategyAssignmentCreate, TradingAccountCreate, TradingAccountRecord
from app.accounts.service import AccountRegistryService, account_registry_service
from app.strategies.service import STRATEGIES

from .credential_guard import CREDENTIAL_REFUSAL_MESSAGE, contains_credential_language
from .models import AccountIntakeRefusal, AccountProposal, ProposedAccountFields

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

REQUIRED_FIELDS = ("label", "broker", "login", "server", "account_type")

_EXTRACTION_PROMPT = """Extract trading account registration details from this instruction. \
Return ONLY a JSON object, no other text, with these keys:
- label: a short human-readable name for the account (invent a reasonable one if not stated, \
e.g. "{{broker}} {{account_type}}")
- broker: the broker name
- login: the account/login number, as a string
- server: the broker server name
- account_type: exactly one of "demo", "live", "prop" -- infer from context if not explicit \
(e.g. "another trading account" with no further qualifier defaults to "demo")
- currency: three-letter currency code, default "USD" if not stated
- initial_balance: a number if stated, otherwise null
- strategy_id: one of {strategy_ids} if the instruction names a strategy matching one of these, \
otherwise null

If a required field (broker, login, server) is genuinely not present in the text, use an \
empty string for it rather than guessing a value.

Instruction: {text}

Return ONLY the JSON object."""


class AccountIntakeError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountIntakeConfig:
    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    model: str = field(default_factory=lambda: os.getenv("AURON_ACCOUNT_INTAKE_MODEL", "claude-sonnet-5"))
    timeout_seconds: float = 30.0
    max_tokens: int = 400


class AccountIntakeService:
    def __init__(
        self,
        config: AccountIntakeConfig | None = None,
        client: httpx.Client | None = None,
        accounts: AccountRegistryService | None = None,
    ) -> None:
        self.config = config or AccountIntakeConfig()
        self._client = client
        self._accounts = accounts or account_registry_service
        self._proposals: dict[UUID, AccountProposal] = {}

    def propose(self, text: str, requester_id: str) -> AccountProposal | AccountIntakeRefusal:
        """The one entry point. Checks for credential language before
        anything else -- including before this method's own return value
        is logged by any caller, since a refusal never echoes the input."""
        if contains_credential_language(text):
            return AccountIntakeRefusal(reason=CREDENTIAL_REFUSAL_MESSAGE)

        fields = self._extract(text)
        missing = [f for f in REQUIRED_FIELDS if not str(getattr(fields, f, "")).strip()]
        proposal = AccountProposal(requester_id=requester_id, fields=fields, missing_fields=missing)
        self._proposals[proposal.id] = proposal
        return proposal

    def get_proposal(self, proposal_id: UUID) -> AccountProposal | None:
        return self._proposals.get(proposal_id)

    def status(self) -> dict:
        """Capability health: is extraction even possible right now."""
        return {
            "module": "account-intake",
            "api_key_configured": bool(self.config.api_key),
            "proposals_pending": sum(1 for p in self._proposals.values() if not p.confirmed),
            "proposals_confirmed": sum(1 for p in self._proposals.values() if p.confirmed),
        }

    def confirm(self, proposal_id: UUID, requester_id: str) -> TradingAccountRecord:
        """The only place a real account gets created. Requires the exact
        proposal id from propose() -- there is no way to confirm fields
        that were never actually proposed and shown back first."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise AccountIntakeError(f"No such proposal: {proposal_id}")
        if proposal.requester_id != requester_id:
            raise AccountIntakeError("Only the person who requested this proposal can confirm it")
        if proposal.confirmed:
            raise AccountIntakeError("This proposal was already confirmed -- propose a new one for another account")
        if proposal.missing_fields:
            raise AccountIntakeError(
                f"Cannot confirm -- missing required fields: {', '.join(proposal.missing_fields)}. "
                "Send the instruction again with those included."
            )
        try:
            account_type = AccountType(proposal.fields.account_type.lower())
        except ValueError as exc:
            raise AccountIntakeError(
                f"'{proposal.fields.account_type}' is not a real account type (demo/live/prop)"
            ) from exc

        record = self._accounts.register_account(TradingAccountCreate(
            label=proposal.fields.label,
            account_type=account_type,
            broker=proposal.fields.broker,
            login=proposal.fields.login,
            server=proposal.fields.server,
            currency=proposal.fields.currency,
            initial_balance=proposal.fields.initial_balance or 10_000.0,
        ))

        if proposal.fields.strategy_id and proposal.fields.strategy_id in STRATEGIES:
            strategy = STRATEGIES[proposal.fields.strategy_id]
            self._accounts.assign_strategy(record.id, StrategyAssignmentCreate(
                strategy_id=strategy["id"], strategy_name=strategy["name"],
                allocation_pct=100.0, enabled=True,
            ))

        proposal.confirmed = True
        proposal.registered_account_id = record.id
        return record

    def _extract(self, text: str) -> ProposedAccountFields:
        if not self.config.api_key:
            raise AccountIntakeError(
                "ANTHROPIC_API_KEY is not set -- AURON cannot parse a free-text account "
                "instruction without it. Set it in the backend's environment."
            )
        prompt = _EXTRACTION_PROMPT.format(
            text=text, strategy_ids=", ".join(f'"{k}"' for k in STRATEGIES),
        )
        client, should_close = (self._client, False) if self._client else (httpx.Client(), True)
        try:
            response = client.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "max_tokens": self.config.max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self.config.timeout_seconds,
            )
            if response.status_code >= 400:
                raise AccountIntakeError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")
            data = response.json()
            blocks = data.get("content", [])
            text_parts = [block["text"] for block in blocks if block.get("type") == "text"]
            raw = "".join(text_parts).strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            if not raw:
                raise AccountIntakeError("Anthropic returned an empty extraction")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise AccountIntakeError(f"Could not parse the extraction as JSON: {raw[:300]}") from exc
            return ProposedAccountFields(
                label=str(parsed.get("label") or "").strip() or "New Account",
                broker=str(parsed.get("broker") or "").strip(),
                login=str(parsed.get("login") or "").strip(),
                server=str(parsed.get("server") or "").strip(),
                account_type=str(parsed.get("account_type") or "demo").strip(),
                currency=str(parsed.get("currency") or "USD").strip(),
                initial_balance=parsed.get("initial_balance"),
                strategy_id=parsed.get("strategy_id"),
            )
        except httpx.HTTPError as exc:
            raise AccountIntakeError(f"Could not reach the Anthropic API: {exc}") from exc
        finally:
            if should_close:
                client.close()


account_intake_service = AccountIntakeService()
