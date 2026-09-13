"""Exercise real services in fresh processes, not just fresh Python objects.

The changing working directories represent disposable container filesystems;
only the explicitly configured database and application data directory survive.
No model, n8n or notification traffic is allowed in these probes.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
COMMON = """
from app.instagram_content.media_pool_models import (
    FinalizeDraftRequest, MediaPoolIngestRequest,
)
from app.instagram_content.media_pool_service import media_pool_service as pool
from app.instagram_content.models import (
    ContentCandidateCreate, ContentDecision, ContentStatus,
)
from app.instagram_content.service import InstagramContentService, InstagramContentError

def media():
    return MediaPoolIngestRequest(items=[
        dict(media_ref=f'drive-{group}-{i}', media_type='image',
             theme=f'theme-{i}', source_group=f'tag {group}', aesthetic_score=0.8)
        for group in (1, 2) for i in range(3)
    ])
"""

WRITE = (
    COMMON
    + """
class TestPublisher:
    def publish(self, **kwargs):
        return 'test-instagram-receipt'

service = InstagramContentService(publisher=TestPublisher())
service._notify_ready_for_review = lambda item: None
service._record_post_in_knowledge_graph = lambda item: None
assert pool.ingest(media()).ingested == 6
drafts = {d.theme: d for d in pool.run_curation()}
assert set(drafts) == {'tag 1', 'tag 2'}
candidate = service.finalize_draft(
    drafts['tag 1'].id,
    FinalizeDraftRequest(caption_draft='Morning light over the water. A quiet start.'),
)
assert candidate.status == ContentStatus.proposed
service.decide(candidate.id, ContentDecision(approved=True, reason='Reviewed preview'))
assert service.publish(candidate.id).published_media_id == 'test-instagram-receipt'

for ref, caption, approved in (
    ('approved-photo', 'Training finished. Time for a walk outside.', True),
    ('rejected-photo', 'The afternoon sky above the city rooftops.', False),
):
    item = service.propose(ContentCandidateCreate(
        media_items=[dict(media_ref=ref, media_type='image', aesthetic_score=0.9)],
        caption_draft=caption,
    ))
    service.decide(item.id, ContentDecision(approved=approved, reason='Owner decision'))
print('writer-ok')
"""
)

READ = (
    COMMON
    + """
class NeverPublish:
    def publish(self, **kwargs):
        raise AssertionError('Restart must not publish anything')

service = InstagramContentService(publisher=NeverPublish())
items = pool.list_all()
assert len(items) == 6, 'The pool disappeared with the old process/filesystem'
assert {item.source_group for item in items} == {'tag 1', 'tag 2'}
drafts = {d.theme: d for d in pool.list_drafts()}
assert drafts['tag 1'].finalized
assert not drafts['tag 2'].finalized
assert len(pool.list_drafts(pending_only=True)) == 1
for item in items:
    draft = drafts[item.source_group]
    assert item.reserved_in_draft_id == draft.id
    assert not item.available
    assert item.used == (item.source_group == 'tag 1')
    if item.used:
        assert item.used_in_candidate_id == draft.finalized_candidate_id

candidates = service.list_all()
assert len(candidates) == 3
assert {c.status for c in candidates} == {
    ContentStatus.posted, ContentStatus.approved, ContentStatus.rejected,
}
posted = service.get(drafts['tag 1'].finalized_candidate_id)
assert posted.published_media_id == 'test-instagram-receipt'
assert posted.caption_draft == 'Morning light over the water. A quiet start.'
assert any('Reviewed preview' in entry for entry in posted.audit_log)
for candidate in candidates:
    if candidate.status in (ContentStatus.posted, ContentStatus.rejected):
        try:
            service.publish(candidate.id)
        except InstagramContentError:
            pass
        else:
            raise AssertionError('A persisted decision was lost')

duplicate = pool.ingest(media())
assert duplicate.ingested == 0
assert duplicate.skipped_duplicates == 6
assert len(pool.list_all()) == 6
assert pool.run_curation() == [], 'Restart must not reuse reserved/used photos'
print('reader-ok')
"""
)


@pytest.mark.parametrize("variable", ["DATABASE_URL", "JARVIS_DATABASE_URL"])
def test_instagram_state_survives_process_and_workdir_replacement(tmp_path, variable):
    # Only runtime necessities, never inherited provider credentials or .env.
    env = {
        key: value
        for key, value in os.environ.items()
        if key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG")
    }
    env.update(
        PYTHONPATH=str(BACKEND),
        JARVIS_DATA_DIR=str(tmp_path / "persistent-data"),
    )
    env[variable] = f"sqlite:///{(tmp_path / 'persistent.db').as_posix()}"
    for name, script in (("old-container", WRITE), ("new-container", READ)):
        directory = tmp_path / name
        directory.mkdir()
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=directory,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "persistent.db").is_file()
    assert not list(tmp_path.glob("*/jarvis.db")), "No fallback DB in disposable CWD"
