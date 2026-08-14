from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_five_restoration_v21_518 import _succession_store
from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_four_monitoring_v21_516 import _monitor_store as _legacy_monitor_store

router = APIRouter(prefix='/auron/demo1/v21.519', tags=['auron-demo1-telegram-successor-next-generation-forty-five-monitoring'])

_monitor_store: dict[str, dict] = {}
_drift_store: dict[str, dict] = {}
_baseline_store: dict[str, dict] = {}

_START_PHRASE = 'START AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY FIVE MONITORING'
_AUDIT_PHRASE = 'AUDIT AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY FIVE HEALTH'
_DRIFT_PHRASE = 'DECLARE AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY FIVE DRIFT'
_BASELINE_PHRASE = 'CERTIFY AURON TELEGRAM SUCCESSOR NEXT GENERATION FORTY FIVE RENEWED BASELINE'

class MonitoringStartRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    certification_id: str = Field(min_length=1, max_length=160)
    start_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_forty_five_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    monitoring_reference: str = Field(min_length=1, max_length=300)

class HealthAuditRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    audit_phrase: str = Field(min_length=1, max_length=320)
    observed_successor_next_generation_forty_five_hash: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')
    control_state: str = Field(pattern='^(healthy|degraded|failed)$')
    audit_statement: str = Field(min_length=1, max_length=1800)

class DriftRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    drift_phrase: str = Field(min_length=1, max_length=320)
    drift_reference: str = Field(min_length=1, max_length=300)
    drift_statement: str = Field(min_length=1, max_length=1800)

class BaselineCertificationRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    monitoring_id: str = Field(min_length=1, max_length=160)
    certification_phrase: str = Field(min_length=1, max_length=320)
    baseline_reference: str = Field(min_length=1, max_length=300)
    baseline_statement: str = Field(min_length=1, max_length=1800)


def reset_telegram_successor_next_generation_forty_five_monitoring_store() -> None:
    _monitor_store.clear(); _drift_store.clear(); _baseline_store.clear()


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _find(store: dict[str, dict], key: str, value: str) -> dict | None:
    return next((item for item in store.values() if item.get(key) == value), None)


@router.post('/monitoring/start')
def start_monitoring(payload: MonitoringStartRequest) -> dict:
    if payload.start_phrase != _START_PHRASE:
        raise HTTPException(403, 'Explicit successor-next-generation-forty-five monitoring start required')
    existing = _monitor_store.get(payload.certification_id)
    if existing:
        return {'state':'telegram-successor-next-generation-forty-five-monitoring-already-active','monitoring':existing,'idempotent_replay':True,'external_calls_made':0}
    certification = _find(_succession_store, 'certification_id', payload.certification_id)
    if certification is None:
        raise HTTPException(404, 'Stable successor-next-generation-forty-five succession certification not found')
    legacy = _find(_legacy_monitor_store, 'monitoring_id', certification['monitoring_id'])
    expected = certification['active_successor_next_generation_forty_five_hash']
    checks = {'succession_certified':certification.get('certification_state')=='successor-next-generation-forty-five-succession-certified-stable','certification_immutable':certification.get('immutable') is True and bool(certification.get('integrity_hash')),'legacy_state_ready':legacy is not None and legacy.get('monitoring_state')=='certified-successor-next-generation-forty-five-monitoring-pending','hash_matches':payload.observed_successor_next_generation_forty_five_hash==expected,'controls_healthy':payload.control_state=='healthy'}
    blockers=[k for k,v in checks.items() if not v]
    if blockers: raise HTTPException(409, {'message':'Successor-next-generation-forty-five monitoring start blocked','blockers':blockers})
    data={'certification_id':certification['certification_id'],'predecessor_monitoring_id':certification['monitoring_id'],'active_successor_next_generation_forty_five_hash':expected,'monitoring_reference':payload.monitoring_reference,'checks':checks}
    monitoring={'monitoring_id':str(uuid4()),**data,'monitoring_state':'successor-next-generation-forty-five-monitoring-active','health_audits':[],'integrity_hash':_hash(data),'immutable':True,'started_by':payload.actor,'started_at':datetime.now(timezone.utc).isoformat(),'external_calls_made':0}
    _monitor_store[payload.certification_id]=monitoring
    legacy['monitoring_state']='successor-next-generation-forty-five-monitoring-handed-off'; legacy['successor_next_generation_forty_five_monitoring_id']=monitoring['monitoring_id']
    return {'state':'telegram-successor-next-generation-forty-five-monitoring-active','monitoring':monitoring,'external_calls_made':0}


@router.post('/monitoring/audit')
def audit_health(payload: HealthAuditRequest) -> dict:
    if payload.audit_phrase != _AUDIT_PHRASE: raise HTTPException(403, 'Explicit successor-next-generation-forty-five health audit required')
    monitoring=_find(_monitor_store,'monitoring_id',payload.monitoring_id)
    if monitoring is None: raise HTTPException(404,'Successor-next-generation-forty-five monitoring not found')
    expected=monitoring['active_successor_next_generation_forty_five_hash']
    checks={'monitoring_active':monitoring.get('monitoring_state') in {'successor-next-generation-forty-five-monitoring-active','successor-next-generation-forty-five-health-verified'},'hash_matches':payload.observed_successor_next_generation_forty_five_hash==expected,'controls_healthy':payload.control_state=='healthy','no_open_drift':monitoring['monitoring_id'] not in _drift_store}
    healthy=all(checks.values()); data={'monitoring_id':monitoring['monitoring_id'],'observed_hash':payload.observed_successor_next_generation_forty_five_hash,'control_state':payload.control_state,'audit_statement':payload.audit_statement,'checks':checks}
    audit={'audit_id':str(uuid4()),**data,'health_state':'healthy' if healthy else 'drift-detected','integrity_hash':_hash(data),'immutable':True,'audited_by':payload.actor,'audited_at':datetime.now(timezone.utc).isoformat(),'external_calls_made':0}
    monitoring['health_audits'].append(audit); monitoring['monitoring_state']='successor-next-generation-forty-five-health-verified' if healthy else 'successor-next-generation-forty-five-drift-pending'
    return {'state':f"telegram-successor-next-generation-forty-five-{audit['health_state']}",'audit':audit,'monitoring':monitoring,'external_calls_made':0}


