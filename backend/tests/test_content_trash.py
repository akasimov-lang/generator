from datetime import datetime, timezone

from sqlalchemy import select

from app import models
from app.content_trash import restore_content
from app.services import generate_content_item
from test_api_serialization import make_client


def test_delete_and_restore_preserve_text_and_require_manual_publication():
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        task = models.GenerationTask(site_id=site.id, title="Trash", geo="DE", language="de", auto_publish=True)
        item = models.ContentItem(task=task, site_id=site.id, topic="Text", slug="/text/", status="generated", generated_at=datetime.now(timezone.utc), generated_json={"pages": [{"slug": "/text/", "content": {"blocks": []}}]}, idempotency_key="trash")
        db.add(item)
        db.commit()
        item_id = item.id
        source = item.generated_json
        revision = models.ContentRevision(content_item_id=item_id, source_json=source, remarks="Previous edit")
        db.add(revision)
        db.commit()
        revision_id = revision.id
    assert client.delete(f"/api/content/{item_id}").status_code == 200
    assert client.delete(f"/api/content/{item_id}").status_code == 200
    with sessions() as db:
        item = db.get(models.ContentItem, item_id)
        assert item.status == "deleted" and item.deletion_confirmed_at
        assert item.generated_json == source and db.get(models.ContentRevision, revision_id)
        try:
            generate_content_item(db, item)
            assert False, "Deleted text must not regenerate"
        except ValueError:
            pass
    result = client.post(f"/api/content/{item_id}/restore")
    assert result.status_code == 200
    data = result.json()
    assert data["status"] == "generated" and data["generated_json"] == source
    assert data["published_at"] is None and data["indexing_task_id"] is None
    assert data["publication_campaign_id"] is None


def test_restore_rejects_conflicting_url_and_pending_remote_delete():
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        task = models.GenerationTask(site_id=site.id, title="Trash", geo="DE", language="de")
        deleted = models.ContentItem(task=task, site_id=site.id, topic="Old", slug="/same/", status="deleted", generated_json={}, idempotency_key="old")
        active = models.ContentItem(task=task, site_id=site.id, topic="New", slug="/same/", status="generated", generated_json={}, idempotency_key="new")
        db.add_all([deleted, active])
        db.commit()
        item_id = deleted.id
    assert client.post(f"/api/content/{item_id}/restore").status_code == 409
    with sessions() as db:
        item = db.get(models.ContentItem, item_id)
        assert item.status == "deleted"
        item.status = "deletion_pending"
        db.commit()
    assert client.post(f"/api/content/{item_id}/restore").status_code == 409
