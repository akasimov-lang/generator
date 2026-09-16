"""Project-wide notices derived only from local, persisted evidence."""
from sqlalchemy import select, or_, and_
from app import models


def refresh_notices(db, sites):
    if not sites:
        return
    db.flush()
    ids = [site.id for site in sites]
    sections = db.execute(select(
        models.Section.id, models.Section.site_id, models.Section.parent_id,
    ).where(
        models.Section.site_id.in_(ids),
        models.Section.menu_type == "header",
        models.Section.sync_status != "external_deleted",
        models.Section.is_temporary_parent.is_(False),
    )).all()
    header_ids = {row.id for row in sections}
    nested = {row.site_id for row in sections if row.parent_id}
    latest = {}
    for row in db.execute(select(
        models.ContentItem.id, models.ContentItem.site_id, models.ContentItem.section_id,
        models.ContentItem.section_content_mode, models.ContentItem.status,
        models.ContentItem.published_at,
    ).where(
        models.ContentItem.site_id.in_(ids),
        or_(models.ContentItem.published_at.is_not(None), and_(
            models.ContentItem.section_content_mode == "nested",
            models.ContentItem.status.in_(["publishing", "publication_pending_confirmation", "published", "deletion_pending"]),
        )),
    )):
        if (row.section_id in header_ids and row.section_content_mode == "nested"
                and row.status in {"publishing", "publication_pending_confirmation", "published", "deletion_pending"}):
            nested.add(row.site_id)
        if row.published_at:
            # A confirmed publication remains evidence even if its content is later deleted.
            stamp = row.published_at.isoformat().replace("+00:00", "") + ":" + row.id
            latest[row.site_id] = max(latest.get(row.site_id, ""), stamp)
    for site in sites:
        if site.header_menu_rendered is not None:
            site.menu_warning = (
                "header_nested" if site.id in nested and site.header_menu_nested is False
                else "header_missing" if site.header_menu_rendered is False else None
            )
        stamp = max(latest.get(site.id, ""), site.core_update_notice or "")
        if stamp and stamp > (site.core_update_acknowledged or ""):
            site.core_update_notice = stamp
        elif site.core_update_notice:
            site.core_update_notice = None


def refresh_and_commit_notices(db, sites):
    refresh_notices(db, sites)
    # These objects are immediately serialized as /sites. Avoid one reload per
    # project after committing the shared warning state.
    expire = db.expire_on_commit
    try:
        db.expire_on_commit = False
        db.commit()
    finally:
        db.expire_on_commit = expire
