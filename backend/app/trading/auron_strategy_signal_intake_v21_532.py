from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

SignalSide = Literal['buy', 'sell']
SignalType = Literal['market', 'limit', 'stop']
SignalState = Literal['received', 'validated', 'rejected']


class SignalIntakeError(RuntimeError):
    pass


@dataclass(frozen=True)
class StrategySignal:
    signal_id: str
    strategy_id: str
    source: str
    symbol: str
    side: SignalSide
    signal_type: SignalType
    entry_price: float | None
    stop_loss: float
    take_profit: float | None
    risk_pct: float | None
    confidence: float | None
    timeframe: str | None
    rationale: str
    created_at: str
    expires_at: str | None = None


@dataclass(frozen=True)
class SignalRecord:
    signal: StrategySignal
    state: SignalState
    integrity_hash: str
    rejection_reason: str | None
    execution_state: str
    external_calls_made: int = 0


class StrategySignalIntake:
    """Persistent signal intake boundary, deliberately separated from execution.

    B3 accepts and validates strategy intents only. It does not choose accounts,
    calculate lot sizes, place orders, or call MT5/brokers.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS strategy_signals (
                    signal_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL,
                    risk_pct REAL,
                    confidence REAL,
                    timeframe TEXT,
                    rationale TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    state TEXT NOT NULL,
                    integrity_hash TEXT NOT NULL,
                    rejection_reason TEXT,
                    execution_state TEXT NOT NULL
                )
            ''')

    @staticmethod
    def _hash(signal: StrategySignal) -> str:
        payload = {
            'signal_id': signal.signal_id,
            'strategy_id': signal.strategy_id,
            'source': signal.source,
            'symbol': signal.symbol,
            'side': signal.side,
            'signal_type': signal.signal_type,
            'entry_price': signal.entry_price,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'risk_pct': signal.risk_pct,
            'confidence': signal.confidence,
            'timeframe': signal.timeframe,
            'rationale': signal.rationale,
            'created_at': signal.created_at,
            'expires_at': signal.expires_at,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    @staticmethod
    def _validate(signal: StrategySignal) -> str | None:
        if not signal.strategy_id.strip() or not signal.source.strip() or not signal.symbol.strip():
            return 'strategy_id, source and symbol are required'
        if signal.stop_loss <= 0:
            return 'stop_loss must be positive'
        if signal.signal_type in {'limit', 'stop'} and (signal.entry_price is None or signal.entry_price <= 0):
            return 'pending signal types require a positive entry_price'
        if signal.signal_type == 'market' and signal.entry_price is not None and signal.entry_price <= 0:
            return 'entry_price must be positive when supplied'
        if signal.take_profit is not None and signal.take_profit <= 0:
            return 'take_profit must be positive when supplied'
        if signal.risk_pct is not None and not (0 < signal.risk_pct <= 10):
            return 'risk_pct must be > 0 and <= 10'
        if signal.confidence is not None and not (0 <= signal.confidence <= 1):
            return 'confidence must be between 0 and 1'
        return None

    def ingest(self, signal: StrategySignal) -> SignalRecord:
        integrity_hash = self._hash(signal)
        existing = self.get(signal.signal_id)
        if existing is not None:
            if existing.integrity_hash != integrity_hash:
                raise SignalIntakeError('signal_id already exists with different payload')
            return existing

        rejection = self._validate(signal)
        state: SignalState = 'rejected' if rejection else 'validated'
        execution_state = 'not-dispatched'
        with self._connect() as conn:
            conn.execute('''
                INSERT INTO strategy_signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                signal.signal_id, signal.strategy_id, signal.source, signal.symbol, signal.side,
                signal.signal_type, signal.entry_price, signal.stop_loss, signal.take_profit,
                signal.risk_pct, signal.confidence, signal.timeframe, signal.rationale,
                signal.created_at, signal.expires_at, state, integrity_hash, rejection,
                execution_state,
            ))
        record = self.get(signal.signal_id)
        if record is None:
            raise SignalIntakeError('signal persistence failed')
        return record

    def get(self, signal_id: str) -> SignalRecord | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM strategy_signals WHERE signal_id=?', (signal_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        signal = StrategySignal(
            signal_id=data['signal_id'], strategy_id=data['strategy_id'], source=data['source'],
            symbol=data['symbol'], side=data['side'], signal_type=data['signal_type'],
            entry_price=data['entry_price'], stop_loss=data['stop_loss'], take_profit=data['take_profit'],
            risk_pct=data['risk_pct'], confidence=data['confidence'], timeframe=data['timeframe'],
            rationale=data['rationale'], created_at=data['created_at'], expires_at=data['expires_at'],
        )
        return SignalRecord(signal, data['state'], data['integrity_hash'], data['rejection_reason'], data['execution_state'], 0)

    def list_validated(self, limit: int = 100) -> list[SignalRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT signal_id FROM strategy_signals WHERE state='validated' ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [record for row in rows if (record := self.get(row['signal_id'])) is not None]

    def mark_for_risk_evaluation(self, signal_id: str) -> SignalRecord:
        record = self.get(signal_id)
        if record is None:
            raise KeyError('signal not found')
        if record.state != 'validated':
            raise SignalIntakeError('only validated signals may advance to risk evaluation')
        with self._connect() as conn:
            conn.execute(
                "UPDATE strategy_signals SET execution_state='pending-risk-evaluation' WHERE signal_id=?",
                (signal_id,),
            )
        result = self.get(signal_id)
        if result is None:
            raise SignalIntakeError('signal state update failed')
        return result


def make_signal(
    *, strategy_id: str, source: str, symbol: str, side: SignalSide,
    signal_type: SignalType, stop_loss: float, rationale: str,
    entry_price: float | None = None, take_profit: float | None = None,
    risk_pct: float | None = None, confidence: float | None = None,
    timeframe: str | None = None, expires_at: str | None = None,
    signal_id: str | None = None,
) -> StrategySignal:
    return StrategySignal(
        signal_id=signal_id or str(uuid4()), strategy_id=strategy_id, source=source,
        symbol=symbol.upper(), side=side, signal_type=signal_type, entry_price=entry_price,
        stop_loss=stop_loss, take_profit=take_profit, risk_pct=risk_pct,
        confidence=confidence, timeframe=timeframe, rationale=rationale,
        created_at=datetime.now(timezone.utc).isoformat(), expires_at=expires_at,
    )
