import pytest

from app.documents.auron_documents_readonly_canary_adapter_v21_597 import (
    DocumentsReadonlyCanaryAdapter,DocumentsReadonlyCanaryAdapterError)
from app.core.auron_integration_readiness_v21_597 import get_integration_readiness


def adapter(tmp_path): return DocumentsReadonlyCanaryAdapter(tmp_path/'documents.db')


def test_metadata_inspection_is_local_readonly_and_idempotent(tmp_path):
    a=adapter(tmp_path); kw=dict(vertical='files-documents',provider_id='documents-local-readonly',scope='metadata-only',
        action_key='inspect-file-metadata',payload={'file_id':'f-1'},idempotency_key='k-1')
    ref=a.execute_canary_action(**kw); assert a.execute_canary_action(**kw)==ref
    result=a.read_result(provider_ref=ref); preview=a.preview(ref)
    assert result.state=='completed' and result.external_calls_made==0
    assert preview['metadata_only'] is True and preview['content_read'] is False and preview['mutation_performed'] is False


def test_version_preview_requires_version_and_remains_content_free(tmp_path):
    a=adapter(tmp_path)
    ref=a.execute_canary_action(vertical='files-documents',provider_id='documents-local-readonly',scope='version-preview',
        action_key='preview-file-version',payload={'file_id':'f-1','version_id':'v-7'},idempotency_key='k-2')
    p=a.preview(ref); assert p['version_id']=='v-7' and p['content_read'] is False and p['external_calls_made']==0


def test_mutation_and_content_fields_are_rejected(tmp_path):
    a=adapter(tmp_path)
    for payload in ({'file_id':'f','content':'secret'},{'file_id':'f','delete':True},{'file_id':'f','move':'x'}):
        with pytest.raises(DocumentsReadonlyCanaryAdapterError):
            a.execute_canary_action(vertical='files-documents',provider_id='documents-local-readonly',scope='metadata-only',
                action_key='inspect-file-metadata',payload=payload,idempotency_key=str(payload))


def test_disallowed_action_and_wrong_provider_fail_closed(tmp_path):
    a=adapter(tmp_path)
    with pytest.raises(DocumentsReadonlyCanaryAdapterError):
        a.execute_canary_action(vertical='files-documents',provider_id='documents-local-readonly',scope='x',action_key='delete-file',payload={'file_id':'f'},idempotency_key='x')
    with pytest.raises(DocumentsReadonlyCanaryAdapterError):
        a.execute_canary_action(vertical='files-documents',provider_id='other',scope='x',action_key='inspect-file-metadata',payload={'file_id':'f'},idempotency_key='y')


def test_stop_is_persistent(tmp_path):
    a=adapter(tmp_path); a.stop_canary(activation_id='a1',reason='operator-stop'); assert a.is_stopped('a1') is True


def test_descriptor_and_readiness_keep_external_execution_disabled(tmp_path):
    d=adapter(tmp_path).descriptor(); r=get_integration_readiness()
    assert d.read_only is True and d.mutation_enabled is False and d.delete_enabled is False and d.move_enabled is False
    assert d.network_transport_enabled is False and d.production_transport_enabled is False
    assert r['roadmap_version']=='v21.597' and r['next_item']=='G11-documents-canary-end-to-end-certification'
    assert r['live_transports_enabled'] is False and r['trading_execution_enabled'] is False
