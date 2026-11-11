from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models, report_generations, maintenance_worklist
from app.db import Base
from types import SimpleNamespace


@pytest.fixture
def env():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        a = models.Site(name='a.test', base_url='https://a.test', publication_endpoint='/')
        b = models.Site(name='b.test', base_url='https://b.test', publication_endpoint='/')
        db.add_all([a, b]); db.commit()
        yield db, a, b
    engine.dispose()


def make(db, site, status='generating', percent=15):
    task = models.GenerationTask(title='Task', site_id=site.id, geo='CZ', language='cs')
    db.add(task); db.flush()
    item = models.ContentItem(task_id=task.id, site_id=site.id, topic='Topic', slug='/topic/',
        status=status, generation_progress=percent, competitor_research_progress=100,
        generated_json={'large_payload': 'must not load'}, idempotency_key=str(uuid4()))
    db.add(item); db.commit()
    return task, item


def test_report_only_loads_explicit_tasks_for_same_site(env):
    db, a, b = env
    task, item = make(db, a)
    extra, _ = make(db, a)
    foreign, _ = make(db, b)
    result = report_generations.for_entries(db, [{'site_id': a.id, 'generation_task_ids': [task.id, foreign.id]}])
    assert [r['id'] for r in result[a.id]] == [item.id]
    assert 'generated_json' not in result[a.id][0]


def test_mismatched_task_site_cannot_leak_content(env):
    db, a, b = env
    task, item = make(db, b)
    item.site_id = a.id; db.commit()
    assert report_generations.for_entries(db, [{'site_id': a.id, 'generation_task_ids': [task.id]}]) == {}


def test_failure_with_stored_100_is_not_ready(env):
    db, a, _ = env
    task, item = make(db, a, 'generation_failed', 100)
    row = report_generations.for_entries(db, [{'site_id': a.id, 'generation_task_ids': [task.id]}])[a.id][0]
    assert row['percent'] == 99 and not row['ready']
    assert row['status'] == 'generation_failed'


def test_ready_text_and_live_progress_survive_compact_work_report(env):
    db, a, _ = env
    task, item = make(db, a, 'generated', 15)
    rows = [{'site_id': a.id, 'generation_task_ids': [task.id], 'work_summary': {'done': ['Saved']}}]
    job = SimpleNamespace(payload={})
    result = maintenance_worklist.enrich(job, rows, db)
    assert result[0]['generations'][0]['percent'] == 100
    assert result[0]['generations'][0]['ready']
    assert result[0]['work_summary']['done'] == ['Saved']


def test_unrelated_reports_do_not_query_generation_tables():
    class NoQuery:
        def execute(self, *args):
            raise AssertionError('unexpected query')
    assert report_generations.for_entries(NoQuery(), [{'site_id': 'a'}]) == {}
