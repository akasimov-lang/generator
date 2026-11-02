"""Reconcile a saved plan against fresh Webdev data without replaying its writes."""
from datetime import datetime, timezone
from uuid import UUID, uuid5
import httpx
from sqlalchemy import select
from app import models, project_network as network


def fresh_project(db, site):
    from app.project_cache import fetch_project_cache
    rows = fetch_project_cache([site.name])
    item = next((row for row in rows if row.get('name') == site.name), None)
    server = (item or {}).get('serverId') or (item or {}).get('serverIp')
    if server and server != site.cache_server_ip:
        site.cache_server_ip = str(server); db.commit()
    with network.Remote(db, site) as remote:
        return remote.project()


def checks(db, run, site, project, state):
    from app import project_pages as pages, cross_reglue as cross
    from app.domain_redirects import for_reglue
    plan = run.plan
    result = []
    def check(code, label, ok):
        result.append({'code': code, 'label': label, 'ok': bool(ok)})
    check('DOMAIN', 'Домен в сетке', plan['new_main'] in state['domains'])
    check('MAIN', 'Main', state['canon'] == plan['new_main'])
    check('ALTERNATES', 'Альтернейты', state.get('has_head') and state['alternateMarkup'] == plan['alternateMarkup'] and state['enableAlternates'] == plan.get('enableAlternates', True))
    path = plan.get('fake_main_path')
    if path:
        check('FAKE_MAIN', 'Фейковый внутряк', state.get('fake_main_enabled') and state.get('fake_main_current') == path and path in state.get('fake_main_paths', []))
    if plan.get('canonicalFakeMainMarkup') is not None:
        check('CANONICAL', 'Canonical', state.get('enableCanonical') and state.get('canonicalFakeMainMarkup') == plan['canonicalFakeMainMarkup'])
    op = db.get(models.NetworkOperation, cross.receipt_id(run, 'reglue'))
    if op and op.request_payload.get('redirect_sync'):
        try: ok = state.get('domain_redirects') == for_reglue({**state, 'redirects_verified': isinstance(project['settings'].get('redirects'), list)}, op.request_payload)
        except ValueError: ok = False
        check('REDIRECTS', 'Доменные редиректы', ok)
    elif plan.get('redirect_old_main'):
        check('REDIRECTS', 'Доменные редиректы', False)
    if plan.get('rewrite_title_h1'):
        edit = db.get(models.ProjectPageEdit, str(uuid5(UUID(run.id), 'title-h1-save')))
        ok = date_ok = False
        if edit:
            current = pages.find_page(project, edit.page_key)
            paragraph_edit = db.get(models.ProjectPageEdit, str(uuid5(UUID(run.id), 'paragraphs-save'))) if plan.get('rewrite_paragraphs') else None
            if paragraph_edit:
                from app.reglue_paragraphs import title_matches
                ok = title_matches(edit.after_page, current, plan.get('title_rewrite_mode','minimal'))
            else:
                ok = pages.editable(current) == pages.editable(edit.after_page)
            final = paragraph_edit or edit
            date_ok = bool(final.after_page.get('updatedTime')) and current.get('updatedTime') == final.after_page['updatedTime']
            if ok and date_ok:
                edit.status = 'confirmed'; edit.error = None
                site.homepage_title = current.get('title') or ''
        check('TITLE_H1', 'Title/H1', ok)
        check('CONTENT_DATE', 'Дата обновления контента', date_ok)
    if plan.get('rewrite_paragraphs'):
        edit = db.get(models.ProjectPageEdit, str(uuid5(UUID(run.id), 'paragraphs-save')))
        ok = date_ok = False
        if edit:
            current = pages.find_page(project, edit.page_key)
            ok = pages.editable(current) == pages.editable(edit.after_page)
            date_ok = bool(edit.after_page.get('updatedTime')) and current.get('updatedTime') == edit.after_page['updatedTime']
            if ok and date_ok:
                edit.status, edit.error = 'confirmed', None
        check('PARAGRAPHS', 'Абзацы', ok)
        if not plan.get('rewrite_title_h1'):
            check('CONTENT_DATE', 'Дата обновления контента', date_ok)
    if plan.get('source_site_id', run.site_id) != run.site_id and not plan.get('reserve_pool_id'):
        source = db.get(models.Site, plan['source_site_id'])
        source_project = fresh_project(db, source)
        check('SOURCE_REMOVED', 'Извлечение из исходной сетки', plan['new_main'] not in source_project['settings'].get('domains', []))
    return result


