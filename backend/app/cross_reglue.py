"""Receipt-driven transfer between networks, followed by promotion to Main."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import re
import httpx
from uuid import UUID, uuid5
from sqlalchemy import select
from app import models, project_network as network
from app.domain_transfer_policy import banned_domains, domain_key, geo_key, policy_key, require_transfer_allowed
from app.network_state import alternate_links
from app.domain_classification import classify_domains


def brand_key(value):
    return re.sub(r'[^\w]', '', (value or '').casefold())


def require_pair(source, target):
    if not source or not target or source.id == target.id:
        raise ValueError('Для переноса нужны две разные сетки.')
    if not all(s.is_active and s.project_status == 'mass_actions' for s in (source, target)):
        raise ValueError('Обе сетки должны участвовать в массовых действиях.')
    brand = brand_key(source.brand)
    geo = geo_key(source.cache_geo)
    if not brand or brand == brand_key('Общие ключи') or brand != brand_key(target.brand):
        raise ValueError('Перенос разрешён только между сетками одного бренда.')
    if len(geo) != 2 or geo != geo_key(target.cache_geo):
        raise ValueError('Перенос разрешён только между сетками одного GEO.')


@contextmanager
def participant_locks(db, site_id, plan):
    with ExitStack() as stack:
        for key in sorted({site_id, plan.get('source_site_id', site_id)}):
            stack.enter_context(network.network_lock(db, key))
        yield


def transferable(source, state, domain):
    key = domain_key(domain)
    protected = [source.name, state['canon'], state.get('reserve'), *state.get('amp_domains', []),
                 *(source.main_domain_history or []), *(source.alternate_domain_history or []), *(source.x_default_history or [])]
    markup = state['alternateMarkup'].replace('{{settings.canon}}', state['canon'])
    protected += [link['domain'] for link in alternate_links(markup)]
    if domain not in state['domains'] or key in {domain_key(d) for d in protected}:
        raise ValueError('Домен занят текущими настройками или отмечен в истории использования.')
    if (source.domain_types or {}).get(domain) == 'amp':
        raise ValueError('AMP-домены не переносятся.')
    if classify_domains(state['domains'], source.domain_types or {})[domain]['is_subdomain']:
        raise ValueError('Для переноса выберите корневой домен.')
    if sum(domain_key(d) == key for d in state['domains']) > 1:
        raise ValueError('В исходной сетке есть несколько вариантов адреса этого домена.')
    if any(domain_key(d).endswith('.' + key) for d in state['domains'] if domain_key(d) != key):
        raise ValueError('У домена есть поддомены в исходной сетке.')


def unique_membership(db, domain, permitted):
    for site in db.scalars(select(models.Site).where(models.Site.is_active.is_(True))):
        if site.id not in permitted and any(domain_key(d) == domain_key(domain) for d in (site.cache_domains or [])):
            raise ValueError('Домен присутствует ещё в одной сетке: ' + site.name)


def preview(db, target, state):
    from app import auto_reglue as auto
    cfg = auto.config(db)
    auto.require_eligible(target, cfg, auto.config(db, target.id))
    if auto.active_run(db, target.id):
        raise ValueError('Принимающая сетка уже участвует в незавершённом запуске.')
    if cfg.scheme_mode not in {'preserve', 'clean'}:
        raise ValueError('Для перекрёстного режима выберите сохранение схемы или чистый альтернейт.')
    allowed = db.info.get('cross_allowed_site_ids')
    query = select(models.Site).where(models.Site.is_active.is_(True), models.Site.project_status == 'mass_actions', models.Site.id != target.id).order_by(models.Site.name)
    if allowed is not None:
        query = query.where(models.Site.id.in_(allowed))
    if db.scalar(select(models.NetworkOperation.id).where(models.NetworkOperation.site_id == target.id, models.NetworkOperation.status.in_(['pending', 'unknown'])).limit(1)):
        raise ValueError('Принимающая сетка имеет неподтверждённую операцию.')
    reasons = []
    for source in db.scalars(query):
        try:
            require_pair(source, target)
        except ValueError:
            continue
        if auto.config(db, source.id).scope == 'personal' or auto.active_run(db, source.id):
            continue
        if db.scalar(select(models.NetworkOperation.id).where(models.NetworkOperation.site_id == source.id, models.NetworkOperation.status.in_(['pending', 'unknown'])).limit(1)):
            continue
        source_state = network.read_network(db, source)
        for domain in source_state['domains']:
            try:
                transferable(source, source_state, domain)
                require_transfer_allowed(db, source, domain)
                unique_membership(db, domain, {source.id})
            except ValueError as error:
                reasons.append(str(error)); continue
            if not state.get('has_head'):
                raise ValueError('Не получены данные head принимающей сетки.')
            before = state['alternateMarkup']
            after = re.sub(r'(?<=://)' + re.escape(state['canon']) + r'(?=[/:\"\s]|$)', domain, before)
            if cfg.scheme_mode == 'clean':
                after = ''
            plan = {'execution_mode': 'cross_network', 'scope': 'mass', 'site_id': target.id,
                    'project': target.name, 'source_site_id': source.id, 'source_project': source.name,
                    'brand': target.brand, 'geo': geo_key(target.cache_geo), 'old_main': state['canon'], 'new_main': domain,
                    'source_revision': source_state['revision'], 'revision': state['revision'],
                    'alternateMarkup': after, 'alternates_before': {'markup': before, 'enabled': state['enableAlternates']},
                    'scheme_mode': cfg.scheme_mode, 'enableAlternates': False if cfg.scheme_mode == 'clean' else state['enableAlternates'], 'required_page_urls': ['https://' + domain + '/'],
                    'domain_type': (source.domain_types or {}).get(domain),
                    'config_hash': auto.digest(cfg.model_dump())}
            plan['preview_token'] = auto.digest(plan)
            return plan
    details = '; '.join(dict.fromkeys(reasons))[:1200]
    raise ValueError('Нет подходящего домена в других сетках этого бренда и GEO.' + (' ' + details if details else ''))


def receipt_id(run, action):
    return str(uuid5(UUID(run.id), 'cross:' + action))


def completed_job(db, site, operation):
    if operation.status == 'failed':
        raise ValueError(operation.message or 'Ошибка операции Webdev.')
    job_id = operation.request_payload.get('job_id')
    # Membership alone is insufficient: nginx/DNS provisioning may still be running.
    if not job_id:
        raise ValueError('Webdev не вернул идентификатор задачи. Нужна ручная проверка результата.')
    with network.Remote(db, site) as remote:
        job = remote.job_state(job_id)
    if not job:
        return False
    result = job.get('result') or {}
    if job.get('state') == 'failed' or result.get('errorCount', 0) or any(d.get('status') == 'error' for d in job.get('domains', [])):
        raise ValueError('Задача Webdev завершилась ошибкой: ' + str(job.get('error') or result)[:500])
    return job.get('state') == 'completed' and operation.status == 'confirmed'


def change(db, run, site, action, state, **values):
    receipt = receipt_id(run, action)
    existing = db.get(models.NetworkOperation, receipt)
    if existing is None:
        run.phase = 'cross_' + action; run.status = 'running'; db.commit()
        network.change_network(db, site, network.NetworkChange(request_id=receipt, action=action, revision=state['revision'], **values), run.initiator, auto_run_id=run.id)
        existing = db.get(models.NetworkOperation, receipt)
    db.refresh(existing)
    if existing.status == 'failed':
        raise ValueError(existing.message or 'Ошибка Webdev.')
    ready = completed_job(db, site, existing) if action in {'delete_domain', 'create_domains'} else existing.status == 'confirmed'
    if not ready:
        run.status = 'waiting'; run.message = 'Ждём подтверждения Webdev: ' + action + '. Повторная отправка не выполняется.'; db.commit()
    return ready


def execute(db, run):
    from app import auto_reglue as auto
    plan = run.plan
    target = db.get(models.Site, run.site_id)
    source = db.get(models.Site, plan['source_site_id'])
    domain = plan['new_main']
    try:
        # Same lock as ban edits; another run cannot transfer the domain concurrently.
        with network.network_lock(db, policy_key(domain)):
            require_pair(source, target)
            cfg = auto.config(db)
            if cfg.execution_mode != 'cross_network' or not cfg.enabled:
                raise ValueError('Перекрёстный режим выключен.')
            if run.plan.get('scheduled') and not cfg.schedule_enabled:
                raise ValueError('Расписание выключено.')
            if any(auto.config(db, s.id).scope == 'personal' for s in (source, target)):
                raise ValueError('Сетка переведена на персональные настройки.')
            if banned_domains(db, target, [domain])[domain]:
                raise ValueError('Домен отмечен БАН в GEO проекта.')
            source_state = network.read_network(db, source)
            target_state = network.read_network(db, target)
            deletion = db.get(models.NetworkOperation, receipt_id(run, 'delete_domain'))
            addition = db.get(models.NetworkOperation, receipt_id(run, 'create_domains'))
            if deletion is None:
                if auto.digest(cfg.model_dump()) != plan['config_hash']:
                    raise ValueError('Настройки изменились после предпросмотра.')
                if source_state['revision'] != plan['source_revision'] or target_state['revision'] != plan['revision']:
                    raise ValueError('Сетки изменились после предпросмотра. Подготовьте план снова.')
                if db.scalar(select(models.NetworkOperation.id).where(models.NetworkOperation.site_id.in_([source.id, target.id]), models.NetworkOperation.status.in_(['pending', 'unknown'])).limit(1)):
                    raise ValueError('У сетки есть неподтверждённая операция.')
                transferable(source, source_state, domain)
                require_transfer_allowed(db, source, domain)
                unique_membership(db, domain, {source.id})
                run.plan = {**run.plan, 'started_at': datetime.now(timezone.utc).isoformat()}; db.commit()
            if not change(db, run, source, 'delete_domain', source_state, domain=domain):
                return
            source_state = network.read_network(db, source)
            if any(domain_key(d) == domain_key(domain) for d in source_state['domains']):
                raise ValueError('Извлечение домена из исходной сетки не подтверждено.')
            if addition is None:
                require_transfer_allowed(db, target, domain)
                unique_membership(db, domain, set())
                if target_state['canon'] != plan['old_main']:
                    raise ValueError('Main принимающей сетки изменился.')
            if not change(db, run, target, 'create_domains', target_state, domains=[domain]):
                return
            target_state = network.read_network(db, target)
            if domain not in target_state['domains']:
                raise ValueError('Домен не появился в принимающей сетке.')
            if 'added_at' not in run.plan:
                added_at = target_state.get('domain_added_at', {}).get(domain) or datetime.now(timezone.utc).isoformat()
                target.network_state = {**target.network_state, 'domain_added_at': {**target.network_state.get('domain_added_at', {}), domain: added_at}}
                if plan.get('domain_type'):
                    target.domain_types = {**(target.domain_types or {}), domain: plan['domain_type']}
                run.plan = {**run.plan, 'added_at': added_at}; db.commit()
            try:
                auto.verify_pages(plan['required_page_urls'])
            except (httpx.HTTPError, ValueError):
                run.status = 'waiting'; run.message = 'Домен перенесён. Ждём HTTPS перед сменой Main.'; db.commit(); return
            for action in ('reserve', 'reglue', 'alternates'):
                target_state = network.read_network(db, target)
                receipt = db.get(models.NetworkOperation, receipt_id(run, action))
                if receipt is None:
                    expected = domain if action == 'alternates' else plan['old_main']
                    if target_state['canon'] != expected:
                        raise ValueError('Main изменился вне этого запуска.')
                    if target_state['alternateMarkup'] != plan['alternates_before']['markup'] or target_state['enableAlternates'] != plan['alternates_before']['enabled']:
                        raise ValueError('Альтернейты изменились вне запуска. Проверьте их вручную.')
                if not change(db, run, target, action, target_state, domain=domain, alternate_markup=plan['alternateMarkup'], enable_alternates=plan['enableAlternates']):
                    return
            target_state = network.read_network(db, target)
            if target_state['canon'] != domain or target_state['alternateMarkup'] != plan['alternateMarkup'] or target_state['enableAlternates'] != plan['enableAlternates']:
                raise ValueError('Итоговый Main или альтернейты не подтверждены.')
            from app.network_indexing import queue_indexing
            queue_indexing(db, target, target_state, run.id, run.initiator)
            now = datetime.now(timezone.utc)
            run.plan = {**run.plan, 'alternates_after': {'markup': target_state['alternateMarkup'], 'enabled': target_state['enableAlternates']},
                        'completed_at': now.isoformat(), 'elapsed_seconds': (now - datetime.fromisoformat(run.plan['started_at'])).total_seconds()}
            run.status = 'completed'; run.phase = 'completed'; run.message = 'Домен перенесён и стал Main. Альтернейты подтверждены; история сохранена.'; db.commit()
    except Exception as error:
        db.rollback(); db.refresh(run)
        run.status = 'partial' if db.get(models.NetworkOperation, receipt_id(run, 'delete_domain')) else 'failed'
        run.message = str(error)[:2000]; db.commit()
