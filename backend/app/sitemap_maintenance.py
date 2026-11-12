"""Resumable, scoped sitemap repairs, with backups and public read-back evidence."""
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import httpx
from app import models, network_sitemap as sitemap, maintenance_reports
from app.db import SessionLocal
from app.project_network import Remote, network_lock
from app.factual_research import require_public_url

TASK = 'sitemap_repair'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def public_snapshot(main, expected):
    url = 'https://' + main + '/sitemap.xml'
    result = {'url': url, 'checked_at': stamp(), 'valid': False}
    try:
        asyncio.run(require_public_url(url))
        with httpx.Client(timeout=20, follow_redirects=False, headers={'Cache-Control': 'no-cache'}) as client:
            with client.stream('GET', url) as response:
                result.update(status=response.status_code, location=response.headers.get('location'))
                parts, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 4_000_000:
                        raise ValueError('Sitemap превышает 4 МБ.')
                    parts.append(chunk)
        urls = sitemap.locations(b''.join(parts).decode('utf-8-sig'))
        result.update(count=len(urls), missing=len(set(expected)-set(urls)), extra=len(set(urls)-set(expected)),
            duplicates=len(urls)-len(set(urls)), valid=result['status'] == 200 and len(urls) == len(expected) and set(urls) == set(expected))
        if not result['valid']:
            result['error'] = 'Sitemap не совпадает с опубликованными страницами текущего Main.'
    except (httpx.HTTPError, OSError, ValueError) as error:
        result['error'] = str(error)[:600]
    return result


def outcome(op, public, webdev_verified):
    written = webdev_verified and op.request_payload.get('before') != op.request_payload.get('after')
    if op.status == 'sitemap_done' and public.get('valid'):
        return 'completed', 'updated' if written else 'verified', None
    reason = public.get('error') or op.message or 'Публичный sitemap не подтверждён.'
    if not webdev_verified:
        return 'failed', 'write_error', op.message or 'Webdev не подтвердил сохранение sitemap.'
    if public.get('status') == 404:
        reason = 'Webdev хранит sitemap, но текущий Main возвращает HTTP 404. Требуется исправить публикацию или маршрутизацию домена на хостинге.'
    elif public.get('status') in (301, 302, 303, 307, 308):
        reason = f"Sitemap текущего Main перенаправляется на {public.get('location') or 'другой URL'}. Нужен прямой ответ на выбранном Main."
    return 'partial' if written else 'failed', 'saved_unconfirmed' if written else 'hosting_error', reason


def repair(report_id, row):
    sid = row['site_id']
    evidence = dict(row.get('sitemap') or {})
    with SessionLocal() as db:
        site = db.get(models.Site, sid)
        if not site or site.hidden_from_projects or site.project_status != 'mass_actions':
            return {**row, 'status': 'skipped', 'error': 'Проект больше не имеет статуса «Массовые действия».', 'finished_at': stamp()}
        try:
            with network_lock(db, sid), Remote(db, site) as remote:
                project = remote.project()
                main, urls = sitemap.expected(project)
                public = public_snapshot(main, urls)
                if 'before' not in evidence:
                    evidence['before'] = {'main': main, 'expected_count': len(urls), 'template': project.get('sitemap'),
                        'template_present': 'sitemap' in project, 'public': public, 'checked_at': stamp()}
                evidence.update(expected_count=len(urls), internal_pages=len(urls)-1, sitemap_url='https://'+main+'/sitemap.xml')
                op = sitemap.queue(db, site, report_id, 'anton', manual=False)
                db.commit()
                if public['valid'] and op.status == 'sitemap_queued':
                    # A fresh public verification supersedes historical errors without rewriting a healthy file.
                    op.request_payload = {'main': main, 'urls': urls, 'before': project.get('sitemap'),
                        'after': project.get('sitemap'), 'before_present': 'sitemap' in project, 'audit_report': report_id}
                    op.status = 'sitemap_done'
                    op.message = f'Sitemap проверен: {len(urls)} страниц, только {main}. Изменения не требуются.'
                    db.commit()
                operation_id = op.id
            if op.status in sitemap.ACTIVE:
                sitemap.process(db, operation_id)
            db.expire_all()
            op = db.get(models.NetworkOperation, operation_id)
            # Do not attribute a result to the old Main when an intervening reglue changed it.
            with Remote(db, site) as remote:
                current_project = remote.project()
                current_main, current_urls = sitemap.expected(current_project)
                webdev_verified = current_project.get('sitemap') == op.request_payload.get('after') and isinstance(current_project.get('sitemap'), str)
            if current_main != main or current_urls != urls:
                raise ValueError('Main или страницы изменились во время проверки; нужен повтор с актуальным состоянием.')
            if not public['valid'] or op.status != 'sitemap_done':
                public = public_snapshot(main, urls)
            # A successful second read can finish a pending verification; it never retries the write.
            if public.get('valid') and op.status == 'sitemap_verify':
                sitemap.process(db, operation_id)
                db.refresh(op)
            status, action, error = outcome(op, public, webdev_verified)
            evidence.update(after=public, operation_id=operation_id, operation_status=op.status, action=action,
                webdev_verified=webdev_verified,
                updated_urls=len(urls) if action in ('updated','saved_unconfirmed') else 0)
            result = {**row, 'main': main, 'status': status, 'error': error, 'sitemap': evidence, 'finished_at': stamp()}
            return result
        except Exception as error:
            db.rollback()
            return {**row, 'sitemap': evidence, 'status': 'failed', 'error': str(error)[:700], 'finished_at': stamp()}


