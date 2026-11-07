from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import models
from app.weekly_digest_review import unresolved
from test_project_network import env

START = datetime(2026, 11, 1, 21, tzinfo=timezone.utc)
END = START + timedelta(days=7)
AT = START + timedelta(days=3)


def parent(db, site, *, status='completed', payload=None, result=None):
    row = models.BackgroundJob(id=str(uuid4()), kind='mass_reglue_list', status=status,
        payload=payload or {'site_ids': [site.id]}, result=result or {}, created_at=AT, updated_at=AT)
    db.add(row); db.flush()
    return row


def job(db, site, owner, kind='pilot_text', status='failed', at=AT, **payload):
    row = models.BackgroundJob(id=str(uuid4()), kind=kind, status=status,
        payload={'parent_id': owner.id, 'site_id': site.id, 'field': 'paragraphs', **payload},
        result={}, created_at=at, updated_at=at)
    db.add(row); db.flush()
    return row


def run(db, site, owner, *, status='failed', at=AT):
    row = models.AutoReglueRun(id=str(uuid4()), site_id=site.id, initiator='test', status=status,
        plan={'list_launch_id': owner.id}, created_at=at, updated_at=at)
    db.add(row); db.flush()
    return row


def test_generation_and_publication_error_count_as_one_logical_task(env):
    db, site, _ = env; owner = parent(db, site)
    job(db, site, owner)
    job(db, site, owner, 'pilot_content_publication', at=AT + timedelta(minutes=1))
    db.commit()
    refs = unresolved(db, START, END)
    assert len(refs) == 1 and refs[0]['kind'] == 'text' and refs[0]['site_id'] == site.id


def test_independent_heading_and_paragraph_tasks_are_not_collapsed(env):
    db, site, _ = env; owner = parent(db, site)
    job(db, site, owner, field='paragraphs')
    job(db, site, owner, field='title_h1')
    db.commit()
    assert len(unresolved(db, START, END)) == 2


def test_successful_retry_suppresses_older_failed_attempt(env):
    db, site, _ = env; owner = parent(db, site)
    job(db, site, owner)
    job(db, site, owner, 'pilot_content_publication', 'completed', AT + timedelta(minutes=1))
    db.commit()
    assert unresolved(db, START, END) == []


def test_new_failure_after_success_still_requires_review(env):
    db, site, _ = env; owner = parent(db, site)
    job(db, site, owner, 'pilot_content_publication', 'completed')
    job(db, site, owner, at=AT + timedelta(minutes=1))
    db.commit()
    assert len(unresolved(db, START, END)) == 1


def test_cancelled_parent_excludes_descendant_errors(env):
    db, site, _ = env; owner = parent(db, site, status='cancelled')
    job(db, site, owner); run(db, site, owner)
    db.commit()
    assert unresolved(db, START, END) == []


def test_deleted_plan_tombstone_excludes_descendants(env):
    db, site, _ = env; owner = parent(db, site)
    job(db, site, owner); run(db, site, owner)
    db.add(models.AutoReglueConfig(key='pilot-cancel:' + owner.id, value={'deleted': True})); db.commit()
    assert unresolved(db, START, END) == []


def test_cancelled_site_row_excludes_only_that_projects_work(env):
    db, site, _ = env; owner = parent(db, site, result={'items': {site.id: {'status': 'cancelled'}}})
    job(db, site, owner); run(db, site, owner)
    db.commit()
    assert unresolved(db, START, END) == []


def test_week_uses_half_open_interval_and_ignores_old_errors(env):
    db, site, _ = env; owner = parent(db, site)
    job(db, site, owner, field='old', at=START - timedelta(microseconds=1))
    job(db, site, owner, field='next_week', at=END)
    job(db, site, owner, field='this_week', at=START)
    db.commit()
    refs = unresolved(db, START, END)
    assert len(refs) == 1 and refs[0]['key'].endswith(':this_week')


def test_current_run_pointer_excludes_replaced_failed_run(env):
    db, site, _ = env; owner = parent(db, site)
    run(db, site, owner)
    current = run(db, site, owner, status='completed', at=AT + timedelta(minutes=1))
    owner.result = {'items': {site.id: {'run_id': current.id}}}
    db.commit()
    assert unresolved(db, START, END) == []


