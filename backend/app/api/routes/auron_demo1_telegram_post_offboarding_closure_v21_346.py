from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.routes.auron_demo1_telegram_return_deletion_offboarding_v21_345 import (
    _offboarding_store,
    _proof_store,
    _residual_exception_store,
)

router = APIRouter(prefix='/auron/demo1/v21.346', tags=['auron-demo1-telegram-post-offboarding-closure'])

_archive_store: dict[str, dict] = {}
_risk_review_store: dict[str, dict] = {}
_closure_store: dict[str, dict] = {}
_ARCHIVE_PHRASE = 'ARCHIVE AURON TELEGRAM POST OFFBOARDING EVIDENCE'
_REVIEW_PHRASE = 'REVIEW AURON TELEGRAM RESIDUAL DISCLOSURE RISK'
_CLOSE_PHRASE = 'CLOSE AURON TELEGRAM DISCLOSURE LIFECYCLE'


class PostOffboardingArchiveRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    retention_id: str = Field(min_length=1, max_length=160)
    archive_phrase: str = Field(min_length=1, max_length=320)
    archive_reference: str = Field(min_length=1, max_length=300)


class ResidualRiskReviewRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    archive_id: str = Field(min_length=1, max_length=160)
    review_phrase: str = Field(min_length=1, max_length=320)
    risk_rating: str = Field(pattern='^(none|low|medium|high|critical)$')
    review_statement: str = Field(min_length=1, max_length=1800)


class DisclosureLifecycleCloseRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    archive_id: str = Field(min_length=1, max_length=160)
    closure_phrase: str = Field(min_length=1, max_length=320)
    closure_reference: str = Field(min_length=1, max_length=300)


def reset_telegram_post_offboarding_closure_store() -> None:
    _archive_store.clear()
    _risk_review_store.clear()
    _closure_store.clear()


def _hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _offboarding_by_retention(retention_id: str) -> dict | None:
    return _offboarding_store.get(retention_id)


def _archive_by_id(archive_id: str) -> dict | None:
    return next((item for item in _archive_store.values() if item.get('archive_id') == archive_id), None)


