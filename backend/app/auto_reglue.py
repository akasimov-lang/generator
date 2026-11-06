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
from pydantic import BaseModel, Field, field_validator, model_validator, model_serializer
from sqlalchemy import select

from app import models, project_network
from app.mass_action_reports import refresh_run
from app.subdomain_naming import next_subdomain
from app.fake_main import normalize_fake_path, next_fake_path, fake_canonical_markup
from app.domain_classification import classify_domains
from app.alternate_templates import template_catalog
from app.alternate_language_pool import default_language_pool
from app.project_cache import ProjectCacheError
from app.network_state import alternate_links, domain_name, state_revision, validate_markup
from app.mass_action_scope import MassActionFilter, matches as matches_mass_filter, stamp_plan

ACTIVE = ('planned', 'queued', 'running', 'waiting', 'partial')


class DomainOptions(BaseModel):
    domain_layout: Literal['subdomain_main', 'root_main'] = 'subdomain_main'
    parent_kind: Literal['drop', 'newreg'] = 'drop'
    create_subdomains: bool = False
    create_fake_main: bool = False
    use_current_fake_main: bool = False
    subdomain_add_casino: bool = False
    subdomain_name_style: Literal['mixed', 'joined', 'hyphen'] = 'mixed'
    x_default_use_newreg: bool = False

    @model_validator(mode='after')
    def fake_mode(self):
        if self.create_fake_main and self.use_current_fake_main:
            raise ValueError('Выберите один режим фейковой страницы: новая или текущая.')
        return self


class GlobalConfig(BaseModel):
    selection_filter: MassActionFilter | None = None
    execution_mode: Literal["within_network", "cross_network", "transfer_only"] = "within_network"
    apply_domain_settings: bool = False
    domain_settings: DomainOptions = Field(default_factory=DomainOptions)
    enabled: bool = False
    schedule_enabled: bool = False
    interval_days: Literal[0, 3, 4, 5, 7, 14] = 0
    scheme_mode: Literal["preserve", "add_auxiliary", "base_only", "clean", "locale_base"] = "preserve"
    auxiliary_hreflangs: list[str] = Field(default_factory=default_language_pool, max_length=200)
    max_projects: int = Field(default=20, ge=1, le=100)
    main_target_mode: Literal['legacy', 'newreg', 'drop', 'mixed'] = 'legacy'
    title_h1_rewrite_percent: int = Field(default=20, ge=0, le=100, strict=True)
    newreg_subdomain_share: bool = False
    drop_subdomain_share: bool = False

    @model_serializer(mode='wrap')
    def stable_legacy_snapshot(self, handler):
        values = handler(self)
        if self.title_h1_rewrite_percent == 20: values.pop('title_h1_rewrite_percent', None)
        # Do not invalidate already reserved legacy operations merely by adding
        # an unset filter field to the configuration fingerprint.
        if self.selection_filter is None:
            values.pop('selection_filter', None)
        if self.main_target_mode == 'legacy' and not self.newreg_subdomain_share and not self.drop_subdomain_share:
            for key in ('main_target_mode', 'newreg_subdomain_share', 'drop_subdomain_share'):
                values.pop(key, None)
        return values

    @model_validator(mode='after')
    def manual_transfer_only(self):
        if self.execution_mode == 'transfer_only' and self.schedule_enabled:
            raise ValueError('Перераспределение без переклея запускается вручную, не более двух доменов за нажатие.')
        return self

    @model_validator(mode='after')
    def target_shares(self):
        if self.main_target_mode == 'legacy' and (self.newreg_subdomain_share or self.drop_subdomain_share):
            raise ValueError('Для долей поддоменов выберите тип Main: новореги, дропы или смешанный цикл.')
        if self.main_target_mode == 'newreg' and self.drop_subdomain_share:
            raise ValueError('В режиме «Только новореги» поддомены дропов не используются.')
        if self.main_target_mode == 'drop' and self.newreg_subdomain_share:
            raise ValueError('В режиме «Только дропы» поддомены новорегов не используются.')
        return self

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
    scheme_mode: Literal["preserve", "add_auxiliary", "base_only", "clean"] = "preserve"
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
    create_fake_main: bool = False
    use_current_fake_main: bool = False
    subdomain_add_casino: bool = False
    subdomain_name_style: Literal["mixed", "joined", "hyphen"] = "mixed"
    newreg_domain: str = Field(default='', max_length=253)
    language: str = Field(default='', max_length=15)
    profile_id: str = Field(default='', max_length=300)
    variant: Literal['provided', 'before', 'after', 'current'] = 'current'
    fake_main_path: str = Field(default='', max_length=250)

    @model_validator(mode='after')
    def fake_mode(self):
        if self.create_fake_main and self.use_current_fake_main:
            raise ValueError('Выберите один режим фейковой страницы: новая или текущая.')
        return self

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


