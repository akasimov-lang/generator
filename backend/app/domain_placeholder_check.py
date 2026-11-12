"""Delayed, durable Webdev requests for placeholders after domain provisioning."""
import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from app import models
from app.core.config import get_settings
from app.fake_redirect_check import due
from app.fibery_client import FiberyError, FiberyConflict
from app.fibery_tasks import project_number
from app.fibery_webdev import WebdevClient, CLOSED
from app.network_state import domain_name
from app.reglue_history import utc

KIND = 'domain_placeholder_check'
START_KEY = 'domain-placeholder:enabled-at'
ACTIONS = ('create_domains', 'create_subdomains')


def identity(value):
    return str(uuid5(NAMESPACE_URL, 'pagepilot:domain-placeholder:' + value))


def added_domains(operation):
    return sorted({name for item in (operation.request_payload or {}).get('domains', [])
                   if (name := domain_name(item.get('domain') if isinstance(item, dict) else item))})


def ensure_jobs(db, operation):
    payload = operation.request_payload or {}
    # An accepted provisioning request can still be absent from the remote network:
    # that is precisely the failure this check must detect.
    if operation.action not in ACTIONS or not payload.get('job_id'):
        return []
    at = utc(payload.get('domain_added_at')) or utc(operation.created_at)
    jobs = []
    for domain in added_domains(operation):
        id_ = identity(operation.id + ':' + domain)
        job = db.get(models.BackgroundJob, id_)
        if not job:
            job = models.BackgroundJob(id=id_, kind=KIND, status='queued', payload={
                'site_id': operation.site_id, 'operation_id': operation.id,
                'domain': domain, 'url': 'https://' + domain + '/',
                'title': f'{domain} не добавился в сетку',
                'added_at': at.isoformat(), 'due_at': (at + timedelta(minutes=2)).isoformat()})
            db.add(job)
        jobs.append(job)
    db.flush()
    return jobs


def tick(db, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    if not db.get(models.AutoReglueConfig, START_KEY):
        try:
            with db.begin_nested():
                db.add(models.AutoReglueConfig(key=START_KEY, value={'enabled_at': now.isoformat()}))
                db.flush()
        except IntegrityError:
            pass
        db.commit()
    config = db.get(models.AutoReglueConfig, START_KEY, with_for_update=True)
    start = utc(config.value['enabled_at'])
    operations = db.scalars(select(models.NetworkOperation).outerjoin(models.BackgroundJob, and_(
        models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload['operation_id'].as_string() == models.NetworkOperation.id)).where(
        models.BackgroundJob.id.is_(None), models.NetworkOperation.action.in_(ACTIONS),
        models.NetworkOperation.created_at >= start,
        models.NetworkOperation.request_payload['job_id'].as_string().is_not(None))
        .order_by(models.NetworkOperation.created_at).limit(100)).all()
    created = sum(len(ensure_jobs(db, op)) for op in operations)
    recovered = 0
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
            models.BackgroundJob.status == 'running', models.BackgroundJob.started_at < now - timedelta(minutes=15))):
        job.status, job.dispatched_at = 'queued', None
        recovered += 1
    db.commit()
    return {'created': created, 'recovered': recovered}


def obsolete(db, site, job):
    if not site or site.hidden_from_projects:
        return True
    # Do not cancel merely because a newly requested domain is missing from the
    # network. Cancel only after a later confirmed removal of this exact domain.
    for op in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id == site.id,
            models.NetworkOperation.action == 'delete_domain',
            models.NetworkOperation.status == 'confirmed',
            models.NetworkOperation.created_at >= utc(job.payload['added_at']))):
        if job.payload['domain'] in added_domains(op):
            return True
    return False


def inspect_domain(url):
    from app.brand_health_audit import checked_probe
    return asyncio.run(checked_probe(url, ''))


def confirmed_placeholder(evidence, url):
    previous = evidence.get('previous_attempt') or {}
    host = domain_name(url).removeprefix('www.')
    return all(row.get('url') == url and row.get('outcome') == 'placeholder'
               and row.get('http_status') == 200
               and domain_name(row.get('final_url')).removeprefix('www.') == host
               for row in (previous, evidence))


def request_text(site, domain):
    return (f'{domain} не добавился в сетку',
        f'https://{domain}/ — домен не добавился в сетку, спустя 2 минуты после добавления отдаёт заглушку.\n\n'
        f'https://ai-seo-content-panel.site/project-network/{quote(site.name, safe="")}/\n\n'
        'Проверить и добавить домен.')


