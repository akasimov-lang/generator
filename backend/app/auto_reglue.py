"""Configured, explicit one-pass reglue. Opening a view never starts work."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from html import escape
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid5, NAMESPACE_URL

import httpx
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import models, project_network
from app.subdomain_naming import next_subdomain
from app.domain_classification import classify_domains
from app.alternate_templates import template_catalog
from app.alternate_language_pool import default_language_pool
from app.project_cache import ProjectCacheError
from app.network_state import alternate_links, domain_name, state_revision, validate_markup

ACTIVE = ('queued', 'running', 'waiting', 'partial')


class DomainOptions(BaseModel):
    domain_layout: Literal['subdomain_main', 'root_main'] = 'subdomain_main'
    parent_kind: Literal['drop', 'newreg'] = 'drop'
    create_subdomains: bool = False
    subdomain_add_casino: bool = False
    subdomain_name_style: Literal['mixed', 'joined', 'hyphen'] = 'mixed'
    x_default_use_newreg: bool = False


class GlobalConfig(BaseModel):
    apply_domain_settings: bool = False
    domain_settings: DomainOptions = Field(default_factory=DomainOptions)
    enabled: bool = False
    schedule_enabled: bool = False
    interval_days: Literal[0, 3, 4, 5, 7, 14] = 0
    scheme_mode: Literal["preserve", "add_auxiliary", "base_only"] = "preserve"
    auxiliary_hreflangs: list[str] = Field(default_factory=default_language_pool, max_length=200)
    max_projects: int = Field(default=20, ge=1, le=100)

    @field_validator('auxiliary_hreflangs')
    @classmethod
    def languages(cls, values):
        if any(not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', v) for v in values):
            raise ValueError('Укажите коды языков; x-default задаётся отдельно.')
        return list(dict.fromkeys(values))


class ProjectConfig(BaseModel):
    enabled: bool = False
    scope: Literal["mass", "personal"] = "mass"
    domain_layout: Literal['subdomain_main', 'root_main'] = 'subdomain_main'
    schedule_enabled: bool = False
    interval_days: Literal[0, 3, 4, 5, 7, 14] = 0
    scheme_mode: Literal["preserve", "add_auxiliary", "base_only"] = "preserve"
    auxiliary_hreflangs: list[str] = Field(default_factory=default_language_pool, max_length=200)

    @field_validator('auxiliary_hreflangs')
    @classmethod
    def languages(cls, values):
        return GlobalConfig.languages(values)

    drop_domain: str = Field(default='', max_length=253)
    x_default_use_newreg: bool = False
    x_default_newreg_domain: str = Field(default='', max_length=253)
    parent_kind: Literal['drop', 'newreg'] = 'drop'
    create_subdomains: bool = False
    subdomain_add_casino: bool = False
    subdomain_name_style: Literal["mixed", "joined", "hyphen"] = "mixed"
    newreg_domain: str = Field(default='', max_length=253)
    language: str = Field(default='', max_length=15)
    profile_id: str = Field(default='', max_length=300)
    variant: Literal['provided', 'before', 'after', 'current'] = 'current'
    fake_main_path: str = Field(default='', max_length=250)

    @field_validator('drop_domain', 'newreg_domain', 'x_default_newreg_domain')
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
    # Same lock as the scheduler: saving rules cannot race a due-slot claim.
    with project_network.network_lock(db, 'auto-schedule'):
        key = site_id or 'global'
        row = db.get(models.AutoReglueConfig, key)
        previous = row.value if row else {}
        saved = value.model_dump()
        # Kept only for upgrading existing schedules without resetting their old due date.
        if previous.get('_schedule_since'):
            saved['_schedule_since'] = previous['_schedule_since']
        new_activation = not previous.get('enabled') and value.enabled
        if not site_id or value.scope == 'personal':
            new_activation = new_activation or (value.schedule_enabled and not previous.get('schedule_enabled'))
        if row is None:
            row = models.AutoReglueConfig(key=key, value=saved)
            db.add(row)
        else:
            row.value = saved
        db.flush()
        sync_schedules(db, datetime.now(timezone.utc), immediate=(key if new_activation else None))
        db.commit()
    return value.model_dump()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def select_next_domain(site, state, cfg):
    parent = (cfg.drop_domain if cfg.parent_kind == 'drop' else cfg.newreg_domain).removeprefix('www.')
    if not parent:
        raise ValueError('Укажите родительский домен выбранного варианта.')
    if cfg.create_subdomains:
        return next_subdomain(site, state, cfg, parent)
    domains = [domain for domain in state['domains'] if domain not in state.get('amp_domains', [])]
    start = domains.index(state['canon']) + 1 if state['canon'] in domains else 0
    used = {domain_name(x) for x in [*(site.main_domain_history or []), state['canon'], state.get('prev')]}
    # No wrap and no recycling of former Main domains.
    for domain in domains[start:]:
        if domain.endswith('.' + parent) and domain not in used:
            return domain
    raise ValueError('После текущего Main нет неиспользованного поддомена выбранного дропа/новорега. Добавьте резерв в сетку.')


def select_root_and_subdomain(site, state, cfg):
    domains = [domain for domain in state['domains'] if domain not in state.get('amp_domains', [])]
    start = domains.index(state['canon']) + 1 if state['canon'] in domains else 0
    used_main = {domain_name(x) for x in [*(site.main_domain_history or []), state['canon'], state.get('prev')]}
    used_children = used_main | set(getattr(site, 'alternate_domain_history', None) or [])
    types = getattr(site, 'domain_types', None) or {}
    required_type = 'newreg' if cfg.x_default_use_newreg else 'drop'
    for root in domains[start:]:
        if root in used_main or types.get(root) != required_type:
            continue
        bare_root = root.removeprefix('www.')
        if any(bare_root.endswith('.' + parent.removeprefix('www.')) for parent in domains if parent.removeprefix('www.') != bare_root):
            continue
        if cfg.create_subdomains:
            return root, next_subdomain(site, state, cfg, root)
        child = next((d for d in domains if d.endswith('.' + bare_root) and d != root and d != 'www.' + bare_root and d not in used_children), None)
        if child is None:
            raise ValueError(f'У следующего корневого домена {root} нет неиспользованного поддомена в сетке. Сначала создайте его.')
        return root, child
    raise ValueError('Нет следующего корневого домена нужного типа, который ещё не был Main. Укажите типы доменов в Сетке.')


def select_unused_xdefault(site, state, cfg, target):
    def root_name(value):
        return domain_name(value).removeprefix('www.')
    observed = alternate_links(state['alternateMarkup'].replace('{{settings.canon}}', state['canon']).replace('{{reqPath}}', '/'))
    used = {root_name(value) for value in [
        *(site.main_domain_history or []),
        *(getattr(site, 'x_default_history', None) or []),
        *(getattr(site, 'alternate_domain_history', None) or []),
        state['canon'], state.get('prev'), target,
        *(link['domain'] for link in observed),
    ]}
    types = getattr(site, 'domain_types', None) or {}
    required_type = 'newreg' if cfg.x_default_use_newreg else 'drop'
    for domain in state['domains']:
        if domain in state.get('amp_domains', []):
            continue
        bare = root_name(domain)
        if not bare or any(value == bare or value.endswith('.' + bare) for value in used) or types.get(domain) != required_type:
            continue
        if any(bare.endswith('.' + root_name(parent)) for parent in state['domains'] if root_name(parent) != bare):
            continue
        return domain
    label = 'новорега' if cfg.x_default_use_newreg else 'дропа'
    raise ValueError(f'В сетке нет неиспользованного {label} для x-default. Проверьте типы доменов и историю использования.')


def effective_project_config(global_cfg, cfg):
    if cfg.scope != 'personal' and global_cfg.apply_domain_settings:
        return cfg.model_copy(update=global_cfg.domain_settings.model_dump())
    return cfg


def effective_config(global_cfg, cfg):
    if cfg.scope == 'personal':
        return GlobalConfig(enabled=cfg.enabled, schedule_enabled=cfg.schedule_enabled,
            interval_days=cfg.interval_days, scheme_mode=cfg.scheme_mode,
            auxiliary_hreflangs=cfg.auxiliary_hreflangs)
    return global_cfg


def require_eligible(site, global_cfg, cfg):
    if cfg.scope != 'personal' and site.project_status != 'mass_actions':
        raise ValueError('Проект не имеет статуса «Массовые действия».')
    if not effective_config(global_cfg, cfg).enabled or not cfg.enabled:
        raise ValueError('Автопереклей выключен в настройках.')



def build_plan(site, state, global_cfg, cfg):
    require_eligible(site, global_cfg, cfg)
    cfg = effective_project_config(global_cfg, cfg)
    global_cfg = effective_config(global_cfg, cfg)
    geo = (site.cache_geo or '').strip().upper()
    if not re.fullmatch(r'[A-Z]{2}', geo):
        raise ValueError('В проекте должно быть задано GEO из двух букв.')
    language = (getattr(site, 'cache_language', None) or cfg.language).strip().lower().replace('_', '-').split('-')[0]
    if not re.fullmatch(r'[a-z]{2,3}', language):
        raise ValueError('В проекте должен быть задан код языка, например az.')
    if not state.get('has_head'):
        raise ValueError('Не получены данные head проекта.')
    if cfg.domain_layout == 'root_main':
        target, language_host = select_root_and_subdomain(site, state, cfg)
        x_default = target
    else:
        target = select_next_domain(site, state, cfg)
        language_host = target
        x_default = (select_unused_xdefault(site, state, cfg, target) if global_cfg.scheme_mode == 'base_only'
                     else cfg.x_default_newreg_domain if cfg.x_default_use_newreg else cfg.drop_domain)
    if not x_default:
        raise ValueError('Укажите новорег для x-default.' if cfg.x_default_use_newreg else 'Укажите дроп для x-default.')
    if any(domain in state.get('amp_domains', []) for domain in (target, language_host, x_default)):
        raise ValueError('AMP-домены не участвуют в автопереклеях, включая альтернейты и x-default.')
    known_type = (getattr(site, 'domain_types', None) or {}).get(x_default)
    if known_type == 'newreg' and not cfg.x_default_use_newreg:
        raise ValueError('Домен x-default отмечен как новорег. Включите разрешение новорега в x-default.')
    if known_type == 'drop' and cfg.x_default_use_newreg:
        raise ValueError('Домен x-default отмечен как дроп. Выключите режим новорега или выберите новорег.')
    validate_markup(state['alternateMarkup'])
    source = []
    if cfg.profile_id:
        profile = next((p for p in template_catalog() if p['id'] == cfg.profile_id), None)
        if not profile or domain_name(profile['project']) != domain_name(site.name) or profile['geo'] != geo or profile['language'] != language:
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
            links[key] = {'hreflang': link['hreflang'], 'href': urlunsplit(('https', language_host, url.path or '/', url.query, url.fragment)).replace('/__auto_request_path__', '{{reqPath}}')}
    links[language] = {'hreflang': language, 'href': f'https://{language_host}/'}
    regional = f'{language}-{geo}'
    regional_link = links.get(regional.lower())
    regional_path = cfg.fake_main_path or (urlsplit(regional_link['href']).path if regional_link else '')
    if not regional_path or regional_path == '/':
        raise ValueError('Укажите путь внутренней копии главной для альтернейта язык-GEO, например /events/.')
    links[regional.lower()] = {'hreflang': regional, 'href': f'https://{language_host}{regional_path}'}
    if global_cfg.scheme_mode == 'base_only':
        links = {language: links[language], regional.lower(): links[regional.lower()]}
    added_hreflang = None
    if global_cfg.scheme_mode == 'add_auxiliary':
        lang = next((lang for lang in global_cfg.auxiliary_hreflangs if lang.lower() not in links and lang.lower() != language and lang.split('-')[-1].upper() != geo), None)
        if lang:
            added_hreflang = lang
            links[lang.lower()] = {'hreflang': lang, 'href': f'https://{language_host}/'}
    links['x-default'] = {'hreflang': 'x-default', 'href': f'https://{x_default}/'}
    markup = '\n'.join(f'<link rel="alternate" hreflang="{escape(x["hreflang"], quote=True)}" href="{escape(x["href"], quote=True)}" />' for x in links.values())
    validate_markup(markup)
    plan = {'create_subdomain': language_host if cfg.create_subdomains else None, 'site_id': site.id, 'project': site.name, 'geo': geo, 'old_main': state['canon'], 'new_main': target,
            'drop_domain': cfg.drop_domain, 'domain_layout': cfg.domain_layout, 'language_domain': language_host, 'x_default_domain': x_default, 'x_default_use_newreg': cfg.x_default_use_newreg, 'parent_kind': cfg.parent_kind, 'scope': cfg.scope, 'scheme_mode': global_cfg.scheme_mode, 'alternateMarkup': markup,
            'required_page_urls': list(dict.fromkeys(x['href'] for x in links.values() if '{{reqPath}}' not in x['href'] and urlsplit(x['href']).path not in {'', '/'})),
            'added_hreflang': added_hreflang, 'pool_exhausted': global_cfg.scheme_mode == 'add_auxiliary' and added_hreflang is None,
            'revision': state.get('revision') or state_revision(state), 'config_hash': digest([global_cfg.model_dump(), cfg.model_dump()])}
    classification = classify_domains(state['domains'], getattr(site, 'domain_types', None) or {}, site.main_domain_history or [], state['canon'])
    plan['domain_classification'] = {domain: classification.get(domain) for domain in {target, language_host, x_default}}
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


def prepare_run(db, site, request_id, token, username, scope=None):
    if scope == 'mass' and config(db, site.id).scope == 'personal':
        raise ValueError('У проекта персональные настройки: участие в массовом автопереклее запрещено.')
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
            if not site: raise ValueError('Проект не найден.')
            cfg = config(db, site.id)
            if plan.get('scope', 'mass') != cfg.scope: raise ValueError('Режим участия изменился; запуск остановлен.')
            require_eligible(site, config(db), cfg)
            if plan.get('scheduled') and not effective_config(config(db), cfg).schedule_enabled: raise ValueError('Расписание выключено.')
            state = project_network.read_network(db, site)
            if run.phase == 'prepared':
                current = build_plan(site, state, config(db), config(db, site.id))
                if current['preview_token'] != plan['preview_token']: raise ValueError('Состояние изменилось до начала запуска. Нужен новый предпросмотр.')
                if not plan.get('create_subdomain'):
                    verify_pages(plan['required_page_urls'])
            if plan.get('create_subdomain') and run.phase in {'prepared', 'create_subdomains', 'subdomain_ready'}:
                target = plan['create_subdomain']
                receipt = str(uuid5(UUID(run.id), 'create_subdomains'))
                existing = db.get(models.NetworkOperation, receipt)
                if not existing:
                    if state['canon'] != plan['old_main']:
                        raise ValueError('Canonical изменился до создания поддомена. Подготовьте новый план.')
                    if target in state['domains']:
                        raise ValueError('Поддомен появился после подготовки плана. Подготовьте новый план.')
                    run.phase = 'create_subdomains'; run.status = 'running'; db.commit()
                    payload = project_network.NetworkChange(request_id=UUID(receipt), action='create_subdomains', revision=state['revision'], domains=[target])
                    project_network.change_network(db, site, payload, run.initiator, auto_run_id=run.id)
                    existing = db.get(models.NetworkOperation, receipt)
                db.refresh(existing)
                if existing.status == 'failed':
                    raise ValueError(existing.message or 'Создание поддомена завершилось ошибкой.')
                if existing.status != 'confirmed':
                    run.status = 'waiting'; run.message = 'Поддомен создаётся. Ждём подтверждения Webdev без повторной отправки.'; db.commit(); return
                run.phase = 'subdomain_ready'; db.commit()
                try:
                    verify_pages(list(dict.fromkeys(['https://' + target + '/', *plan['required_page_urls']])))
                except (httpx.HTTPError, ValueError):
                    run.status = 'waiting'; run.message = 'Поддомен добавлен. Ждём HTTPS и доступности страниц схемы; Main ещё не меняем.'; db.commit(); return
            run.status = 'running'; db.commit()
            for action in ['reserve', 'reglue', 'alternates']:
                db.refresh(run)
                if run.status == 'cancelled': return
                db.refresh(site)
                cfg = config(db, site.id)
                if plan.get('scope', 'mass') != cfg.scope: raise ValueError('Режим участия изменился; запуск остановлен.')
                require_eligible(site, config(db), cfg)
                if plan.get('scheduled') and not effective_config(config(db), cfg).schedule_enabled: raise ValueError('Расписание выключено.')
                receipt = str(uuid5(UUID(run.id), action))
                existing = db.get(models.NetworkOperation, receipt)
                state = project_network.read_network(db, site)
                if existing:
                    db.refresh(existing)
                    if existing.status == 'confirmed': continue
                    if existing.status == 'failed': raise ValueError(existing.message or 'Ошибка Webdev.')
                    run.status = 'waiting'; run.message = 'Ожидается подтверждение Webdev. Проверяем результат чтением настроек без повторной записи.'; db.commit(); return
                if any(plan.get(key) in state.get('amp_domains', []) for key in ('new_main', 'language_domain', 'x_default_domain')):
                    raise ValueError('Домен плана теперь относится к AMP. Переклей остановлен.')
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


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def schedule_eligible(site, global_cfg, cfg):
    rules = effective_config(global_cfg, cfg)
    return bool(cfg.enabled and rules.enabled and rules.schedule_enabled
                and (cfg.scope == 'personal' or site.project_status == 'mass_actions'))


def legacy_due(db, site, cfg, rules):
    anchors = []
    for key in ((site.id,) if cfg.scope == 'personal' else ('global', site.id)):
        row = db.get(models.AutoReglueConfig, key)
        if row and row.value.get('_schedule_since'):
            anchors.append(utc(datetime.fromisoformat(row.value['_schedule_since'])))
    if not anchors:
        return None
    last = db.scalar(select(models.AutoReglueRun).where(models.AutoReglueRun.site_id == site.id)
                     .order_by(models.AutoReglueRun.updated_at.desc()).limit(1))
    if last:
        anchors.append(utc(last.updated_at))
    return max(anchors) + timedelta(days=rules.interval_days)


def sync_schedules(db, now, immediate=None):
    global_cfg = config(db)
    sites = db.scalars(select(models.Site).join(models.AutoReglueConfig, models.AutoReglueConfig.key == models.Site.id)).all()
    for site in sites:
        cfg = config(db, site.id)
        rules = effective_config(global_cfg, cfg)
        enabled = schedule_eligible(site, global_cfg, cfg)
        row = db.get(models.AutoReglueSchedule, site.id)
        if row is None and enabled:
            first = None if immediate == site.id or immediate == 'global' and cfg.scope == 'mass' else legacy_due(db, site, cfg, rules)
            first = first or now
            row = models.AutoReglueSchedule(site_id=site.id, enabled=True, interval_days=rules.interval_days,
                anchor_at=first, next_run_at=first)
            db.add(row)
        elif row is not None:
            row.enabled = enabled
            if row.interval_days != rules.interval_days:
                row.interval_days = rules.interval_days
                # Period changes are measured from the last scheduled slot, never from a save.
                if rules.interval_days == 0:
                    row.last_scheduled_at = None
                    row.anchor_at = now
                    row.next_run_at = now
                elif row.last_scheduled_at:
                    row.next_run_at = utc(row.last_scheduled_at) + timedelta(days=rules.interval_days)
    db.flush()


def next_scheduled_at(db, site):
    cfg = config(db, site.id)
    if not schedule_eligible(site, config(db), cfg):
        return None
    row = db.get(models.AutoReglueSchedule, site.id)
    return utc(row.next_run_at) if row and row.enabled and not (row.interval_days == 0 and row.last_scheduled_at) else None


def advance_schedule(row, due, now):
    row.last_scheduled_at = due
    if row.interval_days == 0:
        return
    interval = timedelta(days=row.interval_days)
    # Keep the calendar anchored; collapse missed slots to one run after downtime.
    row.next_run_at = due + interval * (max(0, (now - due) // interval) + 1)


def schedule_tick(db, enqueue, now=None):
    now = utc(now or datetime.now(timezone.utc))
    started = []
    with project_network.network_lock(db, 'auto-schedule'):
        sync_schedules(db, now)
        db.commit()
        settings = config(db)
        schedules = db.scalars(select(models.AutoReglueSchedule).where(models.AutoReglueSchedule.enabled.is_(True))
                               .order_by(models.AutoReglueSchedule.next_run_at, models.AutoReglueSchedule.site_id)).all()
        for schedule in schedules:
            if len(started) >= settings.max_projects:
                break
            site = db.get(models.Site, schedule.site_id)
            pending = active_run(db, site.id)
            if pending:
                if pending.status == 'queued' and pending.plan.get('scheduled'):
                    enqueue(pending.id)  # Recover commit -> queue failures using the same receipt.
                    started.append(pending.id)
                continue
            if schedule.interval_days == 0 and schedule.last_scheduled_at:
                continue
            due = utc(schedule.next_run_at)
            if due > now:
                continue
            request_id = str(uuid5(NAMESPACE_URL, f'auto-reglue:{site.id}:{due.isoformat()}'))
            try:
                plan = preview(db, site)
                status, message = 'queued', None
            except (ValueError, httpx.HTTPError, ProjectCacheError) as error:
                db.rollback()
                plan, status, message = {'project': site.name}, 'failed', str(error)[:2000]
            # Atomic durable receipt + advancement; crash/retry cannot consume the same slot twice.
            with project_network.network_lock(db, site.id):
                db.refresh(schedule, with_for_update=True)
                if active_run(db, site.id):
                    continue
                existing = db.get(models.AutoReglueRun, request_id)
                if existing is None:
                    run = models.AutoReglueRun(id=request_id, site_id=site.id, initiator='scheduler',
                        status=status, phase='prepared', plan={**plan, 'scheduled': True, 'scheduled_for': due.isoformat()},
                        message=message)
                    db.add(run)
                else:
                    run = existing
                advance_schedule(schedule, due, now)
                db.commit()
            started.append(run.id)
            if run.status == 'queued':
                enqueue(run.id)
    return started
