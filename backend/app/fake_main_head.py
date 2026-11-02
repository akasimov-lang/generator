"""Finish a fake-path change with one durable, never-replayed head update."""
from uuid import UUID, uuid5

import httpx
from sqlalchemy import select

from app import models


def receipt_id(parent):
    return str(uuid5(UUID(parent.id), 'fake-main-head'))


def continue_pending(db, site, remote, state, project):
    from app import project_network as network

    parents = db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id,
        models.NetworkOperation.action.in_(['create_fake_main', 'select_fake_main']),
        models.NetworkOperation.status.in_(['pending', 'unknown']))).all()
    for parent in parents:
        payload = parent.request_payload
        desired = payload.get('head_sync')
        if not desired or not all(state.get('fake_main_settings', {}).get(k) == v for k, v in payload['alternate'].items()):
            continue
        child = db.get(models.NetworkOperation, receipt_id(parent))
        if network.operation_matches(parent, state):
            parent.status = 'confirmed'
            parent.message = 'Фейковый внутряк, canonical и альтернейты подтверждены.'
            db.commit()
            continue
        if child is None:
            before = payload['head_before']
            # Another editor may have changed the markup since the path was saved.
            head = project.get('head')
            if not isinstance(head, dict) or any(k not in head for k in desired):
                parent.status = 'unknown'
                parent.message = 'Внутряк изменён. Не удалось прочитать разметку; обновите данные для завершения canonical и альтернейтов.'
                db.commit()
                continue
            if any(head[k] not in (before[k], v) for k, v in desired.items()):
                parent.status = 'failed'
                parent.message = 'Внутряк изменён, но разметка Webdev изменилась отдельно. Автоматическая замена отменена; проверьте canonical и альтернейты.'
                db.commit()
                continue
            child = models.NetworkOperation(id=receipt_id(parent), site_id=site.id,
                action='alternates', initiator=parent.initiator, status='pending',
                request_payload={'folder': payload['folder'],
                    'alternateMarkup': desired.get('alternateMarkup', state['alternateMarkup']),
                    'enableAlternates': state['enableAlternates'], **desired,
                    'fake_main_parent_id': parent.id,
                    'expected_fake_main': payload['alternate']['currentFakeMain'],
                    'head_sync': desired,
                    'alternates_before': {'markup': state['alternateMarkup'], 'enabled': state['enableAlternates']},
                    'canonical_before': {k: state[k] for k in ('enableCanonical', 'canonicalDefaultMarkup', 'canonicalFakeMainMarkup')}},
                message='Обновляем старый путь в canonical и альтернейтах.')
            db.add(child)
            db.commit()  # Record the only write attempt before I/O.
            try:
                code, body = remote.request('PATCH', '/projects/update-head', {'folder': payload['folder'], **desired})
                child.response_status = code
                if isinstance(body, dict) and (body.get('errors') or body.get('error') or body.get('success') is False):
                    child.status = 'failed'
                    child.message = 'Webdev отклонил обновление разметки: ' + str(body.get('message') or body.get('errors') or body.get('error'))[:1000]
            except httpx.HTTPStatusError as error:
                child.response_status = error.response.status_code
                child.status = 'failed' if 400 <= error.response.status_code < 500 else 'unknown'
                child.message = f'Обновление разметки: HTTP {error.response.status_code}. Повторная отправка заблокирована.'
            except (httpx.HTTPError, ValueError):
                child.status = 'unknown'
                child.message = 'Ответ при обновлении разметки не получен. Проверяем результат без повторной отправки.'
            db.commit()
            try:
                project = remote.project()
                state = network.observe(db, site, project)
            except (httpx.HTTPError, ValueError, network.ProjectCacheError):
                if child.status == 'pending':
                    child.status = 'unknown'
        db.refresh(parent)
        db.refresh(child)
        if network.operation_matches(parent, state):
            child.status = parent.status = 'confirmed'
            child.message = parent.message = 'Фейковый внутряк, canonical и альтернейты подтверждены.'
        elif child.status == 'failed':
            parent.status = 'failed'
            parent.message = 'Внутряк изменён, обновление canonical и альтернейтов не завершено. ' + (child.message or '')
        else:
            parent.status = 'unknown'
            parent.message = 'Внутряк изменён. Ждём подтверждения canonical и альтернейтов; повторная отправка не выполняется.'
        db.commit()
    return state, project
