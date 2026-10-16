from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.db import Base
from app.project_cache import _confirm_published_content
from app.task_status import refresh_task_status


def test_confirmation_updates_task_with_production_autoflush_disabled():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        site = models.Site(name='status.test', base_url='https://status.test', publication_endpoint='https://status.test/api')
        db.add(site); db.flush()
        task = models.GenerationTask(site_id=site.id, title='Task', geo='CZ', language='cs', status='publication_failed', auto_publish=True)
        db.add(task); db.flush()
        items = [models.ContentItem(task_id=task.id, site_id=site.id, topic=str(i), slug=f'/page-{i}/', generated_json={},
                                    status='published' if i == 0 else 'publication_failed', idempotency_key=f'item-{i}') for i in range(2)]
        db.add_all(items); db.commit()
        confirmed = _confirm_published_content(db, site, {'data': {'pages': [{'slug': '/page-1/'}]}}, datetime.now(timezone.utc))
        assert confirmed == 1
        assert task.status == 'published'
        assert {item.status for item in items} == {'published'}
        db.commit()
        db.refresh(task)
        assert task.status == 'published'
        # A manual retry must update the aggregate before commit, too.
        task.auto_publish = False
        items[1].status = 'publishing'
        refresh_task_status(db, task.id)
        assert task.status == 'publishing'
        items[1].status = 'publication_failed'
        refresh_task_status(db, task.id)
        assert task.status == 'publication_failed'
        items[1].status = 'published'
        refresh_task_status(db, task.id)
        assert task.status == 'published'
