"""Continue an authorized Main change with a separate, never-replayed redirect receipt."""
from uuid import UUID, uuid5
import httpx
from sqlalchemy import select
from app import models
from app.domain_redirects import for_reglue


def receipt_id(parent):
    return str(uuid5(UUID(parent.id), 'reglue-domain-redirects'))


def continue_pending(db, site, remote, state, project):
    from app import project_network as network
    parents = db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.action == 'reglue',
        models.NetworkOperation.status.in_(['pending', 'unknown']),
        models.NetworkOperation.request_payload['redirect_sync'].as_boolean() == True)).all()
    for parent in parents:
        payload = parent.request_payload
        if state['canon'] != payload['reserve']:
            continue
        verified = {**state, 'redirects_verified': isinstance(project.get('settings', {}).get('redirects'), list)}
        try:
            desired = for_reglue(verified, payload)
        except ValueError as error:
            parent.status = 'unknown'; parent.message = 'Main изменён. ' + str(error)
            db.commit(); continue
        if desired == state.get('domain_redirects'):
            child = db.get(models.NetworkOperation, receipt_id(parent))
            if child and child.status in {'pending', 'unknown'}:
                child.status = 'confirmed'; child.message = 'Конечные цели редиректов подтверждены.'
            parent.status = 'confirmed'; parent.message = 'Main и конечные цели доменных редиректов подтверждены.'
            parent.request_payload = {**parent.request_payload, 'redirects_after':state['domain_redirects']}
            db.commit(); continue
        child = db.get(models.NetworkOperation, receipt_id(parent))
        if child is None:
            child = models.NetworkOperation(id=receipt_id(parent), site_id=site.id,
                action='reglue_redirects', initiator=parent.initiator, status='pending',
                request_payload={'folder':site.name.encode('idna').decode(), 'redirects':desired,
                    'redirects_before':state['domain_redirects'], 'parent_id':parent.id,
                    'expected_canon':payload['reserve'], 'old_main':payload['source_domain']}, message='Обновляем конечные цели редиректов после смены Main.')
            db.add(child); db.commit()  # Durable intent before the only write attempt.
            try:
                code, body = remote.request('POST', '/projects/update-value',
                    {'folder':child.request_payload['folder'], 'redirects':desired})
                child.response_status = code
                if isinstance(body, dict) and (body.get('errors') or body.get('error') or body.get('success') is False):
                    child.status = 'failed'
                    child.message = 'Webdev отклонил обновление редиректов: ' + str(body.get('message') or body.get('errors') or body.get('error'))[:1000]
            except httpx.HTTPStatusError as error:
                child.response_status = error.response.status_code
                child.status = 'failed' if 400 <= error.response.status_code < 500 else 'unknown'
                child.message = f'Обновление редиректов: HTTP {error.response.status_code}. Повторная отправка заблокирована.'
            except (httpx.HTTPError, ValueError):
                child.status = 'unknown'
                child.message = 'Ответ при обновлении редиректов не получен. Проверяем результат без повторной отправки.'
            db.commit()
            try:
                project = remote.project()
                state = network.observe(db, site, project)
            except (httpx.HTTPError, ValueError, network.ProjectCacheError):
                child.status = 'unknown' if child.status == 'pending' else child.status
                child.message = child.message or 'Не удалось перечитать редиректы.'
        db.refresh(parent); db.refresh(child)
        actual = {**state, 'redirects_verified': isinstance(project.get('settings', {}).get('redirects'), list)}
        if network.operation_matches(child, actual):
            child.status = 'confirmed'; child.message = 'Конечные цели редиректов подтверждены.'
            parent.status = 'confirmed'; parent.message = 'Main и конечные цели доменных редиректов подтверждены.'
            parent.request_payload = {**parent.request_payload, 'redirects_after':state['domain_redirects']}
        elif child.status == 'failed':
            parent.status = 'failed'; parent.message = 'Main изменён, обновление целей редиректов не завершено. ' + (child.message or '')
        elif parent.status != 'confirmed':
            parent.status = 'unknown'; parent.message = 'Main изменён. Ждём подтверждения новых целей редиректов; повторная отправка не выполняется.'
        db.commit()
    return state, project