def execute(db, job_id, *, client=None, probe=None, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    job = db.get(models.BackgroundJob, job_id, with_for_update=True)
    if not job or job.kind != KIND or job.status != 'queued' or not due(job, now):
        db.rollback()
        return {'status': 'waiting_or_claimed'}
    job.status, job.started_at = 'running', now
    job.result = {**(job.result or {}), 'attempts': int((job.result or {}).get('attempts', 0)) + 1}
    db.commit()
    owned = client is None
    try:
        site = db.get(models.Site, job.payload['site_id'])
        outcome = 'superseded'
        if not obsolete(db, site, job):
            evidence = (probe or inspect_domain)(job.payload['url'])
            job.result = {**job.result, 'evidence': evidence}
            db.commit()
            uncertain = {'unreachable', 'blocked', 'http_error', 'redirect_loop'}
            if evidence.get('outcome') in uncertain:
                raise FiberyError('Публичный ответ не подтверждён; заглушка не установлена. Проверка будет повторена.')
            outcome = 'no_placeholder'
            if confirmed_placeholder(evidence, job.payload['url']):
                number = project_number(site.fibery_name)
                if not number:
                    raise FiberyError('У проекта не указан номер Fibery; создание задачи ожидает привязки.')
                if client is None:
                    client = WebdevClient(get_settings().fibery_api_token.get_secret_value())
                from app.project_network import network_lock
                key = 'domain-placeholder-issue:' + identity(number + ':' + job.payload['domain'])
                with network_lock(db, key):
                    db.refresh(site)
                    if obsolete(db, site, job):
                        outcome = 'superseded'
                    elif project_number(site.fibery_name) != number:
                        raise FiberyError('Привязка проекта Fibery изменилась; проверка будет повторена.')
                    else:
                        issue = db.get(models.AutoReglueConfig, key)
                        value = dict(issue.value) if issue else {}
                        existing = client.task(value['task_id']) if value.get('task_id') else None
                        if existing and (existing.get('workflow/state') or {}).get('enum/name') in CLOSED:
                            value = {}
                        # A persisted identity may be a half-completed create. Finish
                        # and verify it before considering other, manually created tasks.
                        task = None if value else client.existing_domain_task(project_number=number, domain=job.payload['domain'])
                        if not task:
                            if not value:
                                title, description = request_text(site, job.payload['domain'])
                                value = {'task_id': identity('task:' + job.id), 'title': title,
                                         'description': description, 'project_number': number}
                            if not issue:
                                issue = models.AutoReglueConfig(key=key, value=value)
                                db.add(issue)
                            else:
                                issue.value = value
                            db.commit()
                            task = client.ensure_webdev_task(task_id=value['task_id'], project_number=number,
                                title=value['title'], description=value['description'], page_url=job.payload['url'], priority='Medium')
                            issue.value = {**value, 'task': task}
                        job.result = {**job.result, 'task': task, 'verified_at': now.isoformat()}
                        outcome = 'task_reused' if task.get('existing') else 'task_created'
            elif evidence.get('outcome') == 'placeholder':
                raise FiberyError('Заглушка не подтверждена двумя ответами этого домена; проверка будет повторена.')
        job.status, job.error, job.finished_at = 'completed', None, datetime.now(timezone.utc)
        job.result = {**job.result, 'outcome': outcome, 'next_attempt_at': None}
        db.commit()
        return {'status': 'completed', 'outcome': outcome, 'task': job.result.get('task')}
    except Exception as error:
        db.rollback()
        job = db.get(models.BackgroundJob, job_id)
        attempts = int((job.result or {}).get('attempts', 1))
        terminal = isinstance(error, FiberyConflict) or attempts >= 6
        job.status, job.dispatched_at = ('failed' if terminal else 'queued'), None
        job.error = str(error) if isinstance(error, FiberyError) else 'Проверка домена или сохранение Webdev-задачи не подтверждены; запланирован повтор.'
        job.result = {**(job.result or {}), 'next_attempt_at': (now + timedelta(seconds=min(1800, 60 * 2**min(attempts-1, 5)))).isoformat()}
        if terminal:
            job.finished_at = now
        db.commit()
        return {'status': job.status, 'message': job.error}
    finally:
        if owned and client is not None:
            client.close()


def notice(job):
    from app.fake_redirect_check import notice as redirect_notice
    return {**redirect_notice(job), 'code': 'FIBERY_WEBDEV_PLACEHOLDER'}
