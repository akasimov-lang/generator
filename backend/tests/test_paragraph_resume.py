from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models, reglue_paragraphs as paragraphs, pilot_text_jobs, pilot_internal_pages
from app.db import Base
from app.project_network import NetworkBusy


@pytest.fixture
def state():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        site = models.Site(name='brand.test', brand='Brand', cache_geo='PL', base_url='https://brand.test', publication_endpoint='/projects/update')
        provider = models.AiProvider(name='test', provider_type='gemini', api_key='test', endpoint_url='https://test.invalid', model='test')
        db.add_all([site, provider]); db.commit()
        content = {'blocks': [{'id': str(i), 'type': 'paragraph', 'data': {'text': f'Original paragraph {i} for Brand.'}} for i in range(13)]}
        project = {'data': {'pages': [{'id': '1', 'slug': '/', 'title': 'Brand', 'content': content}]}}
        yield db, site, project


def response(value):
    return {'candidates': [{'content': {'parts': [{'text': json.dumps(value)}]}}]}


def test_interrupted_rewrite_resumes_only_reviewed_chunks_and_reuses_ready_draft(state, monkeypatch):
    db, site, project = state
    request_id = uuid4(); calls = []
    class WorkerExit(BaseException): pass
    async def interrupted(provider, prompt):
        calls.append(prompt)
        if len(calls) == 3: raise WorkerExit()
        if 'SOURCE_DATA=' in prompt:
            data = json.loads(prompt.split('SOURCE_DATA=')[1])
            return response({'items': [{'id': x['id'], 'text': x['text'].replace('Original', 'Rewritten')} for x in data['items']]})
        return response({'approved': True, 'language_preserved': True, 'issues': []})
    monkeypatch.setattr('app.services.call_gemini', interrupted)
    with pytest.raises(WorkerExit):
        paragraphs.prepare_preview(db, site, request_id, project=project)
    draft_id = str(uuid5(request_id, site.id + f':paragraphs-preview:v{paragraphs.RULE_VERSION}'))
    draft = db.get(models.ProjectPageDraft, draft_id)
    assert draft.status == 'generating'
    assert len(draft.result_metadata['paragraph_checkpoint']['items']) == 12
    before = deepcopy(draft.input_content)
    resumed_ids = []
    async def resumed(provider, prompt):
        if 'SOURCE_DATA=' in prompt:
            data = json.loads(prompt.split('SOURCE_DATA=')[1]); resumed_ids.extend(x['id'] for x in data['items'])
            return response({'items': [{'id': x['id'], 'text': x['text'].replace('Original', 'Rewritten')} for x in data['items']]})
        return response({'approved': True, 'language_preserved': True, 'issues': []})
    monkeypatch.setattr('app.services.call_gemini', resumed)
    monkeypatch.setattr(paragraphs.pages, 'Remote', lambda *_: pytest.fail('resume must use saved input'))
    result = paragraphs.prepare_preview(db, site, request_id)
    assert resumed_ids == [12] and result['count'] == 13
    assert draft.status == 'ready' and draft.result_metadata['meaning_reviewed'] is True
    assert draft.input_content == before
    assert all('Rewritten' in b['data']['text'] for b in draft.result_content['blocks'])
    monkeypatch.setattr('app.services.call_gemini', lambda *_: pytest.fail('ready draft is reused'))
    assert paragraphs.prepare_preview(db, site, request_id) == result


def test_unreviewed_or_invalid_output_is_not_checkpointed(state, monkeypatch):
    db, site, project = state
    request_id = uuid4()
    async def rejected(provider, prompt):
        if 'SOURCE_DATA=' in prompt:
            data = json.loads(prompt.split('SOURCE_DATA=')[1])
            return response({'items': [{'id': x['id'], 'text': x['text'].replace('Original', 'Rewritten')} for x in data['items']]})
        return response({'approved': False, 'language_preserved': True, 'issues': [{'id': 0, 'reason': 'Wrong offer'}]})
    monkeypatch.setattr('app.services.call_gemini', rejected)
    with pytest.raises(ValueError, match='Wrong offer'):
        paragraphs.prepare_preview(db, site, request_id, project=project)
    draft = db.get(models.ProjectPageDraft, str(uuid5(request_id, site.id + f':paragraphs-preview:v{paragraphs.RULE_VERSION}')))
    assert draft.status == 'failed' and not (draft.result_metadata or {}).get('paragraph_checkpoint')


def test_busy_draft_stays_queued_without_false_generation_error(state, monkeypatch):
    db, site, _ = state
    parent = models.BackgroundJob(kind='mass_reglue_list', status='queued', payload={}, result={})
    db.add(parent); db.flush()
    child = models.BackgroundJob(kind='pilot_text', status='queued', payload={'parent_id': parent.id, 'generation_id': str(uuid4()),
        'site_id': site.id, 'field': 'paragraphs', 'plan': {'site_id': site.id, 'rewrite_paragraphs': True}})
    db.add(child); db.commit()
    monkeypatch.setattr(pilot_text_jobs, 'current', lambda *_: parent)
    @contextmanager
    def busy(*args):
        raise NetworkBusy('Already generating')
        yield
    monkeypatch.setattr(paragraphs, 'network_lock', busy)
    assert pilot_text_jobs.execute(db, child.id) == {'status': 'busy'}
    db.refresh(child)
    assert child.status == 'queued' and child.error is None and not child.finished_at


def test_completed_pages_clear_previous_branch_error(monkeypatch):
    job = SimpleNamespace(status='failed', error='Scope changed', payload={'plan': {'count': 1}},
        result={'count': 1}, updated_at=None, finished_at=None)
    item = SimpleNamespace(status='published', published_at=__import__('datetime').datetime.now(), generated_at=None, updated_at=None)
    task = SimpleNamespace(id='task', items=[item], archived_at=None, updated_at=None)
    monkeypatch.setattr(pilot_internal_pages, '_task', lambda *_: task)
    result = pilot_internal_pages.snapshot(SimpleNamespace(get=lambda *_: job), str(uuid4()), str(uuid4()))
    assert result['status'] == 'completed' and result['reason'] is None and result['published'] == 1
