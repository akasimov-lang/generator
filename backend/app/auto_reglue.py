"""Configured, explicit one-pass reglue. Opening a view never starts work."""
import hashlib
import json
import re
from html import escape
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid5

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import models, project_network
from app.alternate_templates import template_catalog
from app.network_state import alternate_links, domain_name, state_revision, validate_markup

ACTIVE = ('queued', 'running', 'waiting', 'partial')


class GlobalConfig(BaseModel):
    enabled: bool = False
    auxiliary_hreflangs: list[str] = Field(default_factory=list, max_length=30)
    max_projects: int = Field(default=20, ge=1, le=100)

    @field_validator('auxiliary_hreflangs')
    @classmethod
    def languages(cls, values):
        if any(not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', v) for v in values):
            raise ValueError('Укажите коды языков; x-default задаётся отдельно.')
        return list(dict.fromkeys(values))


class ProjectConfig(BaseModel):
    enabled: bool = False
    drop_domain: str = Field(default='', max_length=253)
    parent_kind: Literal['drop', 'newreg'] = 'drop'
    newreg_domain: str = Field(default='', max_length=253)
    language: str = Field(default='', max_length=15)
    profile_id: str = Field(default='', max_length=300)
    variant: Literal['provided', 'before', 'after', 'current'] = 'current'
    fake_main_path: str = Field(default='', max_length=250)

    @field_validator('drop_domain', 'newreg_domain')
    @classmethod
    def domains(cls, value):
        if not value: return ''
        normalized = domain_name(value)
        if not normalized or normalized != value.strip().lower().rstrip('.') or not re.fullmatch(r'[a-z0-9.-]+', normalized):
            raise ValueError('Введите домен без протокола, пути и порта.')
        return normalized

    @field_validator('language')
    @classmethod
    def language_code(cls, value):
        if value and not re.fullmatch(r'[a-z]{2,3}', value):
            raise ValueError('Язык: короткий код, например az, ru или en.')
        return value

    @field_validator('fake_main_path')
    @classmethod
    def path(cls, value):
        if value and (not value.startswith('/') or value.startswith('//') or any(c.isspace() for c in value) or '?' in value or '#' in value or '\\' in value):
            raise ValueError('Путь копии главной должен начинаться с /, без домена, параметров и пробелов.')
        return value


def config(db, site_id=None):
    row = db.get(models.AutoReglueConfig, site_id or 'global')
    return (ProjectConfig if site_id else GlobalConfig).model_validate(row.value if row else {})


def save_config(db, value, site_id=None):
    key = site_id or 'global'
    row = db.get(models.AutoReglueConfig, key)
    if row is None:
        row = models.AutoReglueConfig(key=key, value=value.model_dump())
        db.add(row)
    else: row.value = value.model_dump()
    db.commit()
    return row.value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def select_next_domain(site, state, cfg):
    parent = (cfg.drop_domain if cfg.parent_kind == 'drop' else cfg.newreg_domain).removeprefix('www.')
    if not parent:
        raise ValueError('Укажите родительский домен выбранного варианта.')
    domains = state['domains']
    start = domains.index(state['canon']) + 1 if state['canon'] in domains else 0
    used = {domain_name(x) for x in [*(site.main_domain_history or []), state['canon'], state.get('prev')]}
    # No wrap and no recycling of former Main domains.
    for domain in domains[start:]:
        if domain.endswith('.' + parent) and domain not in used:
            return domain
    raise ValueError('После текущего Main нет неиспользованного поддомена выбранного дропа/новорега. Добавьте резерв в сетку.')


def build_plan(site, state, global_cfg, cfg):
    if site.project_status != 'mass_actions':
        raise ValueError('Проект не имеет статуса «Массовые действия».')
    if not global_cfg.enabled or not cfg.enabled:
        raise ValueError('Сначала включите глобальные настройки и автопереклей проекта.')
    geo = (site.cache_geo or '').strip().upper()
    if not re.fullmatch(r'[A-Z]{2}', geo):
        raise ValueError('В проекте должно быть задано GEO из двух букв.')
    if not cfg.drop_domain or not cfg.language:
        raise ValueError('Укажите дроп для x-default и язык проекта.')
    if not state.get('has_head'):
        raise ValueError('Не получены данные head проекта.')
    target = select_next_domain(site, state, cfg)
    validate_markup(state['alternateMarkup'])
    source = []
    if cfg.profile_id:
        profile = next((p for p in template_catalog() if p['id'] == cfg.profile_id), None)
        if not profile or domain_name(profile['project']) != domain_name(site.name) or profile['geo'] != geo or profile['language'] != cfg.language:
            raise ValueError('Шаблон не соответствует проекту или GEO.')
        if cfg.variant not in profile['variants']:
            raise ValueError('Эта версия схемы не заполнена; выберите существующую.')
        source = profile['variants'][cfg.variant]['links']
    links = {}
    for link in [*source, *alternate_links(state['alternateMarkup'])]:
        key = link['hreflang'].lower()
        if key != 'x-default' and key not in links:
            # Canon and all language variants move together; paths are retained.
            url = urlsplit(link['href'].replace('{{settings.canon}}', target).replace('{{reqPath}}', '/__auto_request_path__'))
            links[key] = {'hreflang': link['hreflang'], 'href': urlunsplit(('https', target, url.path or '/', url.query, url.fragment)).replace('/__auto_request_path__', '{{reqPath}}')}
    links.setdefault(cfg.language, {'hreflang': cfg.language, 'href': f'https://{target}/'})
    regional = f'{cfg.language}-{geo}'
    if cfg.fake_main_path:
        links[regional.lower()] = {'hreflang': regional, 'href': f'https://{target}{cfg.fake_main_path}'}
    else:
        links.setdefault(regional.lower(), {'hreflang': regional, 'href': f'https://{target}/'})
    for lang in global_cfg.auxiliary_hreflangs:
        links.setdefault(lang.lower(), {'hreflang': lang, 'href': f'https://{target}/'})
    links['x-default'] = {'hreflang': 'x-default', 'href': f'https://{cfg.drop_domain}/'}
    markup = '\n'.join(f'<link rel="alternate" hreflang="{escape(x["hreflang"], quote=True)}" href="{escape(x["href"], quote=True)}" />' for x in links.values())
    validate_markup(markup)
    plan = {'site_id': site.id, 'project': site.name, 'geo': geo, 'old_main': state['canon'], 'new_main': target,
            'drop_domain': cfg.drop_domain, 'parent_kind': cfg.parent_kind, 'alternateMarkup': markup,
            'required_page_urls': list(dict.fromkeys(x['href'] for x in links.values() if '{{reqPath}}' not in x['href'] and urlsplit(x['href']).path not in {'', '/'})),
            'revision': state.get('revision') or state_revision(state), 'config_hash': digest([global_cfg.model_dump(), cfg.model_dump()])}
    plan['preview_token'] = digest(plan)
    return plan


def preview(db, site):
    state = project_network.read_network(db, site)
    return build_plan(site, state, config(db), config(db, site.id))


def active_run(db, site_id):
    return db.scalar(select(models.AutoReglueRun).where(models.AutoReglueRun.site_id == site_id, models.AutoReglueRun.status.in_(ACTIVE)))


def serialize(run):
    return {'id': run.id, 'site_id': run.site_id, 'status': run.status, 'phase': run.phase,
            'message': run.message, 'plan': run.plan, 'created_at': run.created_at}


def prepare_run(db, site, request_id, token, username):
    existing = db.get(models.AutoReglueRun, str(request_id))
    if existing:
        if existing.site_id != site.id: raise ValueError('Этот запуск принадлежит другому проекту.')
        return existing, False
    plan = preview(db, site)
    if plan['preview_token'] != token:
        raise project_network.NetworkConflict('Состояние изменилось после предпросмотра. Подготовьте план снова.')
    with project_network.network_lock(db, site.id):
        existing = db.get(models.AutoReglueRun, str(request_id))
        if existing:
            if existing.site_id != site.id: raise ValueError('Этот запуск принадлежит другому проекту.')
            return existing, False
        if active_run(db, site.id): raise project_network.NetworkConflict('Для проекта уже есть незавершённый автопереклей.')
        run = models.AutoReglueRun(id=str(request_id), site_id=site.id, initiator=username, plan=plan, status='queued', phase='prepared')
        db.add(run); db.commit()
    return run, True


def verify_pages(urls):
    with httpx.Client(timeout=25, follow_redirects=False) as client:
        for url in urls:
            with client.stream('GET', url) as response:
                if response.status_code != 200:
                    raise ValueError(f'Страница копии главной не подтвердилась: {url} (HTTP {response.status_code}). Создайте её до запуска.')


def execute(db, run_id):
    # Separate lock serializes duplicate Celery deliveries across all phases.
    with project_network.network_lock(db, 'auto-run:' + run_id):
        run = db.get(models.AutoReglueRun, run_id)
        if run is None or run.status not in {'queued', 'waiting', 'running'}: return
        site = db.get(models.Site, run.site_id)
        plan = run.plan
        try:
            if not site or site.project_status != 'mass_actions': raise ValueError('Проект больше не участвует в массовых действиях.')
            if not config(db).enabled or not config(db, site.id).enabled: raise ValueError('Автопереклей выключен в настройках.')
            state = project_network.read_network(db, site)
            if run.phase == 'prepared':
                current = build_plan(site, state, config(db), config(db, site.id))
                if current['preview_token'] != plan['preview_token']: raise ValueError('Состояние изменилось до начала запуска. Нужен новый предпросмотр.')
                verify_pages(plan['required_page_urls'])
            run.status = 'running'; db.commit()
            for action in ['reserve', 'reglue', 'alternates']:
                db.refresh(run)
                if run.status == 'cancelled': return
                if site.project_status != 'mass_actions' or not config(db).enabled or not config(db, site.id).enabled:
                    raise ValueError('Автопереклей остановлен настройками.')
                receipt = str(uuid5(UUID(run.id), action))
                existing = db.get(models.NetworkOperation, receipt)
                state = project_network.read_network(db, site)
                if existing:
                    db.refresh(existing)
                    if existing.status == 'confirmed': continue
                    if existing.status == 'failed': raise ValueError(existing.message or 'Ошибка Webdev.')
                    run.status = 'waiting'; run.message = 'Ожидается подтверждение Webdev. Проверяем результат чтением настроек без повторной записи.'; db.commit(); return
                expected = plan['new_main'] if action == 'alternates' else plan['old_main']
                if state['canon'] != expected: raise ValueError('Canonical изменился вне этого запуска. Проверьте сетку.')
                run.phase = action; db.commit()
                payload = project_network.NetworkChange(request_id=UUID(receipt), action=action, revision=state['revision'], domain=plan['new_main'], alternate_markup=plan['alternateMarkup'], enable_alternates=True)
                project_network.change_network(db, site, payload, run.initiator, auto_run_id=run.id)
                operation = db.get(models.NetworkOperation, receipt); db.refresh(operation)
                if operation.status == 'failed': raise ValueError(operation.message or 'Ошибка Webdev.')
                if operation.status != 'confirmed':
                    run.status = 'waiting'; run.message = operation.message; db.commit(); return
            run.status = 'completed'; run.phase = 'completed'; run.message = 'Новый Main и альтернейты подтверждены.'; db.commit()
        except Exception as error:
            db.rollback(); run = db.get(models.AutoReglueRun, run_id)
            if run and run.status != 'cancelled':
                run.status = 'partial' if run.phase in {'reglue', 'alternates'} else 'failed'
                run.message = str(error)[:2000]; db.commit()
