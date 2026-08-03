from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_gateway_runtime_v21_291 import _active_runtime
from app.api.routes.auron_demo1_telegram_mobile_conversation_bridge_v21_290 import _binding_store
from app.api.routes.auron_demo1_telegram_provider_registration_v21_292 import _active_provider
from app.api.routes.auron_demo1_telegram_production_activation_gate_v21_303 import _activation_store
from app.api.routes.auron_demo1_telegram_secure_bot_provisioning_v21_312 import _validation_store
from app.api.routes.auron_demo1_telegram_inbound_lifecycle_closure_audit_v21_319 import _closure_audit_store

router = APIRouter(prefix='/auron/demo1/v21.320', tags=['auron-demo1-telegram-operational-readiness-observability'])

_readiness_store: dict[str, dict] = {}
_validation_run_store: dict[str, dict] = {}
_VALIDATION_PHRASE = 'START ONE AURON TELEGRAM PHONE VALIDATION RUN'


class TelegramOperationalReadinessRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    public_webhook_reachable: bool = False
    tls_verified: bool = False
    runtime_network_egress_available: bool = False


class TelegramPhoneValidationRunRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    telegram_chat_id: str = Field(min_length=1, max_length=120)
    validation_phrase: str = Field(min_length=1, max_length=200)
    test_message: str = Field(min_length=1, max_length=500)
    execute_external_actions: bool = False


def reset_telegram_operational_readiness_observability_store() -> None:
    _readiness_store.clear()
    _validation_run_store.clear()


def _active_activation() -> dict | None:
    return next((item for item in _activation_store.values() if item.get('active') and item.get('production_transport_authorized')), None)


def _active_provisioning() -> dict | None:
    return next((item for item in _validation_store.values() if item.get('runtime_ready')), None)


