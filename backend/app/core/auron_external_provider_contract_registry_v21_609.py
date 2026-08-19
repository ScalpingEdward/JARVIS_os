from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


class ExternalProviderContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExternalProviderContract:
    contract_id: str
    vertical: str
    provider_id: str
    adapter_id: str
    environment: str
    allowed_capabilities: tuple[str, ...]
    credential_ref: str | None
    read_only: bool
    provider_write_enabled: bool
    network_transport_enabled: bool
    production_transport_enabled: bool
    created_at: str


class ExternalProviderContractRegistry:
    """H1 secretless registry for external-provider sandbox contracts.

    This layer records capability declarations and opaque credential references only. It does not
    resolve secrets, construct provider clients, make network calls, or authorize transport.
    """

    FORBIDDEN_SECRET_MARKERS=(
        'api_key','api_secret','access_token','refresh_token','password','secret','private_key',
        'client_secret','bearer','authorization',
    )

    def __init__(self, db_path: str | Path) -> None:
        self.db_path=str(db_path)
        Path(self.db_path).parent.mkdir(parents=True,exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.db_path); conn.row_factory=sqlite3.Row; return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS external_provider_contracts(
                contract_id TEXT PRIMARY KEY, vertical TEXT NOT NULL, provider_id TEXT NOT NULL,
                adapter_id TEXT NOT NULL, environment TEXT NOT NULL, capabilities_json TEXT NOT NULL,
                credential_ref TEXT, read_only INTEGER NOT NULL, provider_write_enabled INTEGER NOT NULL,
                network_transport_enabled INTEGER NOT NULL, production_transport_enabled INTEGER NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(vertical,provider_id,adapter_id,environment))''')

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash(value: dict) -> str:
        return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @classmethod
    def _validate_secretless(cls, payload: dict) -> None:
        lowered={str(k).lower() for k in payload}
        if any(marker in key for key in lowered for marker in cls.FORBIDDEN_SECRET_MARKERS):
            raise ExternalProviderContractError('raw secret material is forbidden in provider contracts')

    def register(self, *, vertical: str, provider_id: str, adapter_id: str, environment: str,
                 allowed_capabilities: tuple[str, ...], credential_ref: str | None = None,
                 read_only: bool = True, provider_write_enabled: bool = False,
                 network_transport_enabled: bool = False,
                 production_transport_enabled: bool = False,
                 metadata: dict | None = None) -> ExternalProviderContract:
        metadata=metadata or {}
        self._validate_secretless(metadata)
        vertical=vertical.strip(); provider_id=provider_id.strip(); adapter_id=adapter_id.strip(); environment=environment.strip()
        if not all((vertical,provider_id,adapter_id,environment)):
            raise ExternalProviderContractError('vertical/provider/adapter/environment required')
        caps=tuple(dict.fromkeys(c.strip() for c in allowed_capabilities if c.strip()))
        if not caps:
            raise ExternalProviderContractError('at least one capability required')
        if environment != 'sandbox':
            raise ExternalProviderContractError('H1 permits sandbox contracts only')
        if not read_only or provider_write_enabled:
            raise ExternalProviderContractError('H1 permits read-only contracts only')
        if network_transport_enabled or production_transport_enabled:
            raise ExternalProviderContractError('H1 cannot enable network or production transport')
        if credential_ref is not None:
            ref=credential_ref.strip()
            if not ref or any(ch.isspace() for ch in ref):
                raise ExternalProviderContractError('credential_ref must be an opaque non-empty reference')
            if len(ref) > 200:
                raise ExternalProviderContractError('credential_ref too long')
            credential_ref=ref
        created=self._now()
        identity={'vertical':vertical,'provider_id':provider_id,'adapter_id':adapter_id,'environment':environment,'capabilities':caps,'credential_ref':credential_ref}
        cid='provider-contract-'+self._hash(identity)[:24]
        record=ExternalProviderContract(cid,vertical,provider_id,adapter_id,environment,caps,credential_ref,
            True,False,False,False,created)
        with self._connect() as conn:
            existing=conn.execute('''SELECT * FROM external_provider_contracts
                WHERE vertical=? AND provider_id=? AND adapter_id=? AND environment=?''',
                (vertical,provider_id,adapter_id,environment)).fetchone()
            if existing:
                return self._from_row(existing)
            conn.execute('INSERT INTO external_provider_contracts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(
                record.contract_id,record.vertical,record.provider_id,record.adapter_id,record.environment,
                json.dumps(record.allowed_capabilities),record.credential_ref,int(record.read_only),
                int(record.provider_write_enabled),int(record.network_transport_enabled),
                int(record.production_transport_enabled),record.created_at))
        return record

    def get(self, contract_id: str) -> ExternalProviderContract | None:
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM external_provider_contracts WHERE contract_id=?',(contract_id,)).fetchone()
        return None if row is None else self._from_row(row)

    def require_secretless_sandbox(self, contract_id: str) -> ExternalProviderContract:
        record=self.get(contract_id)
        if record is None:
            raise ExternalProviderContractError('provider contract not found')
        if record.environment!='sandbox' or not record.read_only or record.provider_write_enabled:
            raise ExternalProviderContractError('provider contract is not read-only sandbox safe')
        if record.network_transport_enabled or record.production_transport_enabled:
            raise ExternalProviderContractError('provider transport remains unauthorized')
        return record

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ExternalProviderContract:
        return ExternalProviderContract(
            row['contract_id'],row['vertical'],row['provider_id'],row['adapter_id'],row['environment'],
            tuple(json.loads(row['capabilities_json'])),row['credential_ref'],bool(row['read_only']),
            bool(row['provider_write_enabled']),bool(row['network_transport_enabled']),
            bool(row['production_transport_enabled']),row['created_at'])

    def export_public_descriptor(self, contract_id: str) -> dict:
        record=self.require_secretless_sandbox(contract_id)
        data=asdict(record)
        data['credential_ref_present']=record.credential_ref is not None
        data.pop('credential_ref',None)
        return data
