from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, auto_pilot, maintenance_reports, pilot_task_cache
from app.report_list_visibility import hide, hidden_ids, PREFIX
from test_pilot_task_cache import session

USER = {'username': 'anton', 'allowed_site_ids': None}


def report(db):
    site = models.Site(name='sample.test', base_url='https://sample.test', publication_endpoint='/publish')
    db.add(site); db.commit()
    job = maintenance_reports.upsert(db, str(uuid4()), 'Showcase work', 'anton', [site.id],
        [{'site_id':site.id, 'status':'running', 'plan':{'actions':['Write content']}}])
    return site, job


def test_remove_report_from_list_preserves_running_work_and_direct_report():
    with session() as db:
        site, job = report(db)
        before = (job.status, deepcopy(job.payload), deepcopy(job.result))
        assert auto_pilot.tasks(db, USER)['total'] == 1
        assert hide(db, job.id, USER) == {'id':job.id, 'deleted':True}
        assert auto_pilot.tasks(db, USER)['total'] == 0
        assert maintenance_reports.get(db, job.id, USER) is job
        assert (job.status, job.payload, job.result) == before


def test_hide_is_idempotent_and_worker_update_cannot_restore_list_entry():
    with session() as db:
        site, job = report(db)
        hide(db, job.id, USER); hide(db, job.id, USER)
        assert len(list(db.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.startswith(PREFIX))))) == 1
        maintenance_reports.upsert(db, job.id, job.payload['name'], 'anton', [site.id],
            [{'site_id':site.id, 'status':'completed'}], status='completed')
        assert auto_pilot.tasks(db, USER)['total'] == 0


def test_hide_checks_report_owner():
    with session() as db:
        site, job = report(db)
        with pytest.raises(ValueError):hide(db, job.id, {'username':'other', 'allowed_site_ids':None})
        assert not hidden_ids(db, 'anton')


def test_hide_checks_project_permissions():
    with session() as db:
        site, job = report(db)
        with pytest.raises(ValueError):hide(db, job.id, {'username':'anton', 'allowed_site_ids':[]})
        assert not hidden_ids(db, 'anton')


def test_hide_invalidates_persistent_list_cache():
    with session() as db:
        site, job = report(db)
        assert pilot_task_cache.tasks(db, USER)['total'] == 1
        hide(db, job.id, USER)
        assert pilot_task_cache.tasks(db, USER)['total'] == 0
