"""Read-only public Main/selected-inner audit for a saved, exact brand scope."""
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import urljoin, urlsplit, quote

import httpx
from sqlalchemy import select
from app import models, maintenance_reports
from app.db import SessionLocal
from app.fake_redirect_check import exact_url
from app.factual_research import require_public_url
from app.network_state import domain_name, project_network_state
from app.project_cache import project_server_url, refresh_project_server_token
from app.project_pages import pages, is_home
from app.provisioning_readiness import content_samples, normalized
from app.reference_context import readable

TASK = 'brand_health_audit'
BRANDS = ('Pelican', 'Fontan', 'BetOnRed', 'Lemon Casino')
PLACEHOLDERS = ('welcome to my website', 'welcome to nginx', 'apache2 ubuntu default page',
    'default web site page', 'default website page', 'this domain is parked', 'domain is for sale',
    'website coming soon', 'site under construction', 'website is under construction',
    'site not installed', 'domain not configured', 'домен не привязан', 'сайт не настроен')


def now():
    return datetime.now(timezone.utc).isoformat()


def classify(html, status, brand, expected_title='', samples=()):
    title_match = re.search(r'<title\b[^>]*>(.*?)</title\s*>', html, re.I | re.S)
    title = normalized(readable(title_match[1])) if title_match else ''
    text = normalized(readable(html))
    lower = text.casefold()
    words = len(text.split())
    evidence = {'title': title[:350], 'words': words, 'excerpt': text[:550],
                'sha256': hashlib.sha256(html.encode()).hexdigest()}
    def result(outcome, reason):
        return {**evidence, 'outcome': outcome, 'reason': reason}
    challenge = ('just a moment', 'checking your browser', 'verify you are human', 'access denied', 'captcha')
    if words < 250 and any(x in lower for x in challenge):
        return result('blocked', 'Защита/проверка посетителя; содержимое сайта не подтверждено.')
    if status != 200:
        return result('http_error', f'HTTP {status}; вместо рабочей страницы получен ошибочный ответ.')
    marker = next((x for x in PLACEHOLDERS if x in lower), None)
    if marker and words < 250:
        return result('placeholder', 'Заглушка: ' + marker)
    matched = [s for s in samples if normalized(s).casefold() in lower]
    if expected_title and title.casefold() == normalized(expected_title).casefold() and matched:
        return result('healthy', 'Title и фрагмент статьи совпадают с текущим проектом Webdev.')
    key = re.sub(r'[^a-z]', '', brand.casefold()).replace('casino', '')
    aliases = {'fontan': ('fontan', 'fountain'), 'betonred': ('betonred',),
               'pelican': ('pelican',), 'lemon': ('lemon',)}.get(key, (key,))
    title_key = re.sub(r'[^a-z]', '', title.casefold())
    if words >= 120 and any(alias and alias in title_key for alias in aliases):
        return result('healthy', 'Содержательная страница нужного бренда: бренд в Title и текст статьи.')
    return result('review', 'Контент не совпал с ожидаемой страницей; требуется проверка содержания.')


async def probe(url, brand, expected_title='', samples=(), *, transport=None, validate=require_public_url):
    if not url:
        return {'outcome': 'not_configured', 'reason': 'Адрес не задан.', 'checked_at': now(), 'chain': []}
    evidence = {'url': url, 'checked_at': now(), 'chain': []}
    seen = set()
    current = url
    try:
        async with httpx.AsyncClient(timeout=18, follow_redirects=False, trust_env=False, transport=transport,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; PagePilotSiteAudit/1.0)', 'Cache-Control': 'no-cache'}) as client:
            for _ in range(9):
                if current in seen:
                    return {**evidence, 'outcome': 'redirect_loop', 'reason': 'Цикл редиректов.', 'final_url': current}
                seen.add(current)
                await asyncio.wait_for(validate(current), timeout=10)
                async with client.stream('GET', current) as response:
                    code = response.status_code
                    hop = {'url': current, 'status': code}
                    evidence['chain'].append(hop)
                    if code in (301, 302, 303, 307, 308):
                        location = response.headers.get('location')
                        if not location:
                            return {**evidence, 'outcome': 'http_error', 'reason': 'Редирект без Location.'}
                        current = urljoin(current, location)
                        hop['location'] = current
                        continue
                    chunks, size = [], 0
                    async for part in response.aiter_bytes():
                        size += len(part)
                        if size > 2_000_000:
                            return {**evidence, 'outcome': 'review', 'reason': 'HTML превышает лимит проверки 2 МБ.'}
                        chunks.append(part)
                    html = b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace')
                    result = classify(html, code, brand, expected_title, samples)
                    if result['outcome'] == 'healthy' and len(evidence['chain']) > 1:
                        result.update(outcome='redirect', reason='Сайт открывается после редиректа; выбранный URL не отдаёт 200 напрямую.')
                    return {**evidence, **result, 'final_url': current, 'http_status': code}
            return {**evidence, 'outcome': 'redirect_loop', 'reason': 'Более 8 редиректов.', 'final_url': current}
    except (httpx.HTTPError, OSError, ValueError, TimeoutError) as error:
        return {**evidence, 'outcome': 'unreachable', 'reason': f'{type(error).__name__}: {str(error)[:220]}', 'final_url': current}