def saved_project_rules(value):
    # Personal scheduling controls participation; retain rules when it is disabled.
    return value.model_copy(update={'scope': 'personal' if value.schedule_enabled else 'mass'})


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


def select_next_domain(site, state, cfg, *, allocation_index=None):
    from app.domain_transfer_policy import blocked_transfer_zone
    parent = (cfg.drop_domain if cfg.parent_kind == 'drop' else cfg.newreg_domain).removeprefix('www.')
    if not parent:
        raise ValueError('Укажите родительский домен выбранного варианта.')
    if blocked_transfer_zone(parent):raise ValueError('Родительский домен отмечен БАН: запрещённая зона.')
    if cfg.create_subdomains:
        return next_subdomain(site, state, cfg, parent, allocation_index=allocation_index)
    domains = [domain for domain in state['domains'] if domain not in state.get('amp_domains', []) and not blocked_transfer_zone(domain)]
    start = domains.index(state['canon']) + 1 if state['canon'] in domains else 0
    used = {domain_name(x) for x in [*(site.main_domain_history or []), state['canon'], state.get('prev')]}
    # No wrap and no recycling of former Main domains.
    for domain in domains[start:]:
        if domain.endswith('.' + parent) and domain not in used:
            return domain
    raise ValueError('После текущего Main нет неиспользованного поддомена выбранного дропа/новорега. Добавьте резерв в сетку.')


def select_root_and_subdomain(site, state, cfg, *, allocation_index=None):
    from app.domain_transfer_policy import blocked_transfer_zone
    domains = [domain for domain in state['domains'] if domain not in state.get('amp_domains', []) and not blocked_transfer_zone(domain)]
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
            return root, next_subdomain(site, state, cfg, root, allocation_index=allocation_index)
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


def require_eligible(site, global_cfg, cfg, *, preview_only=False, manual=False):
    if getattr(site, 'reglue_participation', True) is False:
        raise ValueError('Участвует в переклее: Нет.')
    if cfg.scope != 'personal' and site.project_status != 'mass_actions':
        raise ValueError('Проект не имеет статуса «Массовые действия».')
    if not preview_only and not manual and not effective_config(global_cfg, cfg).enabled:
        raise ValueError('Автопереклей выключен в настройках.')



