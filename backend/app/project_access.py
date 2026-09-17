"""Request-scoped project isolation. Worker sessions do not carry request grants."""
from fastapi import HTTPException
from sqlalchemy import event, or_, select
from sqlalchemy.orm import Session, with_loader_criteria
from app import models


def scoped_models(ids):
    content_ids = select(models.ContentItem.id).where(models.ContentItem.site_id.in_(ids))
    result = [(models.Site, models.Site.id.in_(ids))]
    for mapper in models.Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, 'site_id'):
            condition = cls.site_id.in_(ids)
            if cls is models.PromptTemplate:
                condition = or_(cls.site_id.is_(None), condition)
            result.append((cls, condition))
        elif hasattr(cls, 'content_item_id'):
            result.append((cls, cls.content_item_id.in_(content_ids)))
    return result


@event.listens_for(Session, 'do_orm_execute')
def filter_projects(execute_state):
    ids = execute_state.session.info.get('allowed_site_ids')
    if ids is None:
        return
    if execute_state.is_select:
        for cls, condition in scoped_models(ids):
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(cls, condition, include_aliases=True))
    elif execute_state.is_update or execute_state.is_delete:
        mapper = execute_state.bind_mapper
        if mapper:
            for cls, condition in scoped_models(ids):
                if mapper.class_ is cls:
                    execute_state.statement = execute_state.statement.where(condition)


def visible(db, cls, value):
    if not isinstance(value, str) or not db.scalar(select(cls.id).where(cls.id == value)):
        raise HTTPException(404, 'Объект не найден или нет доступа к проекту.')


def guard_references(db, values):
    references = {'site_id': models.Site, 'task_id': models.GenerationTask,
                  'content_id': models.ContentItem, 'content_item_id': models.ContentItem,
                  'section_id': models.Section, 'parent_id': models.Section,
                  'campaign_id': models.PublicationCampaign, 'publication_campaign_id': models.PublicationCampaign,
                  'prompt_id': models.PromptTemplate}
    for key, value in values.items():
        if value is None or value == '':
            continue
        singular = key[:-1] if key.endswith('_ids') else key
        cls = references.get(singular)
        if cls:
            for item in value if isinstance(value, list) else [value]:
                visible(db, cls, item)


@event.listens_for(Session, 'before_flush')
def guard_writes(db, flush_context, instances):
    ids = db.info.get('allowed_site_ids')
    if ids is None:
        return
    for obj in list(db.new) + list(db.dirty) + list(db.deleted):
        if isinstance(obj, models.Site) and (obj.id not in ids or
                (db.info.get('allowed_project_keys') is not None and (obj.name, obj.cache_server_ip) not in db.info['allowed_project_keys'])):
            raise HTTPException(403, 'Нет доступа к проекту.')
        if hasattr(obj, 'site_id') and obj.site_id not in ids:
            if not (isinstance(obj, models.PromptTemplate) and obj.site_id is None):
                raise HTTPException(403, 'Нет доступа к проекту.')
        guard_references(db, {key: getattr(obj, key) for key in
            ('task_id', 'content_item_id', 'section_id', 'parent_id', 'publication_campaign_id')
            if hasattr(obj, key) and getattr(obj, key)})


def external_projects(db, projects):
    keys = db.info.get('allowed_project_keys') if db is not None else None
    if keys is None:
        return projects
    return [row for row in projects if (row.get('name'), str(row.get('serverId') or row.get('server_id') or row.get('serverIp') or row.get('server_ip') or '').strip()) in keys]
