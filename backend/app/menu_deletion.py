"""Delete exactly one menu branch, preserving siblings and their metadata."""
import copy

from pydantic import BaseModel, Field
from sqlalchemy import select

from app import models

CHILD_KEYS = ("children", "items", "submenu", "subMenu")


class MenuBranchDelete(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    external_id: str = Field(default="", max_length=160)


def node_path(node):
    from app.services import _normalized_project_slug
    return _normalized_project_slug(next((node[key] for key in ("slug", "path", "url", "href") if node.get(key)), ""))


def remove_branch(items: list, path: str, external_id: str = "") -> tuple[list, list]:
    from app.services import _normalized_project_slug
    target = _normalized_project_slug(path)
    removed = []
    matches = 0

    def collect(node):
        removed.append(node)
        for key in CHILD_KEYS:
            for child in node.get(key, []) if isinstance(node.get(key), list) else []:
                if isinstance(child, dict):
                    collect(child)

    def walk(nodes):
        nonlocal matches
        kept = []
        for node in nodes:
            if not isinstance(node, dict):
                kept.append(copy.deepcopy(node))
                continue
            node_id = str(node.get("id") or node.get("external_id") or node.get("externalId") or "")
            if node_path(node) == target and (not external_id or not node_id or node_id == external_id):
                matches += 1
                collect(node)
                continue
            clone = copy.deepcopy(node)
            for key in CHILD_KEYS:
                if isinstance(node.get(key), list):
                    clone[key] = walk(node[key])
            kept.append(clone)
        return kept

    updated = walk(items)
    if matches > 1:
        raise ValueError("Найдено несколько одинаковых пунктов. Обновите проект перед удалением.")
    return updated, removed


async def delete_menu_branch(db, site, menu_type, payload, username):
    from app.services import _normalized_project_slug, sync_project_menus
    from app.technical_pages import menu_lock
    if menu_type not in {"header", "footer"}:
        raise ValueError("Выберите Header или Footer")
    with menu_lock(db, site.id):
        db.refresh(site)
        original = (site.default_menu or {}).get(menu_type) or []
        updated, removed = remove_branch(original, payload.path, payload.external_id)
        sections = db.scalars(select(models.Section).where(
            models.Section.site_id == site.id, models.Section.menu_type == menu_type,
        )).all()
        paths = {node_path(node) for node in removed} | {_normalized_project_slug(payload.path)}
        affected = {section.id for section in sections if _normalized_project_slug(section.path) in paths}
        while True:
            descendants = {section.id for section in sections if section.parent_id in affected}
            if descendants <= affected:
                break
            affected |= descendants
        if not removed and not affected:
            raise ValueError("Пункт меню уже удалён или изменён. Обновите проект.")
        result = await sync_project_menus(db, site, initiator_username=username,
                                         menu_types=(menu_type,), menu_items={menu_type: updated})
        if not result["success"]:
            raise ValueError("Не удалось обновить меню проекта. Ветка сохранена; повторите удаление.")
        for section in sections:
            if section.id in affected:
                section.sync_status = "external_deleted"
        db.add(models.PublicationLog(
            endpoint_url=f"internal://sites/{site.id}/menu/{menu_type}/branch",
            request_payload={"action": "menu_branch_delete", "project_name": site.name,
                             "menu_type": menu_type, "path": payload.path, "username": username},
            response_status=200, response_body={"removed_count": len(removed), "section_count": len(affected)},
        ))
        db.commit()
        return {"deleted": True, "removed_count": len(removed) or len(affected)}
