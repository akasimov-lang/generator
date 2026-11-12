"""Check exact selected fake URLs and request Webdev repairs for confirmed 301s."""
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from app import models
from app.core.config import get_settings
from app.fibery_client import FiberyError, FiberyConflict
from app.fibery_webdev import WebdevClient, CLOSED
from app.fibery_tasks import project_number
from app.network_state import domain_name
from app.reglue_history import utc
from app.reglue_journal import confirmed_at

KIND = 'fake_redirect_check'
START_KEY = 'fake-redirect-check:enabled-at'
ACTIONS = ('create_fake_main', 'select_fake_main', 'alternates', 'reglue')


def identity(value):
    return str(uuid5(NAMESPACE_URL, 'pagepilot:fake-redirect:' + value))


def exact_url(main, path):
    main = domain_name(main)
    if not main or not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or path == '/':
        return None
    if any(c in path for c in ('?', '#', '\\', '\n', '\r', ' ')):
        return None
    return 'https://' + main + path


def selected_url(site):
    state = site.network_state or {}
    if not state.get('fake_main_enabled'):
        return None
    return exact_url(state.get('canon') or site.cache_canon, state.get('fake_main_current'))


def ensure_job(db, operation):
    if operation.status != 'confirmed' or operation.action not in ACTIONS:
        return None
    id_ = identity(operation.id)
    existing = db.get(models.BackgroundJob, id_)
    if existing:
        return existing
    p = operation.request_payload or {}
    before = p.get('fibery_before') or p.get('journal_before') or {}
    after = p.get('fibery_after') or p.get('journal_after') or {}
    alternate = p.get('alternate') or {}
    main = after.get('main') or (p.get('reserve') if operation.action == 'reglue' else before.get('main'))
    # A Main change preserves the fake path unless the confirmed snapshot says otherwise.
    preserved = before if operation.action == 'reglue' else {}
    path = after.get('fake_path', alternate.get('currentFakeMain', preserved.get('fake_path')))
    enabled = after.get('fake_enabled', alternate.get('enableDynamicRoutes', preserved.get('fake_enabled', True)))
    site = db.get(models.Site, operation.site_id)
    if not main and site:
        main = site.cache_canon
    url = exact_url(main, path) if enabled else None
    unchanged = bool(operation.action != 'reglue' and url and url == exact_url(before.get('main'), before.get('fake_path')))
    at = confirmed_at(operation)
    job = models.BackgroundJob(id=id_, kind=KIND,
        status='completed' if not url or unchanged else 'queued',
        finished_at=datetime.now(timezone.utc) if not url or unchanged else None,
        payload={'site_id': operation.site_id, 'operation_id': operation.id, 'url': url,
                 'due_at': (at + timedelta(seconds=15)).isoformat(),
                 'title': f'{main} — проверить редирект {path}'},
        result={'outcome': 'unchanged_or_disabled'} if not url or unchanged else {})
    try:
        with db.begin_nested():
            db.add(job); db.flush()
    except IntegrityError:
        return db.get(models.BackgroundJob, id_)
    return job


def due(job, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    return (now >= utc(job.payload['due_at']) and
            (not (job.result or {}).get('next_attempt_at') or now >= utc(job.result['next_attempt_at'])))


def tick(db, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    config = db.get(models.AutoReglueConfig, START_KEY)
    if not config:
        try:
            with db.begin_nested():
                db.add(models.AutoReglueConfig(key=START_KEY, value={'enabled_at': now.isoformat()})); db.flush()
        except IntegrityError:
            pass
        db.commit()
    config = db.get(models.AutoReglueConfig, START_KEY, with_for_update=True)
    start = utc(config.value['enabled_at'])
    operations = db.scalars(select(models.NetworkOperation).outerjoin(models.BackgroundJob, and_(
        models.BackgroundJob.kind == KIND,
        models.BackgroundJob.payload['operation_id'].as_string() == models.NetworkOperation.id)).where(
        models.BackgroundJob.id.is_(None), models.NetworkOperation.action.in_(ACTIONS),
        models.NetworkOperation.status == 'confirmed', models.NetworkOperation.updated_at >= start)
        .order_by(models.NetworkOperation.updated_at).limit(100)).all()
    created = 0
    for op in operations:
        job = ensure_job(db, op)
        if confirmed_at(op) >= start:
            created += int(job is not None)
        elif job:
            # Later reconciliation may touch old confirmed operations. Consume them
            # without a request so they cannot starve the next batch of new changes.
            job.status, job.finished_at = 'completed', now
            job.result = {'outcome': 'before_activation'}
    recovered = 0
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND,
            models.BackgroundJob.status == 'running', models.BackgroundJob.started_at < now - timedelta(minutes=15))):
        job.status, job.dispatched_at = 'queued', None
        recovered += 1
    db.commit()
    return {'created': created, 'recovered': recovered}


