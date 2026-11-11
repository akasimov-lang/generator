from copy import deepcopy
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app import models, showcase_cache as cache
from app.db import Base


def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    return Session(engine)


def site(db):
    s = models.Site(name='showcase.example', base_url='https://main.example', publication_endpoint='https://main.example/api', external_project_id='showcase-id')
    db.add(s); db.commit()
    return s


def project(brands=('Alpha', 'Beta Casino', 'Beta')):
    return {'id': 'showcase-id', 'name': 'showcase.example', 'settings': {'canon': 'main.example', 'domains': ['main.example']}, 'layout': '',
            'shortcodes': [{'name': 'offers.hbs', 'data': '{{#each casinos.offers}}<strong>{{findValueInObjectByKey this "brand" "value" false}}</strong>{{/each}}'}],
            'data': {'menu': {'header': [], 'footer': []}, 'pages': [{'slug': '/', 'content': {'blocks': [{'type': 'shortcode', 'data': {'shortcode': 'offers'}}]}}],
                     'casinos': {'offers': [[{'key': 'brand', 'type': 'text', 'value': name}] for name in brands]}}}


def test_count_persists_across_sessions_and_deduplicates_connected_brands():
    with session() as db:
        s = site(db); sid = s.id
        assert cache.capture(db, s, project())
        db.commit(); db.expunge_all(); db.info.clear()
        assert cache.cached(db, db.get(models.Site, sid))['count'] == 2


def test_changed_source_updates_count_and_change_time():
    with session() as db:
        s = site(db); before = datetime(2026, 11, 7, tzinfo=timezone.utc); after = before + timedelta(minutes=5)
        cache.capture(db, s, project(), at=before); db.commit()
        cache.capture(db, s, project(('Alpha',)), at=after); db.commit()
        value = cache.cached(db, s)
        assert value['count'] == 1
        assert value['changed_at'] == after.isoformat()


def test_unchanged_refresh_preserves_change_time():
    with session() as db:
        s = site(db); before = datetime(2026, 11, 7, tzinfo=timezone.utc); after = before + timedelta(minutes=5)
        cache.capture(db, s, project(), at=before); db.commit()
        cache.capture(db, s, project(), at=after); db.commit()
        value = cache.cached(db, s)
        assert value['changed_at'] == before.isoformat()
        assert value['checked_at'] == after.isoformat()


def test_partial_cache_keeps_confirmed_count_and_queues_only_one_read():
    with session() as db:
        s = site(db); cache.capture(db, s, project()); db.commit()
        partial = project(('Changed',)); partial.pop('shortcodes')
        assert not cache.capture(db, s, partial); db.commit()
        assert not cache.capture(db, s, partial); db.commit()
        assert cache.cached(db, s)['count'] == 2
        assert len(db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == cache.KIND)).all()) == 1


def test_confirmed_removal_changes_count_to_zero():
    with session() as db:
        s = site(db); cache.capture(db, s, project()); db.commit()
        p = project(); p['data']['pages'][0]['content']['blocks'] = []
        cache.capture(db, s, p); db.commit()
        assert cache.cached(db, s)['count'] == 0


def test_missing_native_data_is_unknown_not_zero():
    p = project(); p['data'].pop('casinos')
    assert cache.summary(p) is None


def test_external_widget_is_unknown_not_empty():
    p = project(); p['shortcodes'][0]['data'] = '<iframe src="https://external.example/casino"></iframe>'
    assert cache.summary(p)['count'] is None
    assert cache.summary(p)['presence'] == 'external'


def test_raw_cards_are_cached_without_counting_unused_gallery():
    p = project(); p['data']['pages'][0]['content']['blocks'] = [{'type': 'raw', 'data': {'html': '<div class="casino-card"><h3>Visible</h3><div class="bonus-value">100 PLN</div></div>'}}]
    assert cache.summary(p)['brands'] == ['Visible']


def test_full_cache_sync_persists_showcase(monkeypatch):
    from app.project_cache import sync_project_cache
    monkeypatch.setattr('app.project_cache._working_project_canons', lambda: set())
    with session() as db:
        s = site(db); sync_project_cache(db, [project()])
        assert cache.cached(db, s)['count'] == 2


def test_direct_refresh_persists_showcase():
    from app.project_cache import _apply_direct_project_snapshot
    with session() as db:
        s = site(db); _apply_direct_project_snapshot(db, s, project())
        assert cache.cached(db, s)['count'] == 2


def test_stream_update_persists_showcase():
    from app.project_cache import sync_project_data_update
    with session() as db:
        s = site(db); sync_project_data_update(db, s.name, project())
        assert cache.cached(db, s)['count'] == 2


def test_list_and_serialization_use_saved_value_without_remote_reads(monkeypatch):
    from app.api import list_sites, list_cached_projects
    from app.schemas import SiteResponse
    def forbidden(*args, **kwargs):
        raise AssertionError('List must not access Webdev')
    monkeypatch.setattr('app.project_pages.fetch_project_cache', forbidden)
    monkeypatch.setattr('app.project_network.Remote.project', forbidden)
    with session() as db:
        s = site(db); cache.capture(db, s, project()); db.commit(); db.expunge_all(); db.info.clear()
        rows = list_sites({}, db)
        assert SiteResponse.model_validate(rows[0]).cache_showcase['count'] == 2
        assert SiteResponse.model_validate(list_cached_projects({}, db)[0]).cache_showcase['count'] == 2


def test_refresh_job_reads_current_source_and_persists_changes(monkeypatch):
    from app.background_jobs import run_job
    class Remote:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def project(self): return project(('New brand',))
    monkeypatch.setattr('app.project_network.Remote', Remote)
    with session() as db:
        s = site(db); cache.capture(db, s, project()); db.commit(); cache.enqueue(db, s); db.commit()
        job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.kind == cache.KIND))
        run_job(db, job.id)
        assert job.status == 'completed'
        assert cache.cached(db, s)['brands'] == ['New brand']


def test_unavailable_server_is_not_requeued_by_every_cache_refresh():
    with session() as db:
        s = site(db); cache.enqueue(db, s); db.commit()
        job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.kind == cache.KIND))
        job.status = 'failed'; job.error = 'HTTP 502'; job.finished_at = datetime.now(timezone.utc)
        db.commit()
        cache.enqueue(db, s); db.commit()
        assert job.status == 'failed' and job.error == 'HTTP 502'


def test_failed_refresh_can_retry_after_cooldown():
    with session() as db:
        s = site(db); cache.enqueue(db, s); db.commit()
        job = db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.kind == cache.KIND))
        job.status = 'failed'; job.error = 'HTTP 502'; job.finished_at = datetime.now(timezone.utc)-timedelta(minutes=16)
        db.commit()
        cache.enqueue(db, s); db.commit()
        assert job.status == 'queued' and job.error is None


def test_empty_shortcode_placeholder_does_not_invalidate_connected_showcase():
    p = project(('Alpha',))
    p['data']['pages'][0]['content']['blocks'].append({'type':'shortcode','data':{'shortcode':''}})
    assert cache.summary(p)['count'] == 1


def test_named_missing_template_still_blocks_false_empty_count():
    p = project(('Alpha',))
    p['data']['pages'][0]['content']['blocks'].append({'type':'shortcode','data':{'shortcode':'missing-offers'}})
    assert cache.summary(p) is None