def test_running_and_partial_work_count_without_network_receipt_duplicates(env):
    db, site, _ = env; owner = parent(db, site)
    network = run(db, site, owner, status='partial')
    job(db, site, owner, status='queued')
    db.add(models.NetworkOperation(id=str(uuid4()), site_id=site.id, action='reglue', status='failed',
        initiator='test', request_payload={'auto_run_id': network.id}, created_at=AT, updated_at=AT))
    db.commit()
    assert {r['kind'] for r in unresolved(db, START, END)} == {'reglue', 'text'}
    assert len(unresolved(db, START, END)) == 2


def make_page_branch(db, site, owner, *, archived=False, published=False):
    task = models.GenerationTask(id=str(uuid4()), title='Menu', site_id=site.id, geo='PL', language='pl',
        archived_at=AT if archived else None, prompt_template='test', generation_mode='menu_structure')
    db.add(task); db.flush()
    branch = job(db, site, owner, 'pilot_internal_pages', 'partial')
    branch.result = {'task_id': task.id}
    item = models.ContentItem(id=str(uuid4()), task_id=task.id, site_id=site.id, topic='Page', slug='/page/',
        generated_json={}, idempotency_key=str(uuid4()), status='published' if published else 'generation_failed',
        published_at=AT if published else None, created_at=AT, updated_at=AT)
    db.add(item); db.flush()
    return branch


def test_all_published_pages_override_stale_partial_branch_status(env):
    db, site, _ = env; owner = parent(db, site)
    make_page_branch(db, site, owner, published=True)
    db.commit()
    assert unresolved(db, START, END) == []


def test_failed_page_counts_once_for_the_internal_pages_branch(env):
    db, site, _ = env; owner = parent(db, site)
    make_page_branch(db, site, owner)
    db.commit()
    refs = unresolved(db, START, END)
    assert len(refs) == 1 and refs[0]['kind'] == 'internal_pages'


def test_archived_content_task_does_not_reappear_as_unfinished(env):
    db, site, _ = env; owner = parent(db, site)
    make_page_branch(db, site, owner, archived=True)
    db.commit()
    assert unresolved(db, START, END) == []


def test_obsolete_generation_is_excluded_after_replanning(env):
    db, site, _ = env; owner = parent(db, site, payload={'generation_id': 'current'})
    job(db, site, owner, generation_id='old')
    db.commit()
    assert unresolved(db, START, END) == []


def test_report_and_draft_parent_are_not_counted_as_extra_tasks(env):
    db, site, _ = env
    parent(db, site, status='queued')
    db.add(models.BackgroundJob(kind='maintenance_report', status='failed', payload={'site_ids': [site.id]},
        created_at=AT, updated_at=AT))
    db.commit()
    assert unresolved(db, START, END) == []


def test_next_week_publication_does_not_complete_previous_week_snapshot(env):
    db, site, _ = env; owner = parent(db, site)
    branch = make_page_branch(db, site, owner, published=True)
    task = db.get(models.GenerationTask, branch.result['task_id'])
    task.items[0].published_at = END + timedelta(seconds=1)
    db.commit()
    assert len(unresolved(db, START, END)) == 1


def test_next_week_archive_does_not_hide_previous_week_unfinished_task(env):
    db, site, _ = env; owner = parent(db, site)
    branch = make_page_branch(db, site, owner, archived=True)
    db.get(models.GenerationTask, branch.result['task_id']).archived_at = END + timedelta(seconds=1)
    db.commit()
    assert len(unresolved(db, START, END)) == 1


def test_review_snapshot_includes_project_reason_and_parent_link(env):
    db, site, _ = env; owner = parent(db, site)
    branch = job(db, site, owner, field='paragraphs'); branch.error='Numerical conditions changed'; db.commit()
    ref=unresolved(db, START, END)[0]
    assert ref['project']==site.name and ref['field']=='paragraphs'
    assert ref['reason']=='Numerical conditions changed' and ref['status']=='failed'
    assert ref['report_url']=='/auto-reglue/pilot/logs?id='+owner.id
