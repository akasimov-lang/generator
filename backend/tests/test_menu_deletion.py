import asyncio
import copy

import pytest
from sqlalchemy import select

from app import models, services
from app.menu_deletion import MenuBranchDelete, delete_menu_branch, remove_branch
from app.security import require_auth
from test_api_serialization import make_client


def tree():
    return [{"id": 1, "title": "Parent", "slug": "/a/", "order": 8, "children": [
        {"id": 2, "slug": "/a/child/", "title": "Child", "order": 2, "children": [{"id": 3, "slug": "/a/child/deep/", "title": "Deep", "order": 3}]},
        {"id": 4, "slug": "/a/sibling/", "title": "Sibling", "order": 7, "custom": "preserve"},
    ]}, {"id": 5, "slug": "/abc/", "title": "Other", "order": 9}]


@pytest.mark.parametrize("path,identifier,count", [("/a/", "1", 3 + 1), ("/a/child/", "2", 2), ("/a/child/deep/", "3", 1)])
def test_deletes_only_selected_subtree(path, identifier, count):
    source = tree()
    original = copy.deepcopy(source)
    updated, removed = remove_branch(source, path, identifier)
    assert source == original
    assert len(removed) == count
    assert updated[-1] == original[-1]
    if path != "/a/":
        assert updated[0]["children"][-1] == original[0]["children"][-1]
        assert updated[0]["id"] == 1 and updated[0]["order"] == 8


def test_missing_or_changed_identity_does_not_delete_anything():
    source = tree()
    assert remove_branch(source, "/a/child/", "wrong") == (source, [])


@pytest.mark.parametrize("success", [True, False])
def test_remote_result_controls_local_removal_and_keeps_other_menu(monkeypatch, success):
    _, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.default_menu = {"header": tree(), "footer": [{"id": 20, "slug": "/contacts/", "title": "Contacts", "order": 1}]}
        parent = models.Section(site_id=site.id, external_id="1", name="Parent", path="/a/", menu_type="header")
        db.add(parent)
        db.flush()
        child = models.Section(site_id=site.id, external_id="2", name="Child", path="/a/child/", menu_type="header", parent_id=parent.id)
        sibling = models.Section(site_id=site.id, external_id="5", name="Other", path="/abc/", menu_type="header")
        db.add_all([child, sibling])
        db.commit()
        before = copy.deepcopy(site.default_menu)
        async def sync(db, site, **kwargs):
            assert kwargs["menu_types"] == ("header",)
            assert kwargs["menu_items"]["header"] == [before["header"][-1]]
            if success:
                site.default_menu = {**site.default_menu, "header": kwargs["menu_items"]["header"]}
                db.commit()
            return {"success": success}
        monkeypatch.setattr(services, "sync_project_menus", sync)
        if success:
            asyncio.run(delete_menu_branch(db, site, "header", MenuBranchDelete(path="/a/", external_id="1"), "editor"))
            assert parent.sync_status == child.sync_status == "external_deleted"
            assert sibling.sync_status == "pending"
        else:
            with pytest.raises(ValueError, match="Ветка сохранена"):
                asyncio.run(delete_menu_branch(db, site, "header", MenuBranchDelete(path="/a/", external_id="1"), "editor"))
            assert parent.sync_status == child.sync_status == "pending"
            assert site.default_menu == before
        assert site.default_menu["footer"] == before["footer"]


def test_branch_deletion_is_available_to_regular_users(monkeypatch):
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.default_menu = {"header": tree(), "footer": []}
        db.commit()
        site_id = site.id
    async def sync(*args, **kwargs):
        return {"success": True}
    monkeypatch.setattr(services, "sync_project_menus", sync)
    client.app.dependency_overrides[require_auth] = lambda: {"id": "editor", "username": "editor", "is_admin": False}
    result = client.request("DELETE", f"/api/sites/{site_id}/menu/header/branch", json={"path": "/a/", "external_id": "1"})
    assert result.status_code == 200 and result.json()["removed_count"] == 4