def build_plan(site, state, global_cfg, cfg, *, db=None):
    from app.mass_reglue_launch import manual_pilot_allowed
    require_eligible(site, global_cfg, cfg, preview_only=bool(db and db.info.get('auto_pilot_preview')),manual=bool(db and manual_pilot_allowed(db,site.id)))
    cfg = effective_project_config(global_cfg, cfg)
    global_cfg = effective_config(global_cfg, cfg)
    naming_index = None
    if db is not None and cfg.scope == 'mass':
        from app.naming_variants import allocation_index
        saved = db.info.get('canonical_replay_plan')
        naming_index = (saved.get('naming_allocation_index') if saved else
                        allocation_index(db.info.get('canonical_allocation_plans', []), site.id, subdomains=True))
    if db is not None and 'auto_pilot_preview' in db.info and cfg.scope == 'mass' and cfg.use_current_fake_main:
        cfg = cfg.model_copy(update={'use_current_fake_main': False, 'create_fake_main': True})
    locale_base = global_cfg.scheme_mode == 'locale_base'
    geo = (site.cache_geo or '').strip().upper()
    if locale_base:
        geo = geo.replace('_', '-').split('-')[-1]
        cfg = cfg.model_copy(update={'create_fake_main': True, 'use_current_fake_main': False,
                                     'profile_id': ''})
    if not re.fullmatch(r'[A-Z]{2}', geo):
        raise ValueError('В проекте должно быть задано GEO из двух букв.')
    language = (getattr(site, 'cache_language', None) or cfg.language).strip().lower().replace('_', '-').split('-')[0]
    if not re.fullmatch(r'[a-z]{2,3}', language):
        raise ValueError('В проекте должен быть задан код языка, например az.')
    if not state.get('has_head'):
        raise ValueError('Не получены данные head проекта.')
    if global_cfg.scheme_mode in {'clean', 'locale_base'} and cfg.domain_layout == 'root_main':
        used = {domain_name(d) for d in [*(site.main_domain_history or []), state['canon'], state.get('prev')]}
        roles = classify_domains(state['domains'], site.domain_types or {})
        from app.domain_transfer_policy import blocked_transfer_zone
        target = next((d for d in state['domains'] if not blocked_transfer_zone(d) and d not in used and d not in state.get('amp_domains', []) and not roles[d]['is_subdomain'] and (site.domain_types or {}).get(d) == cfg.parent_kind), None)
        if not target:
            raise ValueError('Нет неиспользованного корневого домена выбранного типа.')
        language_host = target; x_default = ''
    elif cfg.domain_layout == 'root_main':
        target, language_host = select_root_and_subdomain(site, state, cfg, allocation_index=naming_index)
        x_default = target
    else:
        target = select_next_domain(site, state, cfg, allocation_index=naming_index)
        language_host = target
        x_default = (select_unused_xdefault(site, state, cfg, target) if global_cfg.scheme_mode == 'base_only'
                     else cfg.x_default_newreg_domain if cfg.x_default_use_newreg else cfg.drop_domain)
    if global_cfg.scheme_mode == 'clean':
        plan = {'scope': cfg.scope, 'scheme_mode': 'clean', 'site_id': site.id, 'project': site.name, 'geo': geo,
                'old_main': state['canon'], 'new_main': target, 'alternateMarkup': '', 'enableAlternates': False,
                'alternates_before': {'markup': state['alternateMarkup'], 'enabled': state['enableAlternates']},
                'required_page_urls': ['https://' + target + '/'],
                'create_subdomain': target if cfg.create_subdomains and cfg.domain_layout != 'root_main' else None,
                'revision': state.get('revision') or state_revision(state), 'config_hash': digest([global_cfg.model_dump(), cfg.model_dump()])}
        if naming_index is not None: plan['naming_allocation_index'] = naming_index
        plan['preview_token'] = digest(plan)
        return plan
    if locale_base:
        language_host = x_default = target
    if not x_default:
        raise ValueError('Укажите новорег для x-default.' if cfg.x_default_use_newreg else 'Укажите дроп для x-default.')
    if any(domain in state.get('amp_domains', []) for domain in (target, language_host, x_default)):
        raise ValueError('AMP-домены не участвуют в автопереклеях, включая альтернейты и x-default.')
    known_type = (getattr(site, 'domain_types', None) or {}).get(x_default)
    if not locale_base and known_type == 'newreg' and not cfg.x_default_use_newreg:
        raise ValueError('Домен x-default отмечен как новорег. Включите разрешение новорега в x-default.')
    if not locale_base and known_type == 'drop' and cfg.x_default_use_newreg:
        raise ValueError('Домен x-default отмечен как дроп. Выключите режим новорега или выберите новорег.')
    if not locale_base:
        validate_markup(state['alternateMarkup'])
    source = []
    if cfg.profile_id:
        profile = next((p for p in template_catalog() if p['id'] == cfg.profile_id), None)
        if not profile or domain_name(profile['project']) != domain_name(site.name) or profile['geo'] != geo or profile['language'] != language:
            raise ValueError('Шаблон не соответствует проекту или GEO.')
        if cfg.variant not in profile['variants']:
            raise ValueError('Эта версия схемы не заполнена; выберите существующую.')
        source = profile['variants'][cfg.variant]['links']
    fake_enabled = cfg.create_fake_main or cfg.use_current_fake_main
    links = {}
    for link in ([] if locale_base else [*source, *alternate_links(state['alternateMarkup'])]):
        key = link['hreflang'].lower()
        if key != 'x-default' and key not in links:
            # Canon and all language variants move together; paths are retained.
            url = urlsplit(link['href'].replace('{{settings.canon}}', target).replace('{{reqPath}}', '/__auto_request_path__'))
            links[key] = {'hreflang': link['hreflang'], 'href': urlunsplit(('https', language_host, (url.path or '/') if fake_enabled else '/', url.query if fake_enabled else '', url.fragment if fake_enabled else '')).replace('/__auto_request_path__', '{{reqPath}}')}
    links[language] = {'hreflang': language, 'href': f'https://{language_host}/'}
    regional = f'{language}-{geo}'
    regional_path = '/'
    if cfg.create_fake_main:
        if db is not None:
            from app.fake_path_allocation import next_path
            regional_path = next_path(db, site, state, cfg)
        elif locale_base:
            from app.alternate_templates import next_base_fake_path
            regional_path = next_base_fake_path(site, state, language, geo)
        else:
            regional_path = next_fake_path(site, state, cfg)
    elif cfg.use_current_fake_main:
        current = state.get('fake_main_current')
        if not current or not state.get('fake_main_enabled'):
            raise ValueError('У проекта нет включённой текущей фейковой страницы. Выберите создание новой или режим без фейковых страниц.')
        regional_path = normalize_fake_path(current)
        if regional_path not in state.get('fake_main_paths', []):
            raise ValueError('Текущий фейковый путь отсутствует в списке страниц проекта.')
        if db is not None:
            from app.fake_path_allocation import require_available
            require_available(db, site, regional_path)
    links[regional.lower()] = {'hreflang': regional, 'href': f'https://{language_host}{regional_path}'}
    if global_cfg.scheme_mode in {'base_only', 'locale_base'}:
        links = {language: links[language], regional.lower(): links[regional.lower()]}
    added_hreflang = None
    if global_cfg.scheme_mode == 'add_auxiliary':
        lang = next((lang for lang in global_cfg.auxiliary_hreflangs if lang.lower() not in links and lang.lower() != language and lang.split('-')[-1].upper() != geo), None)
        if lang:
            added_hreflang = lang
            links[lang.lower()] = {'hreflang': lang, 'href': f'https://{language_host}/'}
    links['x-default'] = {'hreflang': 'x-default', 'href': f'https://{x_default}/'}
    markup = '\n'.join(f'<link rel="alternate" hreflang="{escape(x["hreflang"], quote=True)}" href="{escape(x["href"], quote=True)}" />' for x in links.values())
    if locale_base:
        from app.alternate_templates import base_alternate_markup
        markup = base_alternate_markup(target, language, geo, regional_path)
    validate_markup(markup)
    plan = {'create_fake_main_path': regional_path if cfg.create_fake_main else None, 'create_subdomain': language_host if cfg.create_subdomains else None, 'site_id': site.id, 'project': site.name, 'geo': geo, 'old_main': state['canon'], 'new_main': target,
            'fake_main_path': regional_path if fake_enabled else None,
            'canonicalFakeMainMarkup': fake_canonical_markup(regional_path) if fake_enabled else None,
            'drop_domain': cfg.drop_domain, 'domain_layout': cfg.domain_layout, 'language_domain': language_host, 'x_default_domain': x_default, 'x_default_use_newreg': cfg.x_default_use_newreg, 'parent_kind': cfg.parent_kind, 'scope': cfg.scope, 'scheme_mode': global_cfg.scheme_mode, 'alternateMarkup': markup,
            'required_page_urls': list(dict.fromkeys(x['href'] for x in links.values() if '{{reqPath}}' not in x['href'] and urlsplit(x['href']).path not in {'', '/'})),
            'added_hreflang': added_hreflang, 'pool_exhausted': global_cfg.scheme_mode == 'add_auxiliary' and added_hreflang is None,
            'revision': state.get('revision') or state_revision(state), 'config_hash': digest([global_cfg.model_dump(), cfg.model_dump()])}
    classification = classify_domains(state['domains'], getattr(site, 'domain_types', None) or {}, site.main_domain_history or [], state['canon'])
    plan['domain_classification'] = {domain: classification.get(domain) for domain in {target, language_host, x_default}}
    if db is None or not db.info.get('canonical_replay_plan'):
        plan['planning_options'] = cfg.model_dump()
        plan['language'] = language
    if naming_index is not None: plan['naming_allocation_index'] = naming_index
    plan['alternates_before'] = {'markup': state['alternateMarkup'], 'enabled': state['enableAlternates']}
    plan['preview_token'] = digest(plan)
    return plan