def check_run(db, run_id, *, retry_title_h1=False, request_id=None):
    from app.reglue_dns import note
    from app.mass_action_reports import refresh_run
    with network.network_lock(db, 'auto-run:' + run_id):
        run = db.get(models.AutoReglueRun, run_id)
        if not run or run.status == 'cancelled': return
        site = db.get(models.Site, run.site_id)
        result = {'checked_at': datetime.now(timezone.utc).isoformat(), 'status': 'failed', 'checks': []}
        try:
            with network.network_lock(db, site.id):
                project = fresh_project(db, site)
                state = network.observe(db, site, project)
                actual = {**state, 'redirects_verified': isinstance(project['settings'].get('redirects'), list)}
                for op in db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id == site.id, models.NetworkOperation.status == 'failed')):
                    if op.request_payload.get('auto_run_id') != run.id or op.action not in {'reglue', 'alternates', 'create_fake_main', 'select_fake_main'}: continue
                    if network.operation_matches(op, actual):
                        old = op.message
                        op.status = 'unknown'
                        network.observe(db, site, project)
                        note(db, run, run.plan['new_main'], f'Настройки подтверждены Webdev. Ответ при сохранении: HTTP {op.response_status}. {old}')
                result.update(server=site.cache_server_ip, checks=checks(db, run, site, project, state))
                heading_codes = {'TITLE_H1', 'CONTENT_DATE'}
                if (retry_title_h1 and request_id and request_id not in run.plan.get('title_h1_refresh_requests', []) and run.plan.get('rewrite_title_h1')
                        and any(not c['ok'] for c in result['checks'] if c['code'] in heading_codes)
                        and all(c['ok'] for c in result['checks'] if c['code'] not in heading_codes)):
                    from app.reglue_title_h1 import retry_saved
                    run.plan = {**run.plan, 'title_h1_refresh_requests': [*run.plan.get('title_h1_refresh_requests', []), request_id]}
                    db.commit()
                    retry_saved(db, run)
                    project = fresh_project(db, site)
                    state = network.observe(db, site, project)
                    result['checks'] = checks(db, run, site, project, state)
                    result['title_h1_retried'] = True
                success = all(item['ok'] for item in result['checks'])
                result['status'] = 'confirmed' if success else 'mismatch'
                result['message'] = 'Все настройки переклея подтверждены свежими данными Webdev.' if success else 'Не подтверждено: ' + ', '.join(item['label'] for item in result['checks'] if not item['ok'])
                if success and run.status in {'partial', 'failed', 'waiting', 'completed'}:
                    from app.network_indexing import queue_indexing
                    queue_indexing(db, site, state, run.id, run.initiator)
                    run.plan = {**run.plan, 'completed_at': run.plan.get('completed_at') or result['checked_at'],
                        'applied_result': {**run.plan.get('applied_result', {}), 'new_main': state['canon'], 'fake_main_path': state.get('fake_main_current'), 'confirmed_at': result['checked_at']}}
                    run.status = 'completed'; run.phase = 'completed'; run.message = result['message']
        except Exception as error:
            db.rollback(); db.refresh(run)
            code = 'HTTP_' + str(error.response.status_code) if isinstance(error, httpx.HTTPStatusError) else type(error).__name__
            result.update(code=code, message=str(error)[:1500])
        run.plan = {**run.plan, 'verification': result}
        refresh_run(db, run); db.commit()
        return result


def schedule_after_finish(db, run, send):
    from app.reglue_monitor import start
    if not start(db, run):
        return False
    send(run.id, 60)
    run.plan = {**run.plan, 'post_check_queued_at': datetime.now(timezone.utc).isoformat()}
    db.commit()
    return True
