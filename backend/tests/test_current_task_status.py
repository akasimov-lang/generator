from app import models
from app.schemas import GenerationTaskResponse
from app.project_cache import _reconcile_completed_publication_tasks
from test_generation_modes import db,make_site


def task(db, statuses):
    site=make_site(db)
    row=models.GenerationTask(title='Task',site_id=site.id,geo='DK',language='da',status='publication_failed')
    db.add(row);db.flush()
    for i,status in enumerate(statuses):
        db.add(models.ContentItem(task_id=row.id,site_id=site.id,topic='Text',slug=f'/text-{i}/',status=status,
            generated_json={},idempotency_key=f'text-{i}',generation_error='Old failure' if status=='published' else 'Webdev: HTTP 503'))
    db.commit();return row


def test_task_response_recomputes_success_and_hides_obsolete_errors(db):
    row=task(db,['published','published'])
    response=GenerationTaskResponse.model_validate(row)
    assert response.status=='published' and response.error_summary is None
    assert row.status=='publication_failed'  # read serialization does not mutate storage


def test_real_failure_is_visible_with_its_reason(db):
    response=GenerationTaskResponse.model_validate(task(db,['published','publication_failed']))
    assert response.status=='publication_failed'
    assert response.error_summary=='/text-1/: Webdev: HTTP 503'


def test_generation_takes_precedence_while_other_items_are_already_published(db):
    row=task(db,['published','generating'])
    assert GenerationTaskResponse.model_validate(row).status=='generating'


def test_unconfirmed_publication_is_not_reported_as_published(db):
    row=task(db,['published','publication_pending_confirmation'])
    assert GenerationTaskResponse.model_validate(row).status=='publishing'


def test_periodic_reconciliation_repairs_completed_failed_aggregate(db):
    row=task(db,['published','published'])
    assert _reconcile_completed_publication_tasks(db,limit=100)==1
    db.refresh(row);assert row.status=='published'


def test_periodic_reconciliation_keeps_real_failure(db):
    row=task(db,['published','publication_failed'])
    assert _reconcile_completed_publication_tasks(db,limit=100)==0
    db.refresh(row);assert row.status=='publication_failed'
