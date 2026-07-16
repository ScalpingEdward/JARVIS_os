import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request
from uuid import UUID

from ..connectors.models import ConnectorKind, ConnectorPermission, ConnectorState
from ..connectors.service import connector_service
from .models import ConnectorImplementationStatus, ConnectorInvocation, ConnectorInvocationResult, ConnectorOperation


class ConnectorRuntimeError(RuntimeError):
    pass


class SecretResolver:
    def resolve(self, reference: str) -> str:
        if not reference.startswith("env:"):
            raise ConnectorRuntimeError("Only env: secret references are supported")
        value = os.getenv(reference.removeprefix("env:"))
        if not value:
            raise ConnectorRuntimeError("Referenced secret is unavailable")
        return value


class ConnectorRuntimeService:
    HTTP_KINDS = {
        ConnectorKind.telegram,
        ConnectorKind.github,
        ConnectorKind.gmail,
        ConnectorKind.google_calendar,
        ConnectorKind.rest_api,
        ConnectorKind.mcp,
        ConnectorKind.mt5,
        ConnectorKind.tradingview,
    }
    FILE_KINDS = {ConnectorKind.local_files, ConnectorKind.obsidian}

    def __init__(self) -> None:
        self._results: list[ConnectorInvocationResult] = []
        self._resolver = SecretResolver()

    def reset(self) -> None:
        self._results.clear()

    def invoke(self, connector_id: UUID, invocation: ConnectorInvocation) -> ConnectorInvocationResult:
        connector = connector_service.get(connector_id)
        if connector is None:
            raise ConnectorRuntimeError("Connector not found")
        if connector.state not in {ConnectorState.healthy, ConnectorState.connecting}:
            raise ConnectorRuntimeError("Connector is not active")
        required = ConnectorPermission(invocation.operation.value) if invocation.operation != ConnectorOperation.health else ConnectorPermission.read
        if required not in connector.permissions:
            raise ConnectorRuntimeError(f"Missing {required.value} permission")
        if invocation.operation == ConnectorOperation.execute and connector.kind in {ConnectorKind.mt5, ConnectorKind.tradingview}:
            raise ConnectorRuntimeError("Trading execution is disabled")

        if connector.kind in self.FILE_KINDS:
            result = self._invoke_file(connector_id, connector.kind, connector.metadata, invocation)
        elif connector.kind in self.HTTP_KINDS:
            result = self._invoke_http(connector_id, connector.kind, connector.metadata, connector.secret_refs, invocation)
        elif connector.kind == ConnectorKind.docker:
            result = ConnectorInvocationResult(connector_id=connector_id, adapter="docker", action=invocation.action, ok=False, error="Docker execution requires a separately approved local worker")
        else:
            result = ConnectorInvocationResult(connector_id=connector_id, adapter=connector.kind.value, action=invocation.action, ok=False, error="Adapter not implemented")
        self._results.append(result)
        connector_service._log(connector_id, "runtime_invocation", invocation.actor, f"{invocation.action}:ok={result.ok}")
        return result

    def _invoke_file(self, connector_id: UUID, kind: ConnectorKind, metadata: dict[str, str], invocation: ConnectorInvocation) -> ConnectorInvocationResult:
        root = Path(metadata.get("root_path", ".")).expanduser().resolve()
        target = (root / (invocation.resource or "")).resolve()
        if root != target and root not in target.parents:
            raise ConnectorRuntimeError("Path escapes connector root")
        if invocation.operation == ConnectorOperation.read:
            data = target.read_text(encoding="utf-8")
        elif invocation.operation == ConnectorOperation.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            data = str(invocation.payload.get("content", ""))
            target.write_text(data, encoding="utf-8")
        else:
            raise ConnectorRuntimeError("File connectors support read and write only")
        return ConnectorInvocationResult(connector_id=connector_id, adapter=kind.value, action=invocation.action, ok=True, data=data)

    def _invoke_http(self, connector_id: UUID, kind: ConnectorKind, metadata: dict[str, str], secret_refs: list[str], invocation: ConnectorInvocation) -> ConnectorInvocationResult:
        base_url = metadata.get("base_url")
        if not base_url or not base_url.startswith(("https://", "http://")):
            raise ConnectorRuntimeError("Connector base_url is missing or invalid")
        path = invocation.resource or ""
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Content-Type": "application/json", "User-Agent": "PHOENIX-Connector/2.8"}
        if secret_refs:
            headers[metadata.get("auth_header", "Authorization")] = metadata.get("auth_prefix", "Bearer ") + self._resolver.resolve(secret_refs[0])
        method = "GET" if invocation.operation in {ConnectorOperation.read, ConnectorOperation.health} else "POST"
        body = None if method == "GET" else json.dumps(invocation.payload).encode("utf-8")
        req = request.Request(url, data=body, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=float(metadata.get("timeout_seconds", "10"))) as response:
                raw = response.read().decode("utf-8")
                try:
                    data: Any = json.loads(raw) if raw else None
                except json.JSONDecodeError:
                    data = raw
                return ConnectorInvocationResult(connector_id=connector_id, adapter=kind.value, action=invocation.action, ok=True, status_code=response.status, data=data)
        except error.HTTPError as exc:
            return ConnectorInvocationResult(connector_id=connector_id, adapter=kind.value, action=invocation.action, ok=False, status_code=exc.code, error=str(exc))
        except error.URLError as exc:
            return ConnectorInvocationResult(connector_id=connector_id, adapter=kind.value, action=invocation.action, ok=False, error=str(exc.reason))

    def history(self, connector_id: UUID | None = None) -> list[ConnectorInvocationResult]:
        return [item for item in self._results if connector_id is None or item.connector_id == connector_id]

    def status(self) -> ConnectorImplementationStatus:
        return ConnectorImplementationStatus(
            supported_adapters=sorted(kind.value for kind in self.HTTP_KINDS | self.FILE_KINDS | {ConnectorKind.docker}),
            registered_connectors=len(connector_service.list_all()),
            invocations=len(self._results),
        )


connector_runtime_service = ConnectorRuntimeService()
