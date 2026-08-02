from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_controlled_live_transport_adapter_v21_304 import (
    _live_execution_store,
    capture_live_provider_receipt,
    TelegramLiveReceiptRequest,
)

v21_311_router = APIRouter(prefix='/auron/demo1/v21.311', tags=['auron-demo1-telegram-operational-runtime-worker'])

_worker_run_store: dict[str, dict] = {}
_EXECUTION_PHRASE = 'RUN ONE AURON TELEGRAM PROVIDER CALL'


class TelegramRuntimeWorkerRequest(BaseModel):
    execution_id: str = Field(min_length=1, max_length=160)
    actor: str = Field(min_length=1, max_length=120)
    execution_phrase: str = Field(min_length=1, max_length=160)
    timeout_seconds: int = Field(default=15, ge=1, le=60)


def reset_telegram_operational_runtime_worker_store() -> None:
    _worker_run_store.clear()


def _execution_by_id(execution_id: str) -> dict | None:
    return next((item for item in _live_execution_store.values() if item.get('execution_id') == execution_id), None)


def _runtime_enabled() -> bool:
    return os.getenv('TELEGRAM_RUNTIME_WORKER_ENABLED', '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _telegram_token() -> str | None:
    value = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    return value or None


def _provider_call(token: str, request_body: dict, timeout_seconds: int) -> tuple[int, dict]:
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    body = json.dumps(request_body, separators=(',', ':')).encode('utf-8')
    request = Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return int(response.status), json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {'ok': False, 'description': raw or str(exc)}
        return int(exc.code), payload
    except URLError as exc:
        return 503, {'ok': False, 'description': f'network error: {exc.reason}'}


def execute_runtime_worker(payload: TelegramRuntimeWorkerRequest, transport: Callable[[str, dict, int], tuple[int, dict]] | None = None) -> dict:
    if payload.execution_phrase != _EXECUTION_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram runtime-worker execution approval required')
    existing = _worker_run_store.get(payload.execution_id)
    if existing is not None:
        return {'state': 'telegram-runtime-worker-already-executed', 'run': existing, 'idempotent_replay': True}
    execution = _execution_by_id(payload.execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail='Prepared Telegram live execution not found')
    if execution.get('execution_state') != 'authorized-awaiting-runtime-worker':
        raise HTTPException(status_code=409, detail='Telegram execution is not awaiting the runtime worker')
    if not _runtime_enabled() and transport is None:
        raise HTTPException(status_code=409, detail='Telegram runtime worker is disabled')
    token = _telegram_token()
    if token is None and transport is None:
        raise HTTPException(status_code=409, detail='TELEGRAM_BOT_TOKEN is not loaded')
    call = transport or _provider_call
    started_at = datetime.now(timezone.utc).isoformat()
    http_status, provider_payload = call(token or 'test-token', execution['request_body'], payload.timeout_seconds)
    accepted = bool(provider_payload.get('ok')) and 200 <= http_status < 300
    result = provider_payload.get('result') if isinstance(provider_payload.get('result'), dict) else {}
    provider_message_id = str(result.get('message_id')) if accepted and result.get('message_id') is not None else None
    provider_error = None if accepted else str(provider_payload.get('description') or f'Telegram HTTP {http_status}')
    receipt_result = capture_live_provider_receipt(TelegramLiveReceiptRequest(execution_id=payload.execution_id, accepted=accepted, provider_message_id=provider_message_id, provider_error=provider_error, http_status=http_status))
    record = {'worker_run_id': str(uuid4()), 'execution_id': payload.execution_id, 'correlation_id': execution['correlation_id'], 'actor': payload.actor, 'http_status': http_status, 'accepted': accepted, 'provider_message_id': provider_message_id, 'provider_error': provider_error, 'provider_response_ok': bool(provider_payload.get('ok')), 'started_at': started_at, 'completed_at': datetime.now(timezone.utc).isoformat(), 'receipt_id': receipt_result['receipt']['receipt_id'], 'telegram_api_calls_made': 1, 'outbound_messages_sent': 1 if accepted else 0, 'external_calls_made': 1}
    _worker_run_store[payload.execution_id] = record
    return {'state': 'telegram-runtime-worker-call-completed', 'run': record, 'next_layer': 'telegram-live-delivery-state-commit'}


@v21_311_router.get('/status')
def runtime_worker_status() -> dict:
    return {'runtime_worker_enabled': _runtime_enabled(), 'bot_token_loaded': _telegram_token() is not None, 'worker_runs': len(_worker_run_store), 'successful_calls': sum(1 for item in _worker_run_store.values() if item['accepted']), 'failed_calls': sum(1 for item in _worker_run_store.values() if not item['accepted']), 'worker_mode': 'single-approved-live-provider-call'}


@v21_311_router.post('/execute')
def execute_runtime_worker_route(payload: TelegramRuntimeWorkerRequest) -> dict:
    return execute_runtime_worker(payload)


@v21_311_router.get('/runs')
def list_runtime_worker_runs() -> dict:
    return {'count': len(_worker_run_store), 'items': list(_worker_run_store.values())}


@v21_311_router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_live_lifecycle_closure_v21_310 import command_center as v21_310_command_center
    html = v21_310_command_center().replace('v21.310', 'v21.311')
    return html.replace('AURON TELEGRAM LIVE LIFECYCLE CLOSURE COMMAND CENTER', 'AURON TELEGRAM OPERATIONAL RUNTIME WORKER COMMAND CENTER')


from app.api.routes.auron_demo1_telegram_secure_bot_provisioning_v21_312 import router as v21_312_router
from app.api.routes.auron_demo1_telegram_end_to_end_validation_session_v21_313 import router as v21_313_router
from app.api.routes.auron_demo1_telegram_inbound_webhook_receiver_v21_314 import router as v21_314_router
from app.api.routes.auron_demo1_telegram_inbound_conversation_dispatch_v21_315 import router as v21_315_router
from app.api.routes.auron_demo1_telegram_correlated_response_delivery_admission_v21_316 import router as v21_316_router
from app.api.routes.auron_demo1_telegram_correlated_response_controlled_execution_v21_317 import router as v21_317_router

router = APIRouter()
router.include_router(v21_311_router)
router.include_router(v21_312_router)
router.include_router(v21_313_router)
router.include_router(v21_314_router)
router.include_router(v21_315_router)
router.include_router(v21_316_router)
router.include_router(v21_317_router)