async def checked_probe(*args):
    first = await probe(*args)
    if first['outcome'] in {'healthy', 'not_configured'}:
        return {**first, 'attempts': 1}
    second = await probe(*args)
    return {**second, 'attempts': 2, 'previous_attempt': first}


def inspect_site(site_id, token):
    with SessionLocal() as db:
        site = db.get(models.Site, site_id)
        if not site or site.hidden_from_projects or site.brand not in BRANDS:
            return {'site_id': site_id, 'status': 'failed', 'error': 'Проект больше не входит в согласованную группу.'}
        state = dict(site.network_state or {})
        expected_title, samples, config_error = '', [], None
        source = 'cache'
        try:
            with httpx.Client(timeout=25, headers={'Authorization': 'Bearer ' + token}) as remote:
                response = remote.get(project_server_url(site, '/projects/one/') + quote(site.name, safe=''))
                response.raise_for_status()
                project = response.json()
                if not isinstance(project.get('settings'), dict):
                    raise ValueError('Webdev не вернул настройки проекта')
                state = project_network_state(project)
                home = next((p for p in pages(project) if is_home(p)), {})
                expected_title, samples = home.get('title') or '', content_samples(project, home)
                source = 'webdev'
        except Exception as error:
            config_error = type(error).__name__ + ': не удалось сверить конфигурацию с Webdev.'
        main = domain_name(state.get('canon') or site.cache_canon)
        main_url = 'https://' + main + '/' if main else None
        inner = exact_url(main, state.get('fake_main_current')) if state.get('fake_main_enabled') else None
        async def both():
            return await asyncio.gather(checked_probe(main_url, site.brand, expected_title, samples),
                                        checked_probe(inner, site.brand, expected_title, samples))
        main_check, inner_check = asyncio.run(both())
        return {'site_id': site.id, 'status': 'completed', 'main': main, 'main_url': main_url,
                'inner_url': inner, 'domains_count': len(state.get('domains') or site.cache_domains or []),
                'health': {'main': main_check, 'inner': inner_check, 'configuration_source': source,
                           'configuration_error': config_error, 'expected_title': expected_title,
                           'checked_at': now()}, 'finished_at': now()}


def run(report_id):
    """Resume this saved report only; no publication, redirects or Fibery writes."""
    with SessionLocal() as db:
        job = db.get(models.BackgroundJob, report_id)
        if not job or job.kind != maintenance_reports.KIND or job.payload.get('task_type') != TASK:
            raise ValueError('Нужен заранее созданный отчёт проверки брендов.')
        name, actor, ids = job.payload['name'], job.payload['actor'], job.payload['site_ids']
        todo = [r['site_id'] for r in job.result['entries'] if r.get('status') != 'completed']
    async def login():
        async with httpx.AsyncClient(timeout=25) as client:
            return await refresh_project_server_token(client)
    token = asyncio.run(login())
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(inspect_site, sid, token): sid for sid in todo}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                entry = future.result()
            except Exception as error:
                entry = {'site_id': sid, 'status': 'failed', 'error': type(error).__name__ + ': ошибка проверки.'}
            with SessionLocal() as db:
                maintenance_reports.upsert(db, report_id, name, actor, ids, [entry])
            print(sid, entry['status'], flush=True)
    with SessionLocal() as db:
        job = db.get(models.BackgroundJob, report_id)
        status = 'completed' if all(r['status'] == 'completed' for r in job.result['entries']) else 'partial'
        maintenance_reports.upsert(db, report_id, name, actor, ids, status=status)


if __name__ == '__main__':
    import sys
    run(sys.argv[1])
