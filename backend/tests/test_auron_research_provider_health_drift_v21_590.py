from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest

from app.research.auron_research_readonly_canary_adapter_v21_588 import ResearchReadonlyCanaryAdapter
from app.research.auron_research_provider_health_drift_v21_590 import ResearchProviderHealthDriftCertification
from app.core.auron_integration_readiness_v21_590 import get_integration_readiness


def test_fresh_healthy_matching_evidence_certifies(tmp_path):
    d=ResearchReadonlyCanaryAdapter(tmp_path/'a.db').descriptor(); c=ResearchProviderHealthDriftCertification(tmp_path/'h.db')
    now=datetime.now(timezone.utc); e=c.record(d,healthy=True,observed_at=now.isoformat())
    result=c.certify(e.evidence_id,d,now=(now+timedelta(seconds=10)).isoformat())
    assert result.certified is True and result.stale is False and result.drift_detected is False


def test_stale_evidence_fails_closed(tmp_path):
    d=ResearchReadonlyCanaryAdapter(tmp_path/'a.db').descriptor(); c=ResearchProviderHealthDriftCertification(tmp_path/'h.db',max_age_seconds=60)
    now=datetime.now(timezone.utc); e=c.record(d,healthy=True,observed_at=(now-timedelta(seconds=61)).isoformat())
    result=c.certify(e.evidence_id,d,now=now.isoformat())
    assert result.certified is False and 'health-evidence-stale' in result.blockers


def test_unhealthy_provider_fails_closed(tmp_path):
    d=ResearchReadonlyCanaryAdapter(tmp_path/'a.db').descriptor(); c=ResearchProviderHealthDriftCertification(tmp_path/'h.db')
    e=c.record(d,healthy=False); result=c.certify(e.evidence_id,d)
    assert result.certified is False and 'provider-unhealthy' in result.blockers


def test_adapter_configuration_drift_is_detected(tmp_path):
    d=ResearchReadonlyCanaryAdapter(tmp_path/'a.db').descriptor(); c=ResearchProviderHealthDriftCertification(tmp_path/'h.db')
    e=c.record(d,healthy=True); changed=replace(d,allowed_actions=d.allowed_actions+('new-action',))
    result=c.certify(e.evidence_id,changed)
    assert result.certified is False and result.drift_detected is True and 'adapter-config-drift' in result.blockers


def test_missing_evidence_fails_closed(tmp_path):
    d=ResearchReadonlyCanaryAdapter(tmp_path/'a.db').descriptor(); c=ResearchProviderHealthDriftCertification(tmp_path/'h.db')
    result=c.certify('missing',d); assert result.certified is False and 'health-evidence-missing' in result.blockers
    with pytest.raises(RuntimeError): c.require_certified(result)


def test_g3_readiness_advances_to_g4():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.590'
    assert r['next_item']=='G4-provider-specific-canary-command-centre-controls'
    assert r['live_transports_enabled'] is False