def inspect_url(url):
    """GET only; preserve the exact path and never follow an off-site redirect."""
    chain, current, seen = [], url, set()
    with httpx.Client(timeout=20, follow_redirects=False, headers={'User-Agent': 'PagePilot-URL-Check/1.0'}) as client:
        for _ in range(5):
            if current in seen:
                break
            seen.add(current)
            with client.stream('GET', current) as response:
                location = urljoin(current, response.headers['location']) if response.headers.get('location') else None
                chain.append({'url': current, 'status': response.status_code, 'location': location})
            if not location or response.status_code not in {301, 302, 303, 307, 308}:
                break
            if urlsplit(location).netloc != urlsplit(url).netloc or urlsplit(location).scheme not in {'https', 'http'}:
                break
            current = location
    return {'url': url, 'chain': chain, 'checked_at': datetime.now(timezone.utc).isoformat()}


def request_text(evidence):
    url, first = evidence['url'], evidence['chain'][0]
    target = first.get('location')
    if not target:
        raise FiberyError('Ответ 301 без Location: направление редиректа не подтверждено.')
    parsed, redirected = urlsplit(url), urlsplit(target)
    lines = [f'- Проект: {parsed.scheme}://{parsed.netloc}/', f'- Выбранная внутренняя страница: {url}',
             f'- Сейчас: {url} → HTTP 301 → {target}.',
             f'- Исправить: {url} должен возвращать HTTP 200 напрямую. Удалить редирект с этого адреса на {target}.']
    chain = evidence['chain']
    if len(chain) > 1 and chain[-1].get('location') in {hop['url'] for hop in chain}:
        steps = [chain[0]['url']]
        for hop in chain:
            steps.extend([f"HTTP {hop['status']}", hop.get('location') or hop['url']])
        lines.insert(3, '- Обнаружена петля редиректов: ' + ' → '.join(steps) + '.')
    if (parsed.scheme == redirected.scheme and parsed.netloc == redirected.netloc
            and parsed.path.rstrip('/') == redirected.path.rstrip('/') and parsed.path != redirected.path
            and parsed.query == redirected.query and not redirected.fragment):
        lines.append(f'- Настроить HTTP 301 в обратном направлении: {target} → {url}.')
    lines.append('- Проверить отсутствие цепочки и петли редиректов; выбранный URL в canonical и hreflang должен открываться без перенаправления.')
    return f'{parsed.netloc} — исправить редирект {parsed.path}', '\n'.join(lines)


