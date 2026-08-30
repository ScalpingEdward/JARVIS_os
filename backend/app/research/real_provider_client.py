from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_DB_PATH = "data/research_provider_audit.db"


class ResearchProviderFetchError(RuntimeError):
    """Raised whenever a request cannot be executed safely. Fail-closed: on any
    ambiguity or violation, no request is sent and no partial result is returned."""


@dataclass(frozen=True)
class ResearchProviderConfig:
    """Everything the H1-H40 design chain specified in the abstract, enforced for real."""

    allowed_domains: tuple[str, ...]
    timeout_seconds: float = 10.0
    max_response_bytes: int = 1_000_000
    allowed_methods: tuple[str, ...] = ("GET",)


@dataclass(frozen=True)
class ResearchFetchResult:
    request_id: str
    url: str
    status_code: int
    bytes_read: int
    content: str
    fetched_at: str


class ResearchProviderAuditLog:
    """Append-only audit trail for every real outbound research request."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS research_provider_requests(
                    request_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER,
                    bytes_read INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def record(
        self,
        request_id: str,
        url: str,
        method: str,
        status_code: int | None,
        bytes_read: int,
        outcome: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO research_provider_requests
                (request_id, url, method, status_code, bytes_read, outcome, created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    request_id,
                    url,
                    method,
                    status_code,
                    bytes_read,
                    outcome,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def already_succeeded(self, request_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM research_provider_requests WHERE request_id = ? AND outcome = 'success'",
                (request_id,),
            ).fetchone()
        return row is not None


class ResearchProviderClient:
    """The first real, executable outbound call in the research vertical.

    Replaces the H1-H40 design/certification chain, which never performed a
    network call and was never wired into the application. This client
    performs real HTTPS GET requests, but only against an explicit domain
    allowlist, with a bounded timeout, a bounded response size, and an
    append-only audit trail. It never resolves credentials, never writes to a
    provider, and treats every request_id as exactly-once.
    """

    def __init__(
        self,
        config: ResearchProviderConfig,
        audit_log: ResearchProviderAuditLog | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.audit_log = audit_log or ResearchProviderAuditLog()
        self._client = client

    def _client_for_request(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(), True

    def _validate(self, url: str, method: str) -> httpx.URL:
        parsed = httpx.URL(url)
        if parsed.scheme != "https":
            raise ResearchProviderFetchError(f"Only https is allowed, got scheme={parsed.scheme!r}")
        if method not in self.config.allowed_methods:
            raise ResearchProviderFetchError(f"Method {method!r} is not allowed")
        if parsed.host not in self.config.allowed_domains:
            raise ResearchProviderFetchError(
                f"Domain {parsed.host!r} is not in the allowlist {self.config.allowed_domains}"
            )
        return parsed

    def fetch(self, url: str, request_id: str | None = None, method: str = "GET") -> ResearchFetchResult:
        request_id = request_id or str(uuid.uuid4())

        if self.audit_log.already_succeeded(request_id):
            raise ResearchProviderFetchError(f"request_id {request_id!r} already executed (exactly-once)")

        self._validate(url, method)

        client, should_close = self._client_for_request()
        total = 0
        try:
            with client.stream(method, url, timeout=self.config.timeout_seconds) as response:
                chunks: list[bytes] = []
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.config.max_response_bytes:
                        self.audit_log.record(request_id, url, method, response.status_code, total, "rejected-too-large")
                        raise ResearchProviderFetchError(
                            f"Response exceeded max_response_bytes={self.config.max_response_bytes}"
                        )
                    chunks.append(chunk)
                content = b"".join(chunks).decode("utf-8", errors="replace")
                self.audit_log.record(request_id, url, method, response.status_code, total, "success")
                return ResearchFetchResult(
                    request_id=request_id,
                    url=url,
                    status_code=response.status_code,
                    bytes_read=total,
                    content=content,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
        except httpx.TimeoutException as exc:
            self.audit_log.record(request_id, url, method, None, total, "timeout")
            raise ResearchProviderFetchError(f"Request timed out after {self.config.timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            self.audit_log.record(request_id, url, method, None, total, "transport-error")
            raise ResearchProviderFetchError(f"Transport error: {exc}") from exc
        finally:
            if should_close:
                client.close()
