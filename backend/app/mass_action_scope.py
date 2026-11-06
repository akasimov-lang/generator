"""One explicit brand/GEO boundary shared by manual and scheduled mass work."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from app import models
from app.domain_transfer_policy import geo_key


def brand_key(value):
    key = re.sub(r'[^\w]', '', (value or '').casefold())
    return {'maxacasino': 'maxa'}.get(key, key)


class MassActionFilter(BaseModel):
    model_config = ConfigDict(extra='forbid')
    brand: str = Field(min_length=1, max_length=200)
    geo: str = Field(min_length=2, max_length=16)
    include_general: bool = False
    site_type: Literal['monobrand', 'general'] | None = None

    @field_validator('brand')
    @classmethod
    def valid_brand(cls, value):
        value = value.strip()
        if not brand_key(value):
            raise ValueError('Выберите бренд для массового действия.')
        return value

    @field_validator('geo')
    @classmethod
    def valid_geo(cls, value):
        value = geo_key(value)
        if not re.fullmatch('[A-Z]{2}', value):
            raise ValueError('Выберите GEO для массового действия.')
        return value


def matches(site, filters, *, donor_only=False):
    general = site.site_type == 'general' or (site.site_type is None and brand_key(site.brand) in {'', brand_key('Общие ключи')})
    kind = 'general' if general else 'monobrand'
    brand_matches = brand_key('Общие ключи' if general else site.brand) == brand_key(filters.brand)
    return bool(site.is_active and not site.hidden_from_projects and site.project_status == 'mass_actions'
                and (donor_only or getattr(site, 'reglue_participation', True) is not False)
                and geo_key(site.cache_geo) == filters.geo
                and (brand_matches or filters.include_general and general)
                and (filters.site_type is None or filters.site_type == kind))


def constrain(db, filters, allowed=None, targets=()):
    if filters is None:
        raise ValueError('Перед массовым действием выберите бренд и GEO.')
    filters = MassActionFilter.model_validate(filters)
    ids = {site.id for site in db.scalars(select(models.Site)) if matches(site, filters)
           and (allowed is None or site.id in allowed)}
    if any(site.id not in ids for site in targets):
        raise ValueError('В запуске есть проект вне выбранного бренда, GEO или типа проекта. Обновите выборку.')
    db.info['mass_action_filter'] = filters.model_dump()
    db.info['cross_allowed_site_ids'] = ids
    return ids


def stamp_plan(db, plan, state, site, filters=None):
    from app.pilot_donors import stamp
    plan = stamp(db, plan)
    if plan.get('combination_id') and not db.info.get('canonical_replay_plan'):
        from app.reglue_combinations import History, identity
        if plan['combination_id'] != identity(plan):
            available = (plan.get('combination_history') or {}).get('compatible_variants', 1)
            History(db).stamp(plan, available=available)
            from app.auto_reglue import digest
            plan.pop('preview_token', None); plan['preview_token'] = digest(plan)
    filters = filters or db.info.get('mass_action_filter')
    if not filters:
        return plan
    from app.auto_reglue import digest
    plan = {**plan, 'mass_filter': filters, 'brand': site.brand or 'Общие ключи',
            'old_fake_main_path': state.get('fake_main_current') or None,
            'new_fake_main_path': plan.get('create_fake_main_path') or state.get('fake_main_current') or None}
    if state.get('page_metadata') is not None:plan['title_h1_current']=state['page_metadata']
    plan.pop('preview_token', None)
    return {**plan, 'preview_token': digest(plan)}


def require_run_scope(db, run):
    if not run or not run.plan.get('mass_filter'):
        return
    filters = MassActionFilter.model_validate(run.plan['mass_filter'])
    for site_id in {run.site_id, run.plan.get('source_site_id', run.site_id)}:
        from app.pilot_donors import authorized
        donor_only = authorized(db, run.plan, site_id)
        site = db.get(models.Site, site_id)
        if site:
            db.refresh(site)
        if site and not donor_only and run.plan.get('execution_mode') != 'transfer_only' and getattr(site, 'reglue_participation', True) is False:
            raise ValueError('Участвует в переклее: Нет. Запуск остановлен.')
        if not site or not matches(site, filters, donor_only=donor_only):
            raise ValueError('Проект больше не соответствует бренду, GEO или типу сохранённого фильтра. Запуск остановлен.')
