import copy

from sqlalchemy import select

from app import models
from app.schemas import MenuStructureGenerationCreate
from app.services import create_menu_structure_task
from app.security import require_auth
from test_api_serialization import make_client


def test_review_toggle_is_durable_and_scoped_to_exact_menu_item():
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.default_menu = {"header": [{"id": 1, "title": "Reviews", "slug": "/reviews/", "children": [
            {"id": 2, "title": "Hitnspin", "slug": "/reviews/hitnspin/"},
            {"id": 3, "title": "Other", "slug": "/reviews/other/"},
        ]}], "footer": [{"id": 2, "title": "Contacts", "slug": "/contacts/"}]}
        original = copy.deepcopy(site.default_menu)
        site_id = site.id
        db.commit()
    client.app.dependency_overrides[require_auth] = lambda: {"id": "admin-id", "username": "editor", "is_admin": False}
    payload = {"external_id": "2", "name": "Hitnspin", "path": "/reviews/hitnspin/", "menu_type": "header", "is_review": True}
    response = client.patch(f"/api/sites/{site_id}/sections/review", json=payload)
    assert response.status_code == 200
    assert response.json()["is_review"] is True and response.json()["is_temporary_parent"] is False
    with sessions() as db:
        site = db.get(models.Site, site_id)
        assert site.default_menu == original
        task = create_menu_structure_task(db, site, MenuStructureGenerationCreate(geo="PL", language="pl", menu_types=["header", "footer"], collect_competitors=False))
        review = next(item for item in task.items if item.topic == "Hitnspin")
        assert review.generation_context["casino_brand"] == "Hitnspin"
        assert review.generation_context["content_kind"] == "casino_review"
        assert review.generation_context["current_section"]["breadcrumb"] == ["Reviews", "Hitnspin"]
        assert all(item.generation_context["content_kind"] == "menu_page" for item in task.items if item.id != review.id)
        assert db.get(models.Section, review.section_id).is_review is True
    response = client.patch(f"/api/sites/{site_id}/sections/review", json={**payload, "is_review": False})
    assert response.status_code == 200 and response.json()["is_review"] is False
    with sessions() as db:
        assert len(db.scalars(select(models.Section).where(models.Section.site_id == site_id)).all()) == 4
        # A setting change affects future generation; existing text is not rewritten.
        review = db.scalar(select(models.ContentItem).where(models.ContentItem.topic == "Hitnspin"))
        assert review.generation_context["content_kind"] == "casino_review"


def test_new_sections_have_review_disabled():
    _, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        section = models.Section(site_id=site.id, external_id="one", name="Brand", path="/brand/")
        db.add(section)
        db.commit()
        assert section.is_review is False