def execution_config(db, site_id, launch_scope=None):
    cfg = config(db, site_id)
    if launch_scope == 'project':
        # Explicit project launch uses local rules without enabling its schedule.
        cfg = cfg.model_copy(update={'scope': 'personal', 'enabled': True})
    return cfg


def launch_plan(db, site, state, launch_scope=None):
    plan = build_plan(site, state, config(db), execution_config(db, site.id, launch_scope), db=db)
    from app.canonical_allocation import apply
    apply(db, site, plan)
    plan.pop('preview_token', None)
    plan['preview_token'] = digest(plan)
    if launch_scope == 'project':
        plan['launch_scope'] = 'project'
        plan.pop('preview_token')
        plan['preview_token'] = digest(plan)
    return plan


def preview(db, site, launch_scope=None):
    state = project_network.read_network(db, site)
    if launch_scope != 'project' and config(db, site.id).scope != 'personal' and not db.info.get('mass_action_filter') and config(db).selection_filter:
        db.info['mass_action_filter'] = config(db).selection_filter.model_dump()
    if launch_scope != 'project' and config(db).execution_mode == 'transfer_only' and config(db, site.id).scope != 'personal':
        from app.domain_redistribution import preview as transfer_preview
        plan = transfer_preview(db, site, state)
    elif launch_scope != 'project' and config(db).execution_mode == 'cross_network' and config(db, site.id).scope != 'personal':
        from app.cross_reglue import preview as cross_preview
        plan = cross_preview(db, site, state)
    else:
        plan = launch_plan(db, site, state, launch_scope)
    return stamp_plan(db, plan, state, site) if launch_scope != 'project' and config(db, site.id).scope != 'personal' else plan