def run(report_id):
    with SessionLocal() as guard, network_lock(guard, 'sitemap-report:'+report_id):
        job = guard.get(models.BackgroundJob, report_id)
        if not job or job.kind != maintenance_reports.KIND or job.payload.get('maintenance_kind') != TASK:
            raise ValueError('Нужен заранее созданный отчёт sitemap.')
        job.payload = {**job.payload, 'task_type': TASK}
        job.status, job.finished_at = 'running', None
        guard.commit()
        name, ids, actor = job.payload['name'], job.payload['site_ids'], job.payload['actor']
        todo = [row for row in job.result['entries'] if row.get('status') != 'completed']
        with ThreadPoolExecutor(max_workers=4) as pool:
            for future in as_completed([pool.submit(repair, report_id, row) for row in todo]):
                row = future.result()
                with SessionLocal() as db:
                    maintenance_reports.upsert(db, report_id, name, actor, ids, [row])
                print(row['project'], row['status'], row.get('sitemap',{}).get('action'), flush=True)
        with SessionLocal() as db:
            job = db.get(models.BackgroundJob, report_id)
            status = 'completed' if all(r['status'] in ('completed','skipped') for r in job.result['entries']) else 'partial'
            maintenance_reports.upsert(db, report_id, name, actor, ids, status=status)


def record_tasks(report_id):
    """Create one read-back verified SEO receipt per changed, publicly confirmed project."""
    from uuid import UUID, uuid5
    from app.core.config import get_settings
    from app.fibery_client import FiberyClient
    from app.fibery_tasks import project_number, refresh_legacy_receipts
    with SessionLocal() as db, network_lock(db, 'sitemap-fibery:'+report_id):
        job = db.get(models.BackgroundJob, report_id)
        if not job or job.kind != maintenance_reports.KIND or job.payload.get('maintenance_kind') != TASK:
            raise ValueError('Нужен отчёт sitemap.')
        client = FiberyClient(get_settings().fibery_api_token.get_secret_value())
        try:
            for row in list(job.result['entries']):
                evidence = row.get('sitemap') or {}
                if row['status'] != 'completed' or evidence.get('action') != 'updated' or row.get('fibery_task'):
                    continue
                site = db.get(models.Site, row['site_id'])
                key = 'sitemap-fibery:'+report_id+':'+site.id
                ledger = db.get(models.AutoReglueConfig, key)
                if not ledger:
                    number = project_number(site.fibery_name)
                    if not number:
                        row['fibery_error'] = 'У проекта нет привязки Fibery.'
                        maintenance_reports.upsert(db,report_id,job.payload['name'],job.payload['actor'],job.payload['site_ids'],[row],status=job.status)
                        continue
                    ledger = models.AutoReglueConfig(key=key,value={
                        'task_id':str(uuid5(UUID(report_id),'sitemap:'+site.id)), 'project_number':number,
                        'title':row['main']+' — обновление sitemap',
                        'description':f"- Обновлён sitemap: https://{row['main']}/sitemap.xml\n- Включены главная и {evidence['internal_pages']} внутренних страниц; всего {evidence['expected_count']} URL на текущем Main.\n- Проверены сохранение в Webdev и публичный XML (HTTP 200), полный список адресов без дублей.",
                        'site_id':site.id, 'report_id':report_id})
                    db.add(ledger);db.commit()
                try:
                    receipt=client.ensure_task(**{k:ledger.value[k] for k in ('task_id','project_number','title','description')})
                    receipt['verified_at']=stamp()
                    ledger.value={**ledger.value,'fibery_task':receipt}
                    row['fibery_task']=receipt;row.pop('fibery_error',None)
                    maintenance_reports.upsert(db,report_id,job.payload['name'],job.payload['actor'],job.payload['site_ids'],[row],status=job.status)
                    print('FIBERY',site.name,receipt['url'],flush=True)
                except Exception as error:
                    db.rollback();row['fibery_error']=str(error)[:500]
                    maintenance_reports.upsert(db,report_id,job.payload['name'],job.payload['actor'],job.payload['site_ids'],[row],status=job.status)
                    print('FIBERY ERROR',site.name,row['fibery_error'],flush=True)
            refresh_legacy_receipts(db,force=True)
        finally:
            client.close()


if __name__ == '__main__':
    import sys
    (record_tasks if '--fibery' in sys.argv else run)(sys.argv[1])
