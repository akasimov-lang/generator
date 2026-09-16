from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app import models
from app.project_notices import refresh_notices
from app.api import acknowledge_core_update
from test_project_network import env


def publication(db, site, when, **kwargs):
    item = models.ContentItem(
        task_id=str(uuid4()), site_id=site.id, topic="Published", slug="page",
        generated_json={}, status="published", published_at=when,
        idempotency_key=str(uuid4()), **kwargs,
    )
    db.add(item)
    db.flush()
    return item


def test_notices_persist_and_done_is_shared_and_race_safe(env):
    db, site, _ = env
    db.autoflush = False
    now = datetime.now(timezone.utc)
    publication(db, site, now)
    refresh_notices(db, [site])
    db.commit()
    db.expire_all()
    old = site.core_update_notice
    assert old
    publication(db, site, now + timedelta(seconds=1))
    refresh_notices(db, [site])
    db.commit()
    with pytest.raises(HTTPException) as error:
        acknowledge_core_update(site.id, {"stamp": old}, None, db)
    assert error.value.status_code == 409
    current = site.core_update_notice
    acknowledge_core_update(site.id, {"stamp": current}, None, db)
    db.expire_all()
    refresh_notices(db, [site])
    assert site.core_update_notice is None
    assert site.core_update_acknowledged == current
    publication(db, site, now + timedelta(seconds=2))
    refresh_notices(db, [site])
    assert site.core_update_notice > current


def test_menu_notice_uses_db_nested_content_and_clears_after_fix(env):
    db, site, _ = env
    section = models.Section(site_id=site.id, external_id="header", name="Header", path="/",
                             menu_type="header", sync_status="synced")
    db.add(section)
    db.flush()
    publication(db, site, datetime.now(timezone.utc), section_id=section.id, section_content_mode="nested")
    site.header_menu_rendered = True
    site.header_menu_nested = False
    refresh_notices(db, [site])
    db.commit()
    db.expire_all()
    assert site.menu_warning == "header_nested"
    site.header_menu_nested = True
    refresh_notices(db, [site])
    db.commit()
    assert site.menu_warning is None
    site.header_menu_rendered = False
    refresh_notices(db, [site])
    assert site.menu_warning == "header_missing"
    site.header_menu_rendered = True
    site.header_menu_nested = False
    section.sync_status = "external_deleted"
    refresh_notices(db, [site])
    assert site.menu_warning is None
