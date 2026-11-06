from copy import deepcopy

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models, menu_page_scope, services
from app.db import Base
from app.schemas import MenuStructureGenerationCreate


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def setup(db, monkeypatch, pages):
    site = models.Site(name="scope.example", base_url="https://scope.example", publication_endpoint="https://scope.example/api")
    site.default_menu = {"header": [{"id": n, "title": title, "slug": path} for n, (title, path) in enumerate([
        ("Promocje", "/promocje/"), ("Logowanie", "/logowanie/"), ("Turnieje", "/turnieje/"),
        ("Oferta gier", "/oferta-gier/"), ("Wpłaty i wypłaty", "/wplaty-i-wyplaty/"),
    ], 1)], "footer": []}
    db.add(site)
    db.commit()
    class Remote:
        def __init__(self, db, remote_site): assert remote_site.id == site.id
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def project(self): return {"data": {"pages": deepcopy(pages)}}
    monkeypatch.setattr(menu_page_scope, "Remote", Remote)
    return site


def request(**kwargs):
    return MenuStructureGenerationCreate(geo="PL", language="pl", collect_competitors=False, **kwargs)


def test_five_menu_items_with_three_external_pages_create_only_two_texts(db, monkeypatch):
    pages = [{"slug": p} for p in ["/", "/promocje/", "/logowanie/", "/turnieje/"]]
    site = setup(db, monkeypatch, pages)
    menu = deepcopy(site.default_menu)
    task = services.create_menu_structure_task(db, site, request())
    assert task.topics_count == 2
    assert {item.slug for item in task.items} == {"/oferta-gier/", "/wplaty-i-wyplaty/"}
    assert all(item.generation_context["menu_page_creation_only"] for item in task.items)
    assert site.default_menu == menu
    assert len(db.scalars(select(models.ContentItem)).all()) == 2


def test_existing_parent_is_skipped_while_new_child_is_generated(db, monkeypatch):
    site = setup(db, monkeypatch, [{"slug": "/promocje"}])
    parent = models.Section(site_id=site.id, external_id="1", name="Promocje", path="/promocje/", menu_type="header", sync_status="synced")
    db.add(parent)
    db.flush()
    site.default_menu["header"][0]["children"] = [{"id": 99, "title": "Nowe bonusy", "slug": "/promocje/nowe/"}]
    task = services.create_menu_structure_task(db, site, request(section_ids=[parent.id]))
    assert [item.slug for item in task.items] == ["/promocje/nowe/"]
    assert task.items[0].generation_context["current_section"]["breadcrumb"] == ["Promocje", "Nowe bonusy"]


def test_existing_local_pending_task_is_also_excluded(db, monkeypatch):
    site = setup(db, monkeypatch, [{"slug": p} for p in ["/promocje/", "/logowanie/", "/turnieje/"]])
    pending = models.GenerationTask(site_id=site.id, title="Existing", geo="PL", language="pl")
    db.add(pending)
    db.flush()
    db.add(models.ContentItem(task_id=pending.id, site_id=site.id, topic="Pending", slug="/oferta-gier/",
                              generated_json={}, status="generation_queued", idempotency_key="existing-scope-item"))
    db.commit()
    task = services.create_menu_structure_task(db, site, request())
    assert [item.slug for item in task.items] == ["/wplaty-i-wyplaty/"]


def test_all_pages_existing_does_not_create_empty_task(db, monkeypatch):
    site = setup(db, monkeypatch, [{"slug": p} for p in ["/promocje/", "/logowanie/", "/turnieje/", "/oferta-gier/", "/wplaty-i-wyplaty/"]])
    with pytest.raises(ValueError, match="нет пунктов"):
        services.create_menu_structure_task(db, site, request())
    assert not db.scalars(select(models.GenerationTask)).all()


@pytest.mark.parametrize("pages", [None, {}, [{"id": "1"}]])
def test_incomplete_webdev_page_inventory_never_means_all_pages_are_missing(db, monkeypatch, pages):
    site = setup(db, monkeypatch, pages)
    with pytest.raises(ValueError, match="полный список страниц"):
        services.create_menu_structure_task(db, site, request())
    assert not db.scalars(select(models.ContentItem)).all()
    assert not db.scalars(select(models.Section)).all()


def test_unavailable_webdev_does_not_start_generation(db, monkeypatch):
    site = setup(db, monkeypatch, [])
    class Unavailable:
        def __init__(self, *args): pass
        def __enter__(self): raise httpx.ReadTimeout("unavailable")
        def __exit__(self, *args): pass
    monkeypatch.setattr(menu_page_scope, "Remote", Unavailable)
    with pytest.raises(ValueError, match="Генерация не запущена"):
        services.create_menu_structure_task(db, site, request())
    assert not db.scalars(select(models.GenerationTask)).all()
