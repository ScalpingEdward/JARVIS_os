from pathlib import Path

import pytest

from app.connector_runtime.models import ConnectorInvocation, ConnectorOperation
from app.connector_runtime.service import ConnectorRuntimeError, connector_runtime_service
from app.connectors.models import ConnectorAction, ConnectorCreate, ConnectorKind, ConnectorPermission
from app.connectors.service import connector_service


def setup_function() -> None:
    connector_service.reset()
    connector_runtime_service.reset()


def test_local_file_connector_reads_and_writes_inside_root(tmp_path: Path) -> None:
    connector = connector_service.create(
        ConnectorCreate(
            name="vault",
            kind=ConnectorKind.obsidian,
            permissions={ConnectorPermission.read, ConnectorPermission.write},
            metadata={"root_path": str(tmp_path)},
        )
    )
    connector_service.transition(connector.id, ConnectorAction(action="enable"))

    written = connector_runtime_service.invoke(
        connector.id,
        ConnectorInvocation(operation=ConnectorOperation.write, action="write_note", resource="Trading/XAUUSD.md", payload={"content": "# XAUUSD"}),
    )
    assert written.ok is True

    read = connector_runtime_service.invoke(
        connector.id,
        ConnectorInvocation(operation=ConnectorOperation.read, action="read_note", resource="Trading/XAUUSD.md"),
    )
    assert read.data == "# XAUUSD"


def test_path_traversal_is_blocked(tmp_path: Path) -> None:
    connector = connector_service.create(
        ConnectorCreate(name="files", kind=ConnectorKind.local_files, permissions={ConnectorPermission.read}, metadata={"root_path": str(tmp_path)})
    )
    connector_service.transition(connector.id, ConnectorAction(action="enable"))
    with pytest.raises(ConnectorRuntimeError, match="escapes"):
        connector_runtime_service.invoke(
            connector.id,
            ConnectorInvocation(operation=ConnectorOperation.read, action="read", resource="../secret.txt"),
        )


def test_trading_execution_is_always_blocked() -> None:
    connector = connector_service.create(
        ConnectorCreate(
            name="mt5",
            kind=ConnectorKind.mt5,
            permissions={ConnectorPermission.read, ConnectorPermission.execute},
            metadata={"base_url": "http://127.0.0.1:9999"},
        )
    )
    connector_service.transition(connector.id, ConnectorAction(action="enable"))
    with pytest.raises(ConnectorRuntimeError, match="Trading execution is disabled"):
        connector_runtime_service.invoke(
            connector.id,
            ConnectorInvocation(operation=ConnectorOperation.execute, action="place_order"),
        )


def test_secret_resolver_rejects_raw_secrets() -> None:
    connector = connector_service.create(
        ConnectorCreate(
            name="github",
            kind=ConnectorKind.github,
            permissions={ConnectorPermission.read},
            secret_refs=["raw-token"],
            metadata={"base_url": "https://api.github.com"},
        )
    )
    connector_service.transition(connector.id, ConnectorAction(action="enable"))
    with pytest.raises(ConnectorRuntimeError, match="env:"):
        connector_runtime_service.invoke(
            connector.id,
            ConnectorInvocation(operation=ConnectorOperation.read, action="repo", resource="repos/example/example"),
        )


def test_status_lists_concrete_adapters() -> None:
    status = connector_runtime_service.status()
    assert "telegram" in status.supported_adapters
    assert "github" in status.supported_adapters
    assert "obsidian" in status.supported_adapters
    assert status.automatic_order_execution is False
    assert status.automatic_merge is False