def evaluate_operational_readiness(payload: TelegramOperationalReadinessRequest) -> dict:
    runtime = _active_runtime()
    provider = _active_provider()
    activation = _active_activation()
    provisioning = _active_provisioning()
    active_bindings = [item for item in _binding_store.values() if item.get('active')]
    checks = {
        'runtime_present': runtime is not None,
        'runtime_enabled': bool(runtime and runtime.get('enabled')),
        'runtime_webhook_mode': bool(runtime and runtime.get('mode') == 'webhook'),
        'provider_present': provider is not None,
        'provider_ready': bool(provider and provider.get('provider_ready')),
        'provider_runtime_matches': bool(runtime and provider and provider.get('runtime_id') == runtime.get('runtime_id')),
        'production_activation_present': activation is not None,
        'activation_provider_matches': bool(activation and provider and activation.get('provider_id') == provider.get('provider_id')),
        'activation_runtime_matches': bool(activation and runtime and activation.get('runtime_id') == runtime.get('runtime_id')),
        'bot_provisioning_validated': provisioning is not None,
        'runtime_worker_enabled': os.getenv('TELEGRAM_RUNTIME_WORKER_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'},
        'bot_token_loaded': bool(os.getenv('TELEGRAM_BOT_TOKEN', '').strip()),
        'webhook_secret_loaded': bool(os.getenv('TELEGRAM_WEBHOOK_SECRET', '').strip()),
        'paired_operator_chat_present': bool(active_bindings),
        'public_webhook_reachable': payload.public_webhook_reachable,
        'tls_verified': payload.tls_verified,
        'runtime_network_egress_available': payload.runtime_network_egress_available,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    fingerprint = ':'.join([
        str(runtime.get('runtime_id') if runtime else 'none'),
        str(provider.get('provider_id') if provider else 'none'),
        str(activation.get('activation_id') if activation else 'none'),
        payload.actor,
    ])
    existing = _readiness_store.get(fingerprint)
    if existing is not None and existing['checks'] == checks:
        return {'state': 'telegram-operational-readiness-already-evaluated', 'readiness': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    record = {
        'readiness_id': str(uuid4()),
        'runtime_id': runtime.get('runtime_id') if runtime else None,
        'provider_id': provider.get('provider_id') if provider else None,
        'activation_id': activation.get('activation_id') if activation else None,
        'bot_id': provisioning.get('bot_id') if provisioning else None,
        'active_binding_count': len(active_bindings),
        'checks': checks,
        'blockers': blockers,
        'operationally_ready': not blockers,
        'readiness_state': 'ready-for-controlled-phone-validation' if not blockers else 'blocked',
        'evaluated_by': payload.actor,
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'closed_lifecycles_observed': len(_closure_audit_store),
        'external_calls_made': 0,
    }
    _readiness_store[fingerprint] = record
    return {
        'state': 'telegram-operationally-ready' if not blockers else 'telegram-operational-readiness-blocked',
        'readiness': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-controlled-phone-validation-run' if not blockers else 'telegram-operational-readiness-remediation',
    }


@router.post('/evaluate')
def evaluate_operational_readiness_route(payload: TelegramOperationalReadinessRequest) -> dict:
    return evaluate_operational_readiness(payload)


@router.post('/phone-validation/start')
def start_phone_validation_run(payload: TelegramPhoneValidationRunRequest) -> dict:
    if payload.execute_external_actions:
        raise HTTPException(status_code=409, detail='v21.320 prepares the controlled phone validation run only; it does not perform external actions')
    if payload.validation_phrase != _VALIDATION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit phone-validation approval required')
    binding = _binding_store.get(payload.telegram_chat_id)
    if binding is None or not binding.get('active'):
        raise HTTPException(status_code=403, detail='Active Telegram operator/chat binding required')
    readiness = next((item for item in reversed(list(_readiness_store.values())) if item.get('operationally_ready')), None)
    if readiness is None:
        raise HTTPException(status_code=409, detail='Successful Telegram operational-readiness evaluation required')

    existing = _validation_run_store.get(payload.telegram_chat_id)
    if existing is not None and existing.get('run_state') == 'prepared-awaiting-phone-message':
        return {'state': 'telegram-phone-validation-run-already-prepared', 'validation_run': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    record = {
        'validation_run_id': str(uuid4()),
        'readiness_id': readiness['readiness_id'],
        'telegram_chat_id': payload.telegram_chat_id,
        'telegram_user_id': binding.get('telegram_user_id'),
        'operator_id': binding.get('operator_id'),
        'workspace_id': binding.get('workspace_id'),
        'test_message': payload.test_message,
        'expected_flow': ['phone-inbound', 'webhook-secret-verified', 'conversation-dispatched', 'response-admitted', 'execution-prepared', 'runtime-worker-called', 'result-correlated', 'lifecycle-closed'],
        'run_state': 'prepared-awaiting-phone-message',
        'prepared_by': payload.actor,
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'telegram_api_calls_made': 0,
        'outbound_messages_sent': 0,
        'external_calls_made': 0,
    }
    _validation_run_store[payload.telegram_chat_id] = record
    return {
        'state': 'telegram-phone-validation-run-prepared',
        'validation_run': record,
        'external_calls_made': 0,
        'next_layer': 'operator-sends-test-message-from-phone',
    }


@router.get('/status')
def operational_status() -> dict:
    latest = list(_readiness_store.values())[-1] if _readiness_store else None
    return {
        'readiness_evaluations': len(_readiness_store),
        'operationally_ready': bool(latest and latest.get('operationally_ready')),
        'active_blockers': latest.get('blockers', []) if latest else ['readiness-not-evaluated'],
        'phone_validation_runs': len(_validation_run_store),
        'prepared_phone_runs': sum(1 for item in _validation_run_store.values() if item.get('run_state') == 'prepared-awaiting-phone-message'),
        'closed_lifecycles_observed': len(_closure_audit_store),
        'external_calls_made': 0,
        'observability_mode': 'readiness-and-controlled-phone-validation-preflight',
    }


@router.get('/readiness')
def list_readiness_evaluations() -> dict:
    items = sorted(_readiness_store.values(), key=lambda item: item['evaluated_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/phone-validation/runs')
def list_phone_validation_runs() -> dict:
    items = sorted(_validation_run_store.values(), key=lambda item: item['prepared_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_inbound_lifecycle_closure_audit_v21_319 import command_center as v21_319_command_center
    html = v21_319_command_center().replace('v21.319', 'v21.320')
    return html.replace('AURON TELEGRAM INBOUND LIFECYCLE CLOSURE AUDIT COMMAND CENTER', 'AURON TELEGRAM OPERATIONAL READINESS OBSERVABILITY COMMAND CENTER')
