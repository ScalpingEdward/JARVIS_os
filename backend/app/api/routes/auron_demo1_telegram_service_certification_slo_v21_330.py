from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_continuous_queue_orchestration_v21_324 import _queue_item_store
from app.api.routes.auron_demo1_telegram_lifecycle_progression_worker_v21_325 import _dead_letter_store, _progression_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_restoration_probation_v21_329 import _probation_store

router = APIRouter(prefix='/auron/demo1/v21.330', tags=['auron-demo1-telegram-service-certification-slo'])

_certificate_store: dict[str, dict] = {}
_CERTIFY_PHRASE = 'CERTIFY AURON TELEGRAM SERVICE'


class TelegramServiceCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    probation_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=220)
    minimum_reliability_score: float = Field(default=85.0, ge=0.0, le=100.0)


def reset_telegram_service_certification_slo_store() -> None:
    _certificate_store.clear()


def _probation_by_id(probation_id: str) -> dict | None:
    return next((item for item in _probation_store.values() if item.get('probation_id') == probation_id), None)


def _chat_items(store: dict[str, dict], chat_id: str) -> list[dict]:
    return [item for item in store.values() if str(item.get('telegram_chat_id')) == str(chat_id)]


def _baseline_metrics(chat_id: str) -> dict:
    from app.api.routes.auron_demo1_telegram_operational_runtime_worker_v21_311 import _worker_run_store

    worker_runs = [item for item in _worker_run_store.values() if str(item.get('telegram_chat_id') or item.get('chat_id') or '') == str(chat_id)]
    progressions = _chat_items(_progression_store, chat_id)
    queue_items = _chat_items(_queue_item_store, chat_id)
    dead_letters = _chat_items(_dead_letter_store, chat_id)
    successful_worker_calls = sum(1 for item in worker_runs if item.get('accepted'))
    completed_progressions = sum(1 for item in progressions if item.get('progression_state') == 'completed')
    delivery_success_rate = successful_worker_calls / len(worker_runs) if worker_runs else 1.0
    lifecycle_completion_rate = completed_progressions / len(progressions) if progressions else 1.0
    dead_letter_rate = len(dead_letters) / len(progressions) if progressions else 0.0
    queue_completion_rate = sum(1 for item in queue_items if item.get('queue_state') == 'completed') / len(queue_items) if queue_items else 1.0
    reliability_score = round(max(0.0, min(100.0, (
        delivery_success_rate * 40.0
        + lifecycle_completion_rate * 30.0
        + queue_completion_rate * 20.0
        + (1.0 - min(dead_letter_rate, 1.0)) * 10.0
    ))), 2)
    return {
        'worker_runs': len(worker_runs),
        'successful_worker_calls': successful_worker_calls,
        'delivery_success_rate': round(delivery_success_rate, 6),
        'progressions': len(progressions),
        'completed_progressions': completed_progressions,
        'lifecycle_completion_rate': round(lifecycle_completion_rate, 6),
        'queue_items': len(queue_items),
        'queue_completion_rate': round(queue_completion_rate, 6),
        'dead_letters': len(dead_letters),
        'dead_letter_rate': round(dead_letter_rate, 6),
        'runtime_reliability_score': reliability_score,
    }


def _integrity_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@router.post('/certify')
def certify_telegram_service(payload: TelegramServiceCertificationRequest) -> dict:
    if payload.certification_phrase != _CERTIFY_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit Telegram service certification approval required')
    existing = _certificate_store.get(payload.probation_id)
    if existing is not None:
        return {'state': 'telegram-service-already-certified', 'certificate': existing, 'idempotent_replay': True, 'external_calls_made': 0}

    probation = _probation_by_id(payload.probation_id)
    if probation is None:
        raise HTTPException(status_code=404, detail='Telegram restoration probation not found')
    chat_id = probation['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    checks = {
        'probation_completed_stable': probation.get('probation_state') == 'completed-stable',
        'service_active': bool(go_live and go_live.get('continuous_mode_active')),
        'safety_circuit_closed': _circuit_store.get(chat_id, {}).get('state', 'closed') == 'closed',
        'no_dead_letters': len(_chat_items(_dead_letter_store, chat_id)) == 0,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Telegram service certification blocked', 'blockers': blockers})

    metrics = _baseline_metrics(chat_id)
    if metrics['runtime_reliability_score'] < payload.minimum_reliability_score:
        raise HTTPException(status_code=409, detail={
            'message': 'Telegram service reliability score below certification threshold',
            'score': metrics['runtime_reliability_score'],
            'required': payload.minimum_reliability_score,
        })

    now = datetime.now(timezone.utc).isoformat()
    certificate_payload = {
        'probation_id': payload.probation_id,
        'telegram_chat_id': chat_id,
        'metrics': metrics,
        'minimum_reliability_score': payload.minimum_reliability_score,
        'checks': checks,
    }
    certificate = {
        'certificate_id': str(uuid4()),
        **certificate_payload,
        'slo_baseline': {
            'delivery_success_rate': metrics['delivery_success_rate'],
            'lifecycle_completion_rate': metrics['lifecycle_completion_rate'],
            'queue_completion_rate': metrics['queue_completion_rate'],
            'dead_letter_rate': metrics['dead_letter_rate'],
        },
        'runtime_reliability_score': metrics['runtime_reliability_score'],
        'certificate_state': 'certified',
        'integrity_hash': _integrity_hash(certificate_payload),
        'immutable': True,
        'certified_by': payload.actor,
        'certified_at': now,
        'external_calls_made': 0,
    }
    _certificate_store[payload.probation_id] = certificate
    if go_live is not None:
        go_live['go_live_state'] = 'certified-operational-service'
        go_live['service_certificate_id'] = certificate['certificate_id']
    return {'state': 'telegram-service-certified', 'certificate': certificate, 'external_calls_made': 0}


@router.get('/status')
def certification_status() -> dict:
    items = list(_certificate_store.values())
    return {
        'certificates': len(items),
        'certified': sum(1 for item in items if item.get('certificate_state') == 'certified'),
        'average_reliability_score': round(sum(item['runtime_reliability_score'] for item in items) / len(items), 2) if items else 0.0,
        'external_calls_made': 0,
        'mode': 'post-probation-service-certification-with-slo-baseline',
    }


@router.get('/certificates')
def list_certificates() -> dict:
    items = sorted(_certificate_store.values(), key=lambda item: item['certified_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_restoration_probation_v21_329 import command_center as v21_329_command_center
    return v21_329_command_center().replace('v21.329', 'v21.330').replace(
        'AURON TELEGRAM RESTORATION PROBATION COMMAND CENTER',
        'AURON TELEGRAM SERVICE CERTIFICATION SLO COMMAND CENTER',
    )