def execute(db, job_id, *, client=None, probe=None, now=None):
    now = utc(now) or datetime.now(timezone.utc)
    job = db.get(models.BackgroundJob, job_id, with_for_update=True)
    if not job or job.kind != KIND or job.status != 'queued' or not due(job, now):
        db.rollback(); return {'status': 'waiting_or_claimed'}
    job.status, job.started_at = 'running', now
    job.result = {**(job.result or {}), 'attempts': int((job.result or {}).get('attempts', 0)) + 1}
    db.commit()
    owned = client is None
    try:
        site = db.get(models.Site, job.payload['site_id'])
        if not site or selected_url(site) != job.payload['url']:
            outcome = 'superseded'
        else:
            evidence = (probe or inspect_url)(job.payload['url'])
            assert evidence['url'] == job.payload['url'] and evidence['chain'][0]['url'] == evidence['url']
            job.result = {**job.result, 'evidence': evidence}; db.commit()
            first = evidence['chain'][0]
            if first['status'] >= 400:
                raise FiberyError(f"Проверка URL: HTTP {first['status']}; редирект 301 не подтверждён.")
            outcome = 'no_301'
            if first['status'] == 301:
                title, description = request_text(evidence)
                number = project_number(site.fibery_name)
                if not number:
                    raise FiberyError('У проекта не указан номер Fibery; привязка Webdev-задачи ожидает уточнения.')
                if client is None:
                    client = WebdevClient(get_settings().fibery_api_token.get_secret_value())
                from app.project_network import network_lock
                # A separate advisory key serializes only issue writers, not Webdev network edits.
                with network_lock(db, 'fake-redirect-task:' + site.id):
                    db.refresh(site)
                    if selected_url(site) != job.payload['url']:
                        outcome = 'superseded'
                    else:
                        key = 'fake-redirect-issue:' + identity(site.id + ':' + evidence['url'])
                        issue = db.get(models.AutoReglueConfig, key)
                        value = dict(issue.value) if issue else {}
                        existing = client.task(value['task_id']) if value.get('task_id') else None
                        if existing and (existing.get('workflow/state') or {}).get('enum/name') in CLOSED:
                            value = {}
                        if not value:
                            value = {'task_id': identity('task:' + job.id), 'title': title, 'description': description,
                                     'url': evidence['url'], 'project_number': number, 'site_id': site.id}
                        if not issue:
                            issue = models.AutoReglueConfig(key=key, value=value); db.add(issue)
                        else:
                            issue.value = value
                        job.payload = {**job.payload, 'title': value['title']}
                        db.commit()  # Fixed task identity survives uncertain remote responses.
                        task = client.ensure_webdev_task(task_id=value['task_id'], project_number=number,
                            title=value['title'], description=value['description'], page_url=evidence['url'])
                        job.result = {**job.result, 'task': task, 'verified_at': now.isoformat()}
                        issue.value = {**value, 'task': task, 'verified_at': now.isoformat()}
                        outcome = 'task_created'
        job.status, job.error, job.finished_at = 'completed', None, datetime.now(timezone.utc)
        job.result = {**job.result, 'outcome': outcome, 'next_attempt_at': None}
        db.commit()
        return {'status': 'completed', 'outcome': outcome, 'task': (job.result or {}).get('task')}
    except Exception as error:
        db.rollback(); job = db.get(models.BackgroundJob, job_id)
        attempts = int((job.result or {}).get('attempts', 1))
        terminal = isinstance(error, FiberyConflict) or attempts >= 6
        job.status, job.dispatched_at = ('failed' if terminal else 'queued'), None
        job.error = str(error) if isinstance(error, FiberyError) else 'Не удалось проверить URL или подтвердить Webdev-задачу; повтор использует сохранённый идентификатор.'
        job.result = {**(job.result or {}), 'next_attempt_at': (now + timedelta(seconds=min(1800, 60 * 2**min(attempts-1, 5)))).isoformat()}
        if terminal: job.finished_at = now
        db.commit(); return {'status': job.status, 'message': job.error}
    finally:
        if owned and client is not None: client.close()


def notice(job):
    result = job.result or {}; task = result.get('task') or {}
    return {'id': 'webdev:' + job.id, 'source': 'fibery', 'code': 'FIBERY_WEBDEV_REDIRECT',
        'status': job.status, 'message': task.get('title') or job.payload.get('title') or 'Проверка редиректа внутряка',
        'context': job.error or (job.payload.get('url') or ''), 'severity': 'warning' if job.error else 'info',
        'active': bool(task or job.error), 'created_at': job.finished_at or job.created_at, 'occurrences': 1,
        'task_url': task.get('url'), 'task_title': task.get('title')}
