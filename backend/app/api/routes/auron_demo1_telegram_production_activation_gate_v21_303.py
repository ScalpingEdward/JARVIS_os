from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_gateway_runtime_v21_291 import _active_runtime
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _binding_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider

router = APIRouter(prefix='/auron/demo1/v21.303', tags=['auron-demo1-telegram-production-activation-gate'])

_activation_store: dict[str, dict] = {}
_APPROVAL_PHRASE = 'ACTIVATE AURON TELEGRAM PRODUCTION'


class TelegramProductionActivationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    approval_phrase: str = Field(min_length=1, max_length=160)
    runtime_credentials_available: bool = False
    webhook_endpoint_publicly_reachable: bool = False
    tls_verified: bool = False
    operator_chat_verified: bool = False
    enable_live_transport: bool = False


def reset_telegram_production_activation_gate_store() -> None:
    _activation_store.clear()


def _readiness_checks(payload: TelegramProductionActivationRequest) -> tuple[dict, dict | None, dict | None]:
    runtime = _active_runtime()
    provider = _active_provider()
    checks = {
        'runtime_present': runtime is not None,
        'runtime_active': bool(runtime and runtime.get('active')),
        'runtime_enabled': bool(runtime and runtime.get('enabled')),
        'runtime_webhook_mode': bool(runtime and runtime.get('mode') == 'webhook'),
        'runtime_credentials_hashed': bool(runtime and runtime.get('credentials_stored_in_plaintext') is False),
        'runtime_credentials_available': payload.runtime_credentials_available,
        'provider_present': provider is not None,
        'provider_ready': bool(provider and provider.get('provider_ready')),
        'provider_runtime_matches': bool(runtime and provider and provider.get('runtime_id') == runtime.get('runtime_id')),
        'paired_operator_chat_present': any(item.get('active') for item in _binding_store.values()),
        'operator_chat_verified': payload.operator_chat_verified,
        'webhook_endpoint_publicly_reachable': payload.webhook_endpoint_publicly_reachable,
        'tls_verified': payload.tls_verified,
        'explicit_operator_approval': payload.approval_phrase == _APPROVAL_PHRASE,
    }
    return checks, runtime, provider


@router.get('/status')
def telegram_production_activation_status() -> dict:
    active = next((item for item in _activation_store.values() if item['active']), None)
    return {
        'activation_gate_records': len(_activation_store),
        'production_transport_authorized': bool(active and active['production_transport_authorized']),
        'active_activation_id': active['activation_id'] if active else None,
        'telegram_api_calls_made': 0,
        'webhook_registration_performed': False,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'gate_mode': 'operator-approved-production-readiness-gate',
    }


@router.post('/evaluate')
def evaluate_telegram_production_activation(payload: TelegramProductionActivationRequest) -> dict:
    if payload.enable_live_transport:
        raise HTTPException(status_code=409, detail='v21.303 authorizes readiness only; live Telegram transport execution is not enabled')

    checks, runtime, provider = _readiness_checks(payload)
    blockers = [name for name, passed in checks.items() if not passed]
    fingerprint = f"{runtime.get('runtime_id') if runtime else 'none'}:{provider.get('provider_id') if provider else 'none'}:{payload.actor}"
    existing = _activation_store.get(fingerprint)
    if existing is not None and existing['checks'] == checks:
        return {
            'state': 'telegram-production-activation-gate-already-evaluated',
            'activation': existing,
            'idempotent_replay': True,
            'external_calls_made': 0,
        }

    now = datetime.now(timezone.utc).isoformat()
    authorized = not blockers
    record = {
        'activation_id': str(uuid4()),
        'runtime_id': runtime.get('runtime_id') if runtime else None,
        'provider_id': provider.get('provider_id') if provider else None,
        'actor': payload.actor,
        'checks': checks,
        'blockers': blockers,
        'production_transport_authorized': authorized,
        'activation_state': 'authorized-not-executed' if authorized else 'blocked',
        'active': authorized,
        'evaluated_at': now,
        'live_transport_enabled': False,
        'telegram_api_calls_made': 0,
        'webhook_registration_performed': False,
        'outbound_messages_sent': 0,
    }
    if authorized:
        for item in _activation_store.values():
            item['active'] = False
    _activation_store[fingerprint] = record

    return {
        'state': 'telegram-production-transport-authorized' if authorized else 'telegram-production-activation-blocked',
        'activation': record,
        'telegram_api_calls_made': 0,
        'webhook_registration_performed': False,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
        'next_layer': 'telegram-controlled-live-transport-adapter' if authorized else 'telegram-production-readiness-remediation',
        'reply': 'Telegram Production Transport ist freigegeben, aber noch nicht aktiviert.' if authorized else 'Telegram Production Transport bleibt blockiert, bis alle Readiness-Pruefungen bestanden sind.',
    }


@router.get('/evaluations')
def list_activation_evaluations() -> dict:
    items = sorted(_activation_store.values(), key=lambda item: item['evaluated_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_lifecycle_closure_v21_302 import command_center as v21_302_command_center

    html = v21_302_command_center()
    html = html.replace('v21.302', 'v21.303')
    html = html.replace(
        'AURON TELEGRAM LIFECYCLE CLOSURE COMMAND CENTER',
        'AURON TELEGRAM PRODUCTION ACTIVATION GATE COMMAND CENTER',
    )
    return html
