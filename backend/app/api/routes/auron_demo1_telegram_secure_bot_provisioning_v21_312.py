from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix='/auron/demo1/v21.312', tags=['auron-demo1-telegram-secure-bot-provisioning'])

_validation_store: dict[str, dict] = {}
_TOKEN_PATTERN = re.compile(r'^(?P<bot_id>\d{5,20}):(?P<secret>[A-Za-z0-9_-]{30,80})$')


class TelegramBotProvisioningValidationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    expected_bot_id: str | None = Field(default=None, pattern=r'^\d{5,20}$')
    require_worker_enabled: bool = True


def reset_telegram_secure_bot_provisioning_store() -> None:
    _validation_store.clear()


def _enabled() -> bool:
    return os.getenv('TELEGRAM_RUNTIME_WORKER_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _token() -> str | None:
    value = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    return value or None


def _fingerprint(token: str) -> str:
    return sha256(token.encode('utf-8')).hexdigest()[:16]


@router.get('/status')
def provisioning_status() -> dict:
    return {
        'validations': len(_validation_store),
        'runtime_worker_enabled': _enabled(),
        'bot_token_loaded': _token() is not None,
        'bot_token_persisted': False,
        'secret_source': 'environment-only',
        'external_calls_made': 0,
    }


@router.post('/validate')
def validate_provisioning(payload: TelegramBotProvisioningValidationRequest) -> dict:
    token = _token()
    match = _TOKEN_PATTERN.match(token or '')
    bot_id = match.group('bot_id') if match else None
    checks = {
        'token_loaded': token is not None,
        'token_format_valid': match is not None,
        'worker_enabled': _enabled() if payload.require_worker_enabled else True,
        'expected_bot_id_matches': payload.expected_bot_id is None or bot_id == payload.expected_bot_id,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        return {
            'state': 'telegram-bot-provisioning-blocked',
            'checks': checks,
            'blockers': blockers,
            'bot_token_persisted': False,
            'external_calls_made': 0,
            'next_layer': 'telegram-runtime-secret-remediation',
        }

    fingerprint = _fingerprint(token or '')
    existing = _validation_store.get(fingerprint)
    if existing is not None:
        return {'state': 'telegram-bot-provisioning-already-validated', 'validation': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    record = {
        'token_fingerprint': fingerprint,
        'bot_id': bot_id,
        'runtime_worker_enabled': _enabled(),
        'validated_by': payload.actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
        'checks': checks,
        'runtime_ready': True,
        'bot_token_persisted': False,
        'secret_source': 'environment-only',
    }
    _validation_store[fingerprint] = record
    return {
        'state': 'telegram-bot-provisioning-validated',
        'validation': record,
        'external_calls_made': 0,
        'next_layer': 'telegram-end-to-end-validation-session',
    }


@router.get('/validations')
def list_validations() -> dict:
    return {'count': len(_validation_store), 'items': list(_validation_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_operational_runtime_worker_v21_311 import command_center as v21_311_command_center
    html = v21_311_command_center().replace('v21.311', 'v21.312')
    return html.replace('AURON TELEGRAM OPERATIONAL RUNTIME WORKER COMMAND CENTER', 'AURON TELEGRAM SECURE BOT PROVISIONING COMMAND CENTER')