def active_participants(db):
    # Cross-network integrity includes a visible donor reserved by a hidden target.
    columns = models.AutoReglueRun.__table__.c
    return db.execute(select(columns.id, columns.site_id, columns.plan, columns.status)
                      .where(columns.status.in_(ACTIVE)))


def active_run(db, site_id):
    return next((run for run in active_participants(db)
                 if run.site_id == site_id or run.plan.get('source_site_id') == site_id), None)


def blocking_run(db, site_id, permitted):
    for run in active_participants(db):
        if run.site_id != site_id and run.plan.get('source_site_id') != site_id:
            continue
        if permitted and run.id == permitted.id:
            continue
        if (permitted and permitted.plan.get('batch_id')
                and run.plan.get('batch_id') == permitted.plan['batch_id']
                and site_id in {permitted.site_id, permitted.plan.get('source_site_id')}):
            continue
        return run
    return None


def serialize(run):
    from sqlalchemy.orm import object_session
    from app.domain_transfer_queue import progress
    from app.transfer_confirmation import view as confirmation_view
    db=object_session(run)
    return {'id': run.id, 'site_id': run.site_id, 'status': run.status, 'phase': run.phase,
            'message': run.message, 'plan': run.plan, 'created_at': run.created_at, 'confirmation': confirmation_view(run),
            'domain_progress': progress(db,run) if db and not run.plan.get('local_target') and run.plan.get('execution_mode') in {'transfer_only','cross_network'} else []}


def prepare_run(db, site, request_id, token, username, scope=None, saved_plan=None):
    if scope == 'mass' and config(db, site.id).scope == 'personal':
        raise ValueError('У проекта персональные настройки: участие в массовом автопереклее запрещено.')
    existing = db.get(models.AutoReglueRun, str(request_id))
    if existing:
        if existing.site_id != site.id: raise ValueError('Этот запуск принадлежит другому проекту.')
        if db.info.get('mass_action_filter') and existing.plan.get('mass_filter') != db.info['mass_action_filter']:
            raise ValueError('Идентификатор запуска уже использован с другим фильтром.')
        return existing, False
    from app.canonical_allocation import replay
    with replay(db, saved_plan):
        plan = preview(db, site, 'project') if scope == 'project' else preview(db, site)
    if plan['preview_token'] != token:
        raise project_network.NetworkConflict('Состояние изменилось после предпросмотра. Подготовьте план снова.')
    from app.cross_reglue import participant_locks
    from app.fake_path_allocation import group_lock, require_available
    with project_network.network_lock(db, 'reglue-reserve-pool'), participant_locks(db, site.id, plan), group_lock(db, site):
        existing = db.get(models.AutoReglueRun, str(request_id))
        if existing:
            if existing.site_id != site.id: raise ValueError('Этот запуск принадлежит другому проекту.')
            return existing, False
        if any(active_run(db, key) for key in {site.id, plan.get('source_site_id', site.id)}): raise project_network.NetworkConflict('Одна из сеток уже участвует в незавершённом автопереклее.')
        require_available(db, site, plan.get('fake_main_path'))
        run = models.AutoReglueRun(id=str(request_id), site_id=site.id, initiator=username, plan=plan, status='queued', phase='prepared')
        if plan.get('reserve_pool_id'):
            from app.reglue_reserves import validate_plan
            validate_plan(db, site, project_network.read_network(db, site), plan)
        db.add(run); db.flush()
        if plan.get('reserve_pool_id'):
            from app.reglue_reserves import claim
            claim(db, run)
        db.commit()
    return run, True


