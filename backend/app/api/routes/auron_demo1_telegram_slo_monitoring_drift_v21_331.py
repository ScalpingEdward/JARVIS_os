from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_continuous_conversation_supervisor_v21_323 import _circuit_store
from app.api.routes.auron_demo1_telegram_operational_go_live_acceptance_v21_322 import _go_live_store
from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import (
    _baseline_metrics,
    _certificate_store,
)

router = APIRouter(prefix='/auron/demo1/v21.331', tags=['auron-demo1-telegram-slo-monitoring-drift'])

_monitor_store: dict[str, dict] = {}
_drift_store: dict[str, dict] = {}


class TelegramSLOObservationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certificate_id: str = Field(min_length=1, max_length=160)
    max_delivery_drop: float = Field(default=0.05, ge=0.0, le=1.0)
    max_lifecycle_drop: float = Field(default=0.05, ge=0.0, le=1.0)
    max_queue_drop: float = Field(default=0.10, ge=0.0, le=1.0)
    max_dead_letter_increase: float = Field(default=0.02, ge=0.0, le=1.0)
    max_reliability_drop: float = Field(default=5.0, ge=0.0, le=100.0)
    auto_suspend_on_critical_drift: bool = True


def reset_telegram_slo_monitoring_drift_store() -> None:
    _monitor_store.clear()
    _drift_store.clear()


def _certificate_by_id(certificate_id: str) -> dict | None:
    return next((item for item in _certificate_store.values() if item.get('certificate_id') == certificate_id), None)


@router.post('/observe')
def observe_certified_slo(payload: TelegramSLOObservationRequest) -> dict:
    certificate = _certificate_by_id(payload.certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail='Telegram service certificate not found')
    if certificate.get('certificate_state') not in {'certified', 'drift-warning', 'suspended-by-drift'}:
        raise HTTPException(status_code=409, detail='Telegram service certificate is not monitorable')

    chat_id = certificate['telegram_chat_id']
    go_live = _go_live_store.get(chat_id)
    current = _baseline_metrics(chat_id)
    baseline = certificate['slo_baseline']
    deltas = {
        'delivery_success_rate': round(current['delivery_success_rate'] - baseline['delivery_success_rate'], 6),
        'lifecycle_completion_rate': round(current['lifecycle_completion_rate'] - baseline['lifecycle_completion_rate'], 6),
        'queue_completion_rate': round(current['queue_completion_rate'] - baseline['queue_completion_rate'], 6),
        'dead_letter_rate': round(current['dead_letter_rate'] - baseline['dead_letter_rate'], 6),
        'runtime_reliability_score': round(current['runtime_reliability_score'] - certificate['runtime_reliability_score'], 2),
    }
    checks = {
        'delivery_within_tolerance': deltas['delivery_success_rate'] >= -payload.max_delivery_drop,
        'lifecycle_within_tolerance': deltas['lifecycle_completion_rate'] >= -payload.max_lifecycle_drop,
        'queue_within_tolerance': deltas['queue_completion_rate'] >= -payload.max_queue_drop,
        'dead_letter_within_tolerance': deltas['dead_letter_rate'] <= payload.max_dead_letter_increase,
        'reliability_within_tolerance': deltas['runtime_reliability_score'] >= -payload.max_reliability_drop,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    critical = any(name in blockers for name in {
        'delivery_within_tolerance',
        'lifecycle_within_tolerance',
        'dead_letter_within_tolerance',
        'reliability_within_tolerance',
    })
    trend_state = 'critical-drift' if critical else ('warning-drift' if blockers else 'stable')
    now = datetime.now(timezone.utc).isoformat()
    observation = {
        'observation_id': str(uuid4()),
        'certificate_id': payload.certificate_id,
        'telegram_chat_id': chat_id,
        'baseline': baseline,
        'current_metrics': current,
        'deltas': deltas,
        'checks': checks,
        'blockers': blockers,
        'trend_state': trend_state,
        'observed_by': payload.actor,
        'observed_at': now,
        'external_calls_made': 0,
    }
    _monitor_store[observation['observation_id']] = observation

    drift = None
    if blockers:
        drift = {
            'drift_id': str(uuid4()),
            'observation_id': observation['observation_id'],
            'certificate_id': payload.certificate_id,
            'telegram_chat_id': chat_id,
            'severity': 'critical' if critical else 'warning',
            'blockers': blockers,
            'deltas': deltas,
            'detected_at': now,
            'automatic_suspension_applied': False,
            'external_calls_made': 0,
        }
        _drift_store[drift['drift_id']] = drift
        certificate['certificate_state'] = 'drift-warning'

    if critical and payload.auto_suspend_on_critical_drift:
        certificate['certificate_state'] = 'suspended-by-drift'
        certificate['suspended_at'] = now
        if go_live is not None:
            go_live.update(
                continuous_mode_active=False,
                go_live_state='suspended-by-certification-drift',
                paused_at=now,
                pause_reason='critical-slo-certification-drift',
            )
        circuit = _circuit_store.setdefault(chat_id, {'telegram_chat_id': chat_id})
        circuit.update(state='open', opened_at=now, opened_reason='critical-slo-certification-drift')
        if drift is not None:
            drift['automatic_suspension_applied'] = True

    return {
        'state': f'telegram-certified-slo-{trend_state}',
        'observation': observation,
        'drift': drift,
        'continuous_mode_active': bool(go_live and go_live.get('continuous_mode_active')),
        'external_calls_made': 0,
        'next_layer': 'certification-drift-remediation' if blockers else 'continuous-slo-observation',
    }


@router.get('/status')
def slo_monitoring_status() -> dict:
    observations = list(_monitor_store.values())
    return {
        'observations': len(observations),
        'stable': sum(1 for item in observations if item.get('trend_state') == 'stable'),
        'warning_drift': sum(1 for item in observations if item.get('trend_state') == 'warning-drift'),
        'critical_drift': sum(1 for item in observations if item.get('trend_state') == 'critical-drift'),
        'drift_events': len(_drift_store),
        'suspended_certificates': sum(1 for item in _certificate_store.values() if item.get('certificate_state') == 'suspended-by-drift'),
        'external_calls_made': 0,
        'mode': 'continuous-slo-monitoring-reliability-trend-certification-drift-detection',
    }


@router.get('/observations')
def list_slo_observations() -> dict:
    items = sorted(_monitor_store.values(), key=lambda item: item['observed_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/drifts')
def list_certification_drifts() -> dict:
    items = sorted(_drift_store.values(), key=lambda item: item['detected_at'])
    return {'count': len(items), 'items': items, 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_service_certification_slo_v21_330 import command_center as v21_330_command_center
    return v21_330_command_center().replace('v21.330', 'v21.331').replace(
        'AURON TELEGRAM SERVICE CERTIFICATION SLO COMMAND CENTER',
        'AURON TELEGRAM CONTINUOUS SLO MONITORING DRIFT COMMAND CENTER',
    )
