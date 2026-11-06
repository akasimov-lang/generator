from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from app import models
from app.background_jobs import enqueue_publication, dispatch_pending, run_job
from app.worker import celery_app
from test_project_network import env


def content(db, site):
    item = models.ContentItem(task_id=str(uuid4()), site_id=site.id, topic="Ready", slug="ready",
                              generated_json={}, status="approved", idempotency_key=str(uuid4()))
    db.add(item)
    db.commit()
    return item


def test_broker_failure_keeps_intent_and_duplicate_delivery_does_not_publish_twice(env, monkeypatch):
    db, site, _ = env
    item = content(db, site)
    monkeypatch.setattr("app.services.validate_content_for_publication", lambda item: None)
    calls = []
    async def publish(db, item, site, initiator_username=None):
        calls.append(initiator_username)
        item.status = "published"
        db.commit()
    monkeypatch.setattr("app.services.publish_item", publish)
    enqueue_publication(db, item, "editor")
    enqueue_publication(db, item, "editor")
    jobs = db.scalars(select(models.BackgroundJob)).all()
    assert len(jobs) == 1
    def offline(*args):
        raise ConnectionError("broker offline")
    assert dispatch_pending(db, offline) == {"dispatched": 0}
    assert jobs[0].status == "queued"
    sent = []
    assert dispatch_pending(db, lambda *args: sent.append(args)) == {"dispatched": 1}
    assert sent == [(jobs[0].id, "publication")]
    assert run_job(db, jobs[0].id)["status"] == "completed"
    assert run_job(db, jobs[0].id)["status"] == "skipped"
    assert calls == ["editor"]


def test_claimed_job_is_not_repeated_after_worker_loss(env):
    db, _, _ = env
    job = models.BackgroundJob(kind="publication", status="running", payload={})
    db.add(job); db.commit()
    assert run_job(db, job.id)["status"] == "skipped"


def test_cache_sync_dispatch_is_separate_from_publication(env):
    db, _, _ = env
    job = models.BackgroundJob(kind="cache_sync", payload={"names": ["project.test"]})
    db.add(job); db.commit()
    sent = []
    dispatch_pending(db, lambda *args: sent.append(args))
    assert sent == [(job.id, "cache_sync")]
    dispatch_pending(db, lambda *args: sent.append(args))
    assert len(sent) == 1
    job.dispatched_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db.commit()
    dispatch_pending(db, lambda *args: sent.append(args))
    assert len(sent) == 2  # Lost delivery can be resent before it is claimed.


def test_long_tasks_do_not_share_scheduler_or_publication_queue():
    routes = celery_app.conf.task_routes
    assert routes["app.worker.run_content_item_pipeline"]["queue"] == "generation"
    assert routes["app.worker.publish_due_items"]["queue"] == "publication"
    assert routes["app.worker.auto_reglue"]["queue"] == "automation"
    assert routes["app.worker.dispatch_background_jobs"]["queue"] == "background_dispatch"
    assert routes["app.worker.reconcile_pending_publications"]["queue"] == "confirmation"


def test_planning_and_small_generations_have_independent_queues(env):
    db, site, _ = env
    jobs = [models.BackgroundJob(kind=kind, payload=payload) for kind,payload in [
        ('auto_pilot_preview', {}), ('menu_generation', {'site_id':site.id}),
        ('pilot_text', {'field':'title_h1'}), ('pilot_text', {'field':'paragraphs'}),
        ('mass_reglue_list', {})]]
    db.add_all(jobs); db.commit()
    sent=[]
    dispatch_pending(db, lambda id, queue: sent.append((id,queue)))
    assert dict(sent)==dict(zip([job.id for job in jobs],['planning','short_generation','short_generation','pilot_texts','automation']))
    assert sent[0][0]==jobs[0].id


def test_dispatch_does_not_repeat_a_delivery_still_waiting_in_broker(env):
    db, site, _=env
    old=models.BackgroundJob(kind='cache_sync',payload={},dispatched_at=datetime.now(timezone.utc)-timedelta(hours=2))
    new=models.BackgroundJob(kind='auto_pilot_preview',payload={})
    db.add_all([old,new]);db.commit()
    sent=[]
    dispatch_pending(db,lambda *args:sent.append(args),inflight_ids={old.id})
    assert sent==[(new.id,'planning')]
