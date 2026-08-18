import pytest

from app.documents.auron_documents_registry_state_v21_573 import (
    DocumentsRegistryError,
    DocumentsRegistryStateStore,
)
from app.core.auron_integration_readiness_v21_573 import get_integration_readiness


def test_file_folder_version_state_is_persistent_and_normalized(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path / 'documents.sqlite3')
    root = store.observe_item(provider_id='p', provider_item_ref='root', kind='folder', name='Root')
    file_item = store.observe_item(provider_id='p', provider_item_ref='file-1', kind='file',
                                   name='Report.pdf', parent_item_id=root.item_id,
                                   mime_type='application/pdf', metadata={'owner': 'me'})
    version = store.observe_version(item_id=file_item.item_id, provider_version_ref='v1',
                                    content_hash='abc', size_bytes=123,
                                    modified_at='2026-08-18T08:00:00+00:00')
    assert store.get_item(file_item.item_id).current_version_id == version.version_id
    assert store.list_children(root.item_id) == (store.get_item(file_item.item_id),)
    assert store.list_versions(file_item.item_id) == (version,)


def test_item_identity_is_stable_across_observations(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path / 'documents.sqlite3')
    first = store.observe_item(provider_id='p', provider_item_ref='x', kind='file', name='A.txt')
    second = store.observe_item(provider_id='p', provider_item_ref='x', kind='file', name='Renamed.txt')
    assert first.item_id == second.item_id
    assert store.get_item(first.item_id).name == 'Renamed.txt'


def test_version_identity_reuse_with_changed_payload_fails_closed(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path / 'documents.sqlite3')
    item = store.observe_item(provider_id='p', provider_item_ref='x', kind='file', name='A.txt')
    store.observe_version(item_id=item.item_id, provider_version_ref='v1', content_hash='one')
    with pytest.raises(DocumentsRegistryError):
        store.observe_version(item_id=item.item_id, provider_version_ref='v1', content_hash='two')


def test_cross_provider_parent_is_rejected(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path / 'documents.sqlite3')
    parent = store.observe_item(provider_id='p1', provider_item_ref='root', kind='folder', name='Root')
    with pytest.raises(DocumentsRegistryError):
        store.observe_item(provider_id='p2', provider_item_ref='child', kind='file',
                           name='A.txt', parent_item_id=parent.item_id)


def test_folder_cannot_receive_file_version(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path / 'documents.sqlite3')
    folder = store.observe_item(provider_id='p', provider_item_ref='root', kind='folder', name='Root')
    with pytest.raises(DocumentsRegistryError):
        store.observe_version(item_id=folder.item_id, provider_version_ref='v1')


def test_snapshot_is_read_only_and_zero_external_calls(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path / 'documents.sqlite3')
    store.observe_item(provider_id='p', provider_item_ref='root', kind='folder', name='Root')
    snap = store.snapshot('p')
    assert snap['write_enabled'] is False
    assert snap['delete_enabled'] is False
    assert snap['external_calls_made'] == 0


def test_d26_readiness_advances_to_read_integration():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.573'
    assert readiness['next_item'] == 'D27-documents-read-list-search-fetch-integration'
    assert readiness['documents_write_enabled'] is False
    assert readiness['documents_delete_enabled'] is False
    assert readiness['documents_move_enabled'] is False