def verify_pages(urls):
    with httpx.Client(timeout=25, follow_redirects=False) as client:
        for url in urls:
            with client.stream('GET', url) as response:
                if response.status_code != 200:
                    raise ValueError(f'Страница копии главной не подтвердилась: {url} (HTTP {response.status_code}). Создайте её до запуска.')


def execute(db, run_id):
    from app.mass_reglue_launch import manual_pilot_allowed
    run=db.get(models.AutoReglueRun,run_id)
    previous=db.info.get('manual_pilot_job_id')
    db.info['manual_pilot_job_id']=run.plan.get('list_launch_id') if run and manual_pilot_allowed(db,run.site_id,run) else None
    try:return _execute(db,run_id)
    finally:
        if previous is None:db.info.pop('manual_pilot_job_id',None)
        else:db.info['manual_pilot_job_id']=previous


def _execute(db, run_id):
    # Separate lock serializes duplicate Celery deliveries across all phases.
    with project_network.network_lock(db, 'auto-run:' + run_id):
        run = db.get(models.AutoReglueRun, run_id)
        if run is None or run.status not in {'queued', 'waiting', 'running'}: return
        if run.plan.get('execution_mode') == 'transfer_only':
            from app.domain_redistribution import execute as execute_transfer
            return execute_transfer(db, run)
        if run.plan.get('execution_mode') == 'cross_network':
            from app.cross_reglue import execute as execute_cross
            return execute_cross(db, run)
        site = db.get(models.Site, run.site_id)
        plan = run.plan
        try:
            from app.pilot_schemes import validate_single_alternate
            validate_single_alternate(plan)
            if not site: raise ValueError('Проект не найден.')
            cfg = execution_config(db, site.id, plan.get('launch_scope'))
            if plan.get('scope', 'mass') != cfg.scope: raise ValueError('Режим участия изменился; запуск остановлен.')
            from app.mass_reglue_launch import manual_pilot_allowed
            require_eligible(site, config(db), cfg,manual=manual_pilot_allowed(db,site.id,run))
            if plan.get('scheduled') and not effective_config(config(db), cfg).schedule_enabled: raise ValueError('Расписание выключено.')
            state = project_network.read_network(db, site)
            if run.plan.get('waiting_for_network'):
                run.plan = {**run.plan, 'waiting_for_network': False}
            from app.subdomain_naming import validate_unstarted_plan
            validate_unstarted_plan(db, run, state)
            if run.plan.get('content_return_phase', run.phase) == 'prepared':
                from app.canonical_allocation import replay
                with replay(db, plan):
                    current = launch_plan(db, site, state, plan.get('launch_scope'))
                if plan.get('mass_filter'):
                    from app.mass_action_scope import require_run_scope
                    require_run_scope(db, run)
                    current = stamp_plan(db, current, state, site, plan['mass_filter'])
                if current['preview_token'] != plan['preview_token']: raise ValueError('Состояние изменилось до начала запуска. Нужен новый предпросмотр.')
            from app.reglue_content import before_network
            if not before_network(db, run, state): return
            if run.phase == 'prepared' and not plan.get('create_subdomain') and not plan.get('create_fake_main_path'):
                verify_pages(plan['required_page_urls'])
            if plan.get('create_fake_main_path') and run.phase in {'prepared', 'create_fake_main', 'fake_main_ready'}:
                fake_path = plan['create_fake_main_path']
                receipt = str(uuid5(UUID(run.id), 'create_fake_main'))
                existing = db.get(models.NetworkOperation, receipt)
                if not existing:
                    if fake_path in state.get('fake_main_paths', []) or fake_path in state.get('fake_main_history', []):
                        raise ValueError('Путь новой фейковой страницы уже занят. Подготовьте новый план.')
                    if state['canon'] != plan['old_main']:
                        raise ValueError('Canonical изменился до создания фейковой страницы.')
                    run.phase = 'create_fake_main'; run.status = 'running'; db.commit()
                    payload = project_network.NetworkChange(request_id=UUID(receipt), action='create_fake_main', revision=state['revision'], fake_main_path=fake_path, activate_fake_main=True)
                    project_network.change_network(db, site, payload, run.initiator, auto_run_id=run.id)
                    existing = db.get(models.NetworkOperation, receipt)
                if existing:
                    db.refresh(existing)
                    if existing.status == 'failed': raise ValueError(existing.message or 'Ошибка создания фейковой страницы.')
                    if existing.status != 'confirmed':
                        run.status = 'waiting'; run.message = 'Ждём подтверждения фейковой страницы без повторной отправки.'; db.commit(); return
                run.phase = 'fake_main_ready'; db.commit()
                if not plan.get('create_subdomain'):
                    try:
                        verify_pages(plan['required_page_urls'])
                    except (httpx.HTTPError, ValueError):
                        run.status = 'waiting'; run.message = 'Фейковая страница сохранена. Ждём её доступности до смены Main.'; db.commit(); return
                state = project_network.read_network(db, site)
            if plan.get('create_subdomain') and run.phase in {'prepared', 'fake_main_ready', 'create_subdomains', 'subdomain_ready'}:
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
            from app.reglue_settle import ready as provisioning_settled
            created = db.get(models.NetworkOperation, str(uuid5(UUID(run.id), 'create_subdomains')))
            if not provisioning_settled(db, run, created, state):
                return
            run.status = 'running'; db.commit()
            for action in ['reserve', 'reglue', 'alternates']:
                db.refresh(run)
                if run.status == 'cancelled': return
                db.refresh(site)
                cfg = execution_config(db, site.id, plan.get('launch_scope'))
                if plan.get('scope', 'mass') != cfg.scope: raise ValueError('Режим участия изменился; запуск остановлен.')
                require_eligible(site, config(db), cfg,manual=manual_pilot_allowed(db,site.id,run))
                if plan.get('scheduled') and not effective_config(config(db), cfg).schedule_enabled: raise ValueError('Расписание выключено.')
                receipt = str(uuid5(UUID(run.id), action))
                existing = db.get(models.NetworkOperation, receipt)
                state = project_network.read_network(db, site)
                if plan.get('fake_main_path') and (state.get('fake_main_current') != plan['fake_main_path']
                        or not state.get('fake_main_enabled') or plan['fake_main_path'] not in state.get('fake_main_paths', [])):
                    raise ValueError('Действующий фейковый внутряк изменился. Проверьте настройки проекта.')
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
                payload = project_network.NetworkChange(request_id=UUID(receipt), action=action, revision=state['revision'], domain=plan['new_main'], alternate_markup=plan['alternateMarkup'], enable_alternates=plan.get('enableAlternates', True),
                    fake_main_path=(plan.get('fake_main_path') or '') if action == 'alternates' else '',
                    canonical_fake_main_markup=plan.get('canonicalFakeMainMarkup') if action == 'alternates' else None)
                project_network.change_network(db, site, payload, run.initiator, auto_run_id=run.id)
                operation = db.get(models.NetworkOperation, receipt); db.refresh(operation)
                if operation.status == 'failed': raise ValueError(operation.message or 'Ошибка Webdev.')
                if operation.status != 'confirmed':
                    run.status = 'waiting'; run.message = operation.message; db.commit(); return
            from app.network_indexing import verified, queue_indexing
            state = project_network.read_network(db, site)
            if plan.get('fake_main_path') and (not state.get('enableCanonical')
                    or state.get('canonicalFakeMainMarkup') != plan['canonicalFakeMainMarkup']
                    or not state.get('fake_main_enabled') or state.get('fake_main_current') != plan['fake_main_path']
                    or plan['fake_main_path'] not in state.get('fake_main_paths', [])):
                run.status = 'waiting'; run.message = 'Ждём подтверждения текущего фейкового внутряка и его canonical.'; db.commit(); return
            if not verified(state, {'canon': plan['new_main'], 'alternateMarkup': plan['alternateMarkup'], 'enableAlternates': plan.get('enableAlternates', True)}):
                run.status = 'waiting'; run.message = 'Ждём подтверждения canonical и альтернейтов перед индексацией.'; db.commit(); return
            from app.network_sitemap import queue as queue_sitemap
            queue_sitemap(db, site, run.id, run.initiator); db.commit()
            queue_indexing(db, site, state, run.id, run.initiator)
            # Immutable report snapshot of confirmed settings, not just the preview.
            alternates_receipt = db.get(models.NetworkOperation, str(uuid5(UUID(run.id), 'alternates')))
            before = (alternates_receipt.request_payload or {}).get('alternates_before', plan.get('alternates_before'))
            run.plan = {**run.plan, 'alternates_before': before, 'alternates_after': {'markup': state['alternateMarkup'], 'enabled': state['enableAlternates']}, 'applied_result': {
                'project': site.name, 'old_main': plan['old_main'], 'new_main': state['canon'],
                'fake_main_path': state.get('fake_main_current') or None,
                'alternateMarkup': state['alternateMarkup'],
                'enableAlternates': state['enableAlternates'],
                'enableCanonical': state.get('enableCanonical', False),
                'canonicalFakeMainMarkup': state.get('canonicalFakeMainMarkup', ''),
                'canonicalFakeMainResolved': (state.get('canonicalFakeMainMarkup') or '').replace('{{settings.canon}}', state['canon']),
                'confirmed_at': datetime.now(timezone.utc).isoformat(),
            }}
            run.status = 'completed'; run.phase = 'completed'; run.message = 'Новый Main и альтернейты подтверждены.'; refresh_run(db, run); db.commit()
        except project_network.NetworkBusy as error:
            db.rollback(); db.refresh(run)
            run.plan = {**run.plan, 'waiting_for_network': True}
            run.status = 'waiting'; run.message = str(error); db.commit()
        except Exception as error:
            db.rollback(); run = db.get(models.AutoReglueRun, run_id)
            if run and run.status != 'cancelled':
                from app.reglue_content import failure_status
                run.status = 'partial' if run.phase in {'reglue', 'alternates'} else failure_status(db, run, True)
                run.message = str(error)[:2000]; refresh_run(db, run); db.commit()


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def schedule_eligible(site, global_cfg, cfg):
    rules = effective_config(global_cfg, cfg)
    if cfg.scope != 'personal' and (not global_cfg.selection_filter or not matches_mass_filter(site, global_cfg.selection_filter)):
        return False
    if cfg.scope != 'personal' and global_cfg.execution_mode == 'transfer_only':
        return False
    return bool(getattr(site, 'reglue_participation', True) is not False and rules.enabled and rules.schedule_enabled
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
    sites = db.scalars(select(models.Site)
        .outerjoin(models.AutoReglueConfig, models.AutoReglueConfig.key == models.Site.id)
        .outerjoin(models.AutoReglueSchedule, models.AutoReglueSchedule.site_id == models.Site.id)
        .where((models.Site.project_status == 'mass_actions') | models.AutoReglueConfig.key.is_not(None)
               | models.AutoReglueSchedule.site_id.is_not(None))).all()
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
    db.info.pop('mass_action_filter', None)
    db.info.pop('mass_participant_ids', None)
    db.info.pop('cross_allowed_site_ids', None)
    started = []
    with project_network.network_lock(db, 'auto-schedule'):
        sync_schedules(db, now)
        db.commit()
        settings = config(db)
        if settings.execution_mode == 'cross_network':
            from app.cross_reglue_batch import schedule
            started.extend(schedule(db, enqueue, now))
        schedules = db.scalars(select(models.AutoReglueSchedule).where(models.AutoReglueSchedule.enabled.is_(True))
                               .order_by(models.AutoReglueSchedule.next_run_at, models.AutoReglueSchedule.site_id)).all()
        for schedule in schedules:
            if len(started) >= settings.max_projects:
                break
            site = db.get(models.Site, schedule.site_id)
            if settings.execution_mode == 'cross_network' and config(db, site.id).scope != 'personal':
                continue
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
            from app.cross_reglue import participant_locks
            from app.fake_path_allocation import group_lock, require_available
            with participant_locks(db, site.id, plan), group_lock(db, site):
                db.refresh(schedule, with_for_update=True)
                if any(active_run(db, key) for key in {site.id, plan.get('source_site_id', site.id)}):
                    continue
                existing = db.get(models.AutoReglueRun, request_id)
                if existing is None:
                    if status == 'queued' and plan.get('fake_main_path'):
                        try:
                            plan = preview(db, site)
                            require_available(db, site, plan.get('fake_main_path'))
                        except (ValueError, ProjectCacheError, httpx.HTTPError) as error:
                            status, message = 'failed', str(error)[:2000]
                    run = models.AutoReglueRun(id=request_id, site_id=site.id, initiator='scheduler',
                        status=status, phase='prepared', plan={**plan, 'scheduled': True, 'scheduled_for': due.isoformat()},
                        message=message)
                    db.add(run)
                else:
                    run = existing
                advance_schedule(schedule, due, now)
                db.commit()
            if config(db, site.id).scope != 'personal' and settings.selection_filter:
                from app.mass_action_reports import save as save_report
                report_id = uuid5(NAMESPACE_URL, 'mass-schedule:' + digest(settings.selection_filter.model_dump()) + ':' + due.isoformat())
                save_report(db, report_id, settings.selection_filter.model_dump(), [{'site_id': site.id, 'run_id': run.id}], 'scheduler')
            started.append(run.id)
            if run.status == 'queued':
                enqueue(run.id)
    return started
