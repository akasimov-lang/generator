from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select
from app import models, auto_pilot as pilot, mass_reglue_launch as launch
from app import pilot_saved_headings as saved, pilot_text_jobs, pilot_replanning
from app.pilot_scope import selection
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_pilot_variations import make_preview, USER


def ready(db, site, *, mode='minimal', short=False, title='TestBrand ready title'):
    draft = models.ProjectPageDraft(site_id=site.id, page_key='1', requested_by='test',
        action='auto_title_h1_preview', status='ready', input_content={'blocks': []},
        input_metadata={'title_rewrite_mode': mode, 'short_h1': short},
        result_content={'blocks': []}, result_metadata={'title_rewrite_mode': mode,
            'short_h1': short, 'short_h1_reviewed': True, 'meaning_reviewed': True})
    db.add(draft); db.flush()
    return {'draft_id': draft.id, 'mode': mode, 'short_h1': short, 'h1_rule_version': 2,
        'title_before': 'TestBrand old title', 'title_after': title,
        'h1_before': 'TestBrand original heading', 'h1_after': 'TestBrand games'}


def rebuild(db, job, **options):
    shares = {**job.payload['percentages'], **options.pop('shares', {})}
    pilot_replanning.request(db, job.id, uuid4(), USER, scope=selection(), percentages=shares,
        title_rewrite_mode=options.pop('mode', job.payload['title_rewrite_mode']), **options)
    for _ in range(10):
        launch.execute_step(db, job.id, lambda _: pytest.fail('Planning cannot launch a site'))
        if job.status == 'completed': return
    pytest.fail('Replanning did not finish')


def plans(job):
    return {p['site_id']: p for group in job.result['groups'] for p in group.get('plans', [])}


@pytest.fixture
def prepared(pool, monkeypatch):
    calls = []
    def generate(db, site, request, **kwargs):
        calls.append((site.id, str(request)))
        return ready(db, site, mode=kwargs.get('mode', 'minimal'), short=kwargs.get('short_h1', False),
                     title=f'TestBrand prepared title {len(calls)}')
    monkeypatch.setattr('app.reglue_title_h1.prepare_preview', generate)
    db, sites, remotes, job = make_preview(pool, 10)
    assert calls
    return db, sites, remotes, job, calls


def test_global_replan_preserves_reviewed_headings_without_new_generation(prepared):
    db, sites, remotes, job, calls = prepared
    before = {sid: deepcopy(p['title_h1_preview']) for sid, p in plans(job).items() if p.get('title_h1_preview')}
    count = len(calls)
    rebuild(db, job, shares={'redirects': 80})
    assert len(calls) == count
    for sid, preview in before.items():
        assert plans(job)[sid]['title_h1_preview'] == preview
        assert pilot.heading_mode_ready(db, plans(job)[sid], job.payload['title_rewrite_mode'])
    assert all(not remote.calls for remote in remotes.values())
    assert not list(db.scalars(select(models.AutoReglueRun)))


def test_replan_mode_change_keeps_existing_mode_until_explicit_row_refresh(prepared):
    db, sites, remotes, job, calls = prepared
    original = {sid: deepcopy(p) for sid, p in plans(job).items() if p.get('title_h1_preview')}
    count = len(calls)
    rebuild(db, job, mode='full_all')
    assert len(calls) == count
    sid = next(iter(original))
    assert plans(job)[sid]['title_rewrite_mode'] == original[sid]['title_rewrite_mode']
    assert pilot.heading_mode_ready(db, plans(job)[sid], 'full_all')
    neighbours = {key: deepcopy(value) for key, value in plans(job).items() if key != sid}
    pilot.refresh_row(db, job.id, sid, uuid4(), USER)
    changed = plans(job)[sid]
    assert len(calls) == count + 1 and changed['title_rewrite_mode'] == 'full_all'
    assert changed['title_h1_preview']['draft_id'] != original[sid]['title_h1_preview']['draft_id']
    assert changed['alternateMarkup'] != original[sid]['alternateMarkup']
    assert not changed.get('title_h1_reused')
    assert {key: value for key, value in plans(job).items() if key != sid} == neighbours
    regenerated = deepcopy(changed['title_h1_preview'])
    rebuild(db, job)
    assert len(calls) == count + 1 and plans(job)[sid]['title_h1_preview'] == regenerated