@router.post('/archive')
def archive_post_offboarding_evidence(payload: PostOffboardingArchiveRequest) -> dict:
    if payload.archive_phrase != _ARCHIVE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit post-offboarding evidence archive approval required')
    existing = _archive_store.get(payload.retention_id)
    if existing is not None:
        return {'state': 'telegram-post-offboarding-evidence-already-archived', 'archive': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    offboarding = _offboarding_by_retention(payload.retention_id)
    proof = _proof_store.get(payload.retention_id)
    residual = _residual_exception_store.get(payload.retention_id)
    if offboarding is None or proof is None:
        raise HTTPException(status_code=404, detail='Completed recipient offboarding evidence not found')
    checks = {
        'recipient_offboarded': offboarding.get('offboarding_state') == 'recipient-offboarded-compliance-closed',
        'offboarding_immutable': offboarding.get('immutable') is True and bool(offboarding.get('integrity_hash')),
        'proof_immutable': proof.get('immutable') is True and bool(proof.get('integrity_hash')),
        'proof_matches_offboarding': proof.get('proof_id') == offboarding.get('proof_id'),
        'no_open_residual_copy_exception': not bool(residual and residual.get('exception_state') == 'open-residual-copy-exception'),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Post-offboarding evidence archive blocked', 'blockers': blockers})
    evidence = {
        'retention_id': payload.retention_id,
        'offboarding_id': offboarding['offboarding_id'],
        'offboarding_integrity_hash': offboarding['integrity_hash'],
        'proof_id': proof['proof_id'],
        'proof_integrity_hash': proof['integrity_hash'],
        'proof_type': proof['proof_type'],
        'archive_reference': payload.archive_reference,
        'checks': checks,
    }
    archive = {
        'archive_id': str(uuid4()),
        **evidence,
        'archive_state': 'immutable-post-offboarding-evidence-archived',
        'archive_hash': _hash(evidence),
        'immutable': True,
        'archived_by': payload.actor,
        'archived_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _archive_store[payload.retention_id] = archive
    return {'state': 'telegram-post-offboarding-evidence-archived', 'archive': archive, 'external_calls_made': 0}


@router.post('/risk-review')
def review_residual_disclosure_risk(payload: ResidualRiskReviewRequest) -> dict:
    if payload.review_phrase != _REVIEW_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit residual disclosure-risk review required')
    existing = _risk_review_store.get(payload.archive_id)
    if existing is not None:
        return {'state': 'telegram-residual-risk-already-reviewed', 'review': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    archive = _archive_by_id(payload.archive_id)
    if archive is None:
        raise HTTPException(status_code=404, detail='Telegram post-offboarding evidence archive not found')
    checks = {
        'archive_valid': archive.get('archive_state') == 'immutable-post-offboarding-evidence-archived',
        'archive_immutable': archive.get('immutable') is True,
        'archive_hash_valid': archive.get('archive_hash') == _hash({
            'retention_id': archive['retention_id'],
            'offboarding_id': archive['offboarding_id'],
            'offboarding_integrity_hash': archive['offboarding_integrity_hash'],
            'proof_id': archive['proof_id'],
            'proof_integrity_hash': archive['proof_integrity_hash'],
            'proof_type': archive['proof_type'],
            'archive_reference': archive['archive_reference'],
            'checks': archive['checks'],
        }),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Residual disclosure-risk review blocked', 'blockers': blockers})
    data = {
        'archive_id': archive['archive_id'],
        'retention_id': archive['retention_id'],
        'risk_rating': payload.risk_rating,
        'review_statement': payload.review_statement,
        'archive_hash': archive['archive_hash'],
        'checks': checks,
    }
    review = {
        'risk_review_id': str(uuid4()),
        **data,
        'review_state': 'residual-risk-reviewed',
        'closure_eligible': payload.risk_rating in {'none', 'low'},
        'integrity_hash': _hash(data),
        'immutable': True,
        'reviewed_by': payload.actor,
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _risk_review_store[payload.archive_id] = review
    return {'state': 'telegram-residual-disclosure-risk-reviewed', 'review': review, 'external_calls_made': 0}


@router.post('/close')
def close_disclosure_lifecycle(payload: DisclosureLifecycleCloseRequest) -> dict:
    if payload.closure_phrase != _CLOSE_PHRASE:
        raise HTTPException(status_code=403, detail='Explicit disclosure lifecycle closure approval required')
    existing = _closure_store.get(payload.archive_id)
    if existing is not None:
        return {'state': 'telegram-disclosure-lifecycle-already-closed', 'closure': existing, 'idempotent_replay': True, 'external_calls_made': 0}
    archive = _archive_by_id(payload.archive_id)
    review = _risk_review_store.get(payload.archive_id)
    if archive is None or review is None:
        raise HTTPException(status_code=409, detail='Completed archive and residual-risk review required')
    checks = {
        'archive_immutable': archive.get('immutable') is True and bool(archive.get('archive_hash')),
        'risk_review_immutable': review.get('immutable') is True and bool(review.get('integrity_hash')),
        'risk_review_matches_archive': review.get('archive_id') == archive.get('archive_id'),
        'residual_risk_acceptable': review.get('closure_eligible') is True,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers:
        raise HTTPException(status_code=409, detail={'message': 'Final disclosure lifecycle closure blocked', 'blockers': blockers})
    data = {
        'archive_id': archive['archive_id'],
        'risk_review_id': review['risk_review_id'],
        'retention_id': archive['retention_id'],
        'closure_reference': payload.closure_reference,
        'checks': checks,
    }
    closure = {
        'closure_id': str(uuid4()),
        **data,
        'closure_state': 'final-disclosure-lifecycle-closed',
        'integrity_hash': _hash(data),
        'immutable': True,
        'closed_by': payload.actor,
        'closed_at': datetime.now(timezone.utc).isoformat(),
        'external_calls_made': 0,
    }
    _closure_store[payload.archive_id] = closure
    archive['archive_state'] = 'archived-final-lifecycle-closed'
    archive['closure_id'] = closure['closure_id']
    return {'state': 'telegram-final-disclosure-lifecycle-closed', 'closure': closure, 'archive': archive, 'external_calls_made': 0, 'next_layer': 'closed-disclosure-record-retention-and-periodic-integrity-audit'}


@router.get('/status')
def post_offboarding_closure_status() -> dict:
    return {
        'archives': len(_archive_store),
        'risk_reviews': len(_risk_review_store),
        'final_closures': len(_closure_store),
        'closure_blocked_reviews': sum(1 for item in _risk_review_store.values() if not item.get('closure_eligible')),
        'external_calls_made': 0,
        'mode': 'post-offboarding-evidence-archive-residual-risk-review-final-lifecycle-closure',
    }


@router.get('/archives')
def list_archives() -> dict:
    return {'count': len(_archive_store), 'items': list(_archive_store.values()), 'external_calls_made': 0}


@router.get('/risk-reviews')
def list_risk_reviews() -> dict:
    return {'count': len(_risk_review_store), 'items': list(_risk_review_store.values()), 'external_calls_made': 0}


@router.get('/closures')
def list_closures() -> dict:
    return {'count': len(_closure_store), 'items': list(_closure_store.values()), 'external_calls_made': 0}


@router.get('/command-center', response_class=HTMLResponse)
def command_center() -> str:
    from app.api.routes.auron_demo1_telegram_return_deletion_offboarding_v21_345 import command_center as v21_345_command_center
    return v21_345_command_center().replace('v21.345', 'v21.346').replace(
        'AURON TELEGRAM RETURN DELETION OFFBOARDING COMMAND CENTER',
        'AURON TELEGRAM POST OFFBOARDING CLOSURE COMMAND CENTER',
    )
