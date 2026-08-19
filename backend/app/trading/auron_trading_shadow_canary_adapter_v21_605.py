from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import CanaryProviderResult


class TradingShadowCanaryAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class TradingShadowCanaryDescriptor:
    adapter_id: str
    vertical: str
    provider_id: str
    allowed_actions: tuple[str, ...]
    shadow_only: bool
    broker_credentials_required: bool
    broker_network_enabled: bool
    live_order_placement_enabled: bool
    order_cancel_modify_enabled: bool
    position_mutation_enabled: bool
    production_transport_enabled: bool


class TradingShadowCanaryAdapter:
    """G18 local Trading shadow adapter compatible with F2/F3 boundaries.

    The adapter evaluates trade plans and simulates order intent into local persistent state only.
    It has no broker client, accepts no broker credentials, performs no network calls, and cannot
    place/cancel/modify live orders or mutate positions.
    """

    ADAPTER_ID='trading-shadow-canary-v1'
    VERTICAL='trading'
    PROVIDER_ID='trading-analysis-shadow'
    ALLOWED_ACTIONS=('evaluate-trade-plan','simulate-order-intent')

    def __init__(self, db_path: str | Path) -> None:
        self.db_path=str(db_path)
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.db_path); conn.row_factory=sqlite3.Row; return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS trading_shadow_canary_actions(
                    provider_ref TEXT PRIMARY KEY,
                    vertical TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trading_shadow_canary_stops(
                    activation_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    stopped_at TEXT NOT NULL
                );
            ''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @staticmethod
    def _positive_number(value, field: str) -> float:
        if isinstance(value,bool):
            raise TradingShadowCanaryAdapterError(f'{field} must be numeric')
        try:
            number=float(value)
        except (TypeError,ValueError) as exc:
            raise TradingShadowCanaryAdapterError(f'{field} must be numeric') from exc
        if number <= 0:
            raise TradingShadowCanaryAdapterError(f'{field} must be positive')
        return number

    def descriptor(self) -> TradingShadowCanaryDescriptor:
        return TradingShadowCanaryDescriptor(
            self.ADAPTER_ID,self.VERTICAL,self.PROVIDER_ID,self.ALLOWED_ACTIONS,
            True,False,False,False,False,False,False)

    def execute_canary_action(self, *, vertical: str, provider_id: str, scope: str,
                              action_key: str, payload: dict, idempotency_key: str) -> str:
        if vertical != self.VERTICAL:
            raise TradingShadowCanaryAdapterError('trading shadow vertical mismatch')
        if provider_id != self.PROVIDER_ID:
            raise TradingShadowCanaryAdapterError('trading shadow provider mismatch')
        if action_key not in self.ALLOWED_ACTIONS:
            raise TradingShadowCanaryAdapterError('trading shadow action not allowed')
        if not scope.strip():
            raise TradingShadowCanaryAdapterError('explicit shadow scope required')
        if not isinstance(payload,dict):
            raise TradingShadowCanaryAdapterError('payload must be a mapping')

        forbidden={
            'api_key','api_secret','password','token','broker_credentials','broker_session',
            'place_order','send_order','cancel_order','modify_order','close_position','modify_position',
            'broker_url','broker_host','account_login','account_password','live_execute'
        }
        if forbidden.intersection(payload):
            raise TradingShadowCanaryAdapterError('broker credential/live execution fields forbidden')

        symbol=str(payload.get('symbol','')).strip().upper()
        side=str(payload.get('side','')).strip().lower()
        if not symbol:
            raise TradingShadowCanaryAdapterError('symbol required')
        if side not in {'buy','sell'}:
            raise TradingShadowCanaryAdapterError('side must be buy or sell')

        analysis: dict
        if action_key=='evaluate-trade-plan':
            entry=self._positive_number(payload.get('entry'),'entry')
            stop=self._positive_number(payload.get('stop_loss'),'stop_loss')
            target=self._positive_number(payload.get('take_profit'),'take_profit')
            risk=self._positive_number(payload.get('risk_percent'),'risk_percent')
            if risk > 100:
                raise TradingShadowCanaryAdapterError('risk_percent cannot exceed 100')
            risk_distance=abs(entry-stop)
            reward_distance=abs(target-entry)
            rr=None if risk_distance == 0 else reward_distance/risk_distance
            direction_valid=(side=='buy' and stop < entry < target) or (side=='sell' and target < entry < stop)
            analysis={
                'symbol':symbol,'side':side,'entry':entry,'stop_loss':stop,'take_profit':target,
                'risk_percent':risk,'risk_reward_ratio':rr,'direction_valid':direction_valid,
                'decision':'shadow-valid' if direction_valid and rr is not None and rr > 0 else 'shadow-invalid',
                'broker_connected':False,'live_order_created':False,'position_mutated':False,
                'network_calls_made':0,
            }
        else:
            order_type=str(payload.get('order_type','')).strip().lower()
            if order_type not in {'market','limit','stop'}:
                raise TradingShadowCanaryAdapterError('order_type must be market, limit or stop')
            quantity=self._positive_number(payload.get('quantity'),'quantity')
            intended_price=payload.get('intended_price')
            normalized_price=None if intended_price is None else self._positive_number(intended_price,'intended_price')
            analysis={
                'symbol':symbol,'side':side,'order_type':order_type,'quantity':quantity,
                'intended_price':normalized_price,'intent_state':'simulated-not-submitted',
                'broker_connected':False,'live_order_created':False,'position_mutated':False,
                'network_calls_made':0,
            }

        payload_hash=self._hash(payload)
        provider_ref='trading-shadow-'+self._hash({
            'provider':provider_id,'action':action_key,'payload_hash':payload_hash,
            'idempotency_key':idempotency_key})[:24]
        with self._connect() as conn:
            existing=conn.execute(
                'SELECT provider_ref FROM trading_shadow_canary_actions WHERE idempotency_key=?',
                (idempotency_key,),).fetchone()
            if existing:
                return str(existing['provider_ref'])
            conn.execute('''INSERT INTO trading_shadow_canary_actions(
                provider_ref,vertical,provider_id,scope,action_key,payload_json,payload_hash,
                idempotency_key,state,analysis_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',(
                provider_ref,vertical,provider_id,scope.strip(),action_key,
                json.dumps(payload,sort_keys=True,separators=(',',':')),payload_hash,idempotency_key,
                'completed',json.dumps(analysis,sort_keys=True,separators=(',',':')),self._now()))
        return provider_ref

    def read_result(self, *, provider_ref: str) -> CanaryProviderResult:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM trading_shadow_canary_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None:
            raise TradingShadowCanaryAdapterError('trading shadow result not found')
        return CanaryProviderResult(
            str(row['provider_ref']),str(row['vertical']),str(row['provider_id']),str(row['state']),
            str(row['action_key']),str(row['payload_hash']),external_calls_made=0)

    def analysis(self, provider_ref: str) -> dict:
        with self._connect() as conn:
            row=conn.execute('SELECT analysis_json FROM trading_shadow_canary_actions WHERE provider_ref=?',(provider_ref,)).fetchone()
        if row is None:
            raise TradingShadowCanaryAdapterError('trading shadow analysis not found')
        return json.loads(row['analysis_json'])

    def stop_canary(self, *, activation_id: str, reason: str) -> None:
        if not activation_id.strip():
            raise TradingShadowCanaryAdapterError('activation id required')
        with self._connect() as conn:
            conn.execute('''INSERT INTO trading_shadow_canary_stops VALUES (?,?,?)
                ON CONFLICT(activation_id) DO UPDATE SET reason=excluded.reason,stopped_at=excluded.stopped_at''',
                (activation_id.strip(),reason.strip() or 'unspecified',self._now()))

    def is_stopped(self, activation_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute('SELECT 1 FROM trading_shadow_canary_stops WHERE activation_id=?',(activation_id,)).fetchone() is not None