def test_disabling_and_reenabling_heading_share_does_not_discard_generated_text(prepared):
    db, sites, remotes, job, calls = prepared
    count = len(calls)
    before = {sid: deepcopy(p['title_h1_preview']) for sid, p in plans(job).items() if p.get('title_h1_preview')}
    old_share = job.payload['percentages']['title_h1']
    rebuild(db, job, shares={'title_h1': 0})
    assert len(calls) == count and not any(p['rewrite_title_h1'] for p in plans(job).values())
    rebuild(db, job, shares={'title_h1': old_share})
    assert len(calls) == count
    assert {sid: p['title_h1_preview'] for sid, p in plans(job).items() if p.get('title_h1_preview')} == before


def test_completed_uncollected_text_is_saved_before_replanning(env):
    db, site, remote = env
    plan = {'site_id': site.id, 'rewrite_title_h1': True, 'title_rewrite_mode': 'minimal', 'short_h1': False}
    parent = models.BackgroundJob(kind=launch.PREVIEW_KIND, status='queued', payload={},
        result={'groups': [{'plans': [plan]}]})
    db.add(parent); db.flush()
    preview = ready(db, site)
    child = models.BackgroundJob(id=pilot_text_jobs.identity(parent, plan, 'title_h1'), kind='pilot_text',
        status='completed', payload={}, result={'preview': preview})
    db.add(child); db.commit()
    cached = saved.capture(db, parent, parent.result)
    new_plan = {**plan, 'new_main': 'different.test'}
    saved.restore(db, {saved.CACHE: cached}, new_plan)
    assert new_plan['title_h1_preview'] == preview and new_plan['new_main'] == 'different.test'
    assert not new_plan.get('title_h1_error')


def test_foreign_draft_is_never_treated_as_ready_or_regenerated(env):
    db, site, remote = env
    preview = ready(db, site)
    plan = {'site_id': str(uuid4()), 'rewrite_title_h1': True, 'title_rewrite_mode': 'minimal'}
    saved.restore(db, {saved.CACHE: {plan['site_id']: {'generation_id': str(uuid4()), 'title_h1_preview': preview}}}, plan)
    assert plan['title_h1_error'] and not pilot.heading_mode_ready(db, plan)


def test_missing_project_is_not_filled_from_another_projects_cache(env):
    db, site, remote = env
    plan = {'site_id': site.id, 'rewrite_title_h1': True}
    saved.restore(db, {saved.CACHE: {str(uuid4()): {'title_h1_preview': ready(db, site)}}}, plan)
    assert 'title_h1_preview' not in plan


def test_increased_heading_share_generates_only_projects_without_saved_metadata(prepared):
    db, sites, remotes, job, calls = prepared
    already = {sid for sid, p in plans(job).items() if p.get('title_h1_preview')}
    count = len(calls)
    rebuild(db, job, shares={'title_h1': 100})
    generated = [sid for sid, request in calls[count:]]
    assert len(generated) == len(plans(job)) - len(already)
    assert not already.intersection(generated)
    assert all(p.get('title_h1_preview') for p in plans(job).values())


def test_changed_project_language_keeps_old_result_visible_but_requires_explicit_refresh(env):
    db, site, remote = env
    preview = ready(db, site)
    plan = {'site_id': site.id, 'rewrite_title_h1': True, 'language': 'de'}
    saved.restore(db, {saved.CACHE: {site.id: {'generation_id': str(uuid4()),
        'language': 'pl', 'title_h1_preview': preview}}}, plan)
    assert plan['title_h1_preview'] == preview and plan['title_h1_error']
    assert not pilot.heading_mode_ready(db, plan)