@router.post('/drift/declare')
def declare_drift(payload: DriftRequest) -> dict:
    if payload.drift_phrase != _DRIFT_PHRASE: raise HTTPException(403,'Explicit successor-next-generation-forty-five drift declaration required')
    monitoring=_find(_monitor_store,'monitoring_id',payload.monitoring_id)
    if monitoring is None: raise HTTPException(404,'Successor-next-generation-forty-five monitoring not found')
    existing=_drift_store.get(monitoring['monitoring_id'])
    if existing: return {'state':'telegram-successor-next-generation-forty-five-drift-already-declared','drift':existing,'idempotent_replay':True,'external_calls_made':0}
    audits=monitoring.get('health_audits',[]); latest=audits[-1] if audits else None
    checks={'audit_exists':latest is not None,'audit_detected_drift':latest is not None and latest.get('health_state')=='drift-detected','monitoring_pending_drift':monitoring.get('monitoring_state')=='successor-next-generation-forty-five-drift-pending'}
    blockers=[k for k,v in checks.items() if not v]
    if blockers: raise HTTPException(409,{'message':'Successor-next-generation-forty-five drift declaration blocked','blockers':blockers})
    data={'monitoring_id':monitoring['monitoring_id'],'audit_id':latest['audit_id'],'drift_reference':payload.drift_reference,'drift_statement':payload.drift_statement,'checks':checks}
    drift={'drift_id':str(uuid4()),**data,'drift_state':'successor-next-generation-forty-five-drift-open','integrity_hash':_hash(data),'immutable':True,'declared_by':payload.actor,'declared_at':datetime.now(timezone.utc).isoformat(),'external_calls_made':0}
    _drift_store[monitoring['monitoring_id']]=drift; monitoring['monitoring_state']='successor-next-generation-forty-five-drift-open'; monitoring['drift_id']=drift['drift_id']
    return {'state':'telegram-successor-next-generation-forty-five-drift-open','drift':drift,'monitoring':monitoring,'external_calls_made':0}


@router.post('/baseline/certify')
def certify_baseline(payload: BaselineCertificationRequest) -> dict:
    if payload.certification_phrase != _BASELINE_PHRASE: raise HTTPException(403,'Explicit successor-next-generation-forty-five renewed baseline certification required')
    monitoring=_find(_monitor_store,'monitoring_id',payload.monitoring_id)
    if monitoring is None: raise HTTPException(404,'Successor-next-generation-forty-five monitoring not found')
    existing=_baseline_store.get(monitoring['monitoring_id'])
    if existing: return {'state':'telegram-successor-next-generation-forty-five-renewed-baseline-already-certified','baseline':existing,'idempotent_replay':True,'external_calls_made':0}
    audits=monitoring.get('health_audits',[]); latest=audits[-1] if audits else None
    checks={'health_verified':monitoring.get('monitoring_state')=='successor-next-generation-forty-five-health-verified','latest_audit_healthy':latest is not None and latest.get('health_state')=='healthy','no_open_drift':monitoring['monitoring_id'] not in _drift_store,'monitoring_immutable':monitoring.get('immutable') is True and bool(monitoring.get('integrity_hash'))}
    blockers=[k for k,v in checks.items() if not v]
    if blockers: raise HTTPException(409,{'message':'Successor-next-generation-forty-five renewed baseline certification blocked','blockers':blockers})
    data={'monitoring_id':monitoring['monitoring_id'],'audit_id':latest['audit_id'],'active_successor_next_generation_forty_five_hash':monitoring['active_successor_next_generation_forty_five_hash'],'baseline_reference':payload.baseline_reference,'baseline_statement':payload.baseline_statement,'checks':checks}
    baseline={'baseline_id':str(uuid4()),**data,'baseline_state':'successor-next-generation-forty-five-renewed-baseline-certified-active','integrity_hash':_hash(data),'immutable':True,'certified_by':payload.actor,'certified_at':datetime.now(timezone.utc).isoformat(),'external_calls_made':0}
    _baseline_store[monitoring['monitoring_id']]=baseline; monitoring['monitoring_state']='successor-next-generation-forty-five-renewed-baseline-active'; monitoring['baseline_id']=baseline['baseline_id']
    return {'state':'telegram-successor-next-generation-forty-five-renewed-baseline-certified-active','baseline':baseline,'monitoring':monitoring,'external_calls_made':0,'next_layer':'successor-next-generation-forty-five-renewed-baseline-continuity-expiry-renewal-governance'}


@router.get('/status')
def status() -> dict:
    return {'monitoring_sessions':len(_monitor_store),'open_drifts':len(_drift_store),'renewed_baselines':len(_baseline_store),'external_calls_made':0,'mode':'successor-next-generation-forty-five-monitoring-drift-renewed-baseline'}

@router.get('/command-center',response_class=HTMLResponse)
def command_center() -> str:
    return '<!doctype html><html><body><h1>AURON v21.519</h1><p>successor-next-generation-forty-five monitoring, drift governance and renewed baseline certification</p><p>no Telegram API call · no provider execution · no outbound message · external_calls_made=0</p></body></html>'
