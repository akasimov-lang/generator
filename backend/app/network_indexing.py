"""Durable post-reglue indexing receipts; ambiguous sends are never retried."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5

import httpx
from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.indexing import _indexing_task_id
from app.network_state import domain_name, validate_markup


def verified(state, expected):
    if (state.get('canon') != expected['canon'] or not state.get('has_head')
            or not state.get('head_verified', state.get('has_head'))
            or state.get('alternateMarkup') != expected['alternateMarkup']
            or state.get('enableAlternates') != expected['enableAlternates']):
        return False
    try:
        if expected['enableAlternates']:
            validate_markup(state['alternateMarkup'])
    except ValueError:
        return False
    return True


def queue_indexing(db, site, state, source_id, initiator):
    receipt = str(uuid5(UUID(source_id), 'network-indexing'))
    existing = db.get(models.NetworkOperation, receipt)
    if existing:
        return existing
    amp = {domain_name(d) for d in state.get('amp_domains', [])}
    amp.update(domain_name(d) for d, kind in (site.domain_types or {}).items() if kind == 'amp')
    domains = list(dict.fromkeys(domain_name(d) for d in state.get('domains', [])))
    urls = ['https://' + d + '/' for d in domains if d and d not in amp]
    op = models.NetworkOperation(id=receipt, site_id=site.id, action='indexing',
        status='index_queued' if urls else 'failed', initiator=initiator,
        request_payload={'domains': urls, 'engines': ['google'], 'source_id': source_id},
        message=f'Задача индексации основной сетки поставлена в очередь: {len(urls)} доменов. AMP исключены.' if urls else 'В основной сетке нет доменов для индексации.')
    db.add(op)
    db.flush()
    return op


def confirm_manual_indexing(db, site, state):
    operations = db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.site_id == site.id, models.NetworkOperation.action == 'reglue',
        models.NetworkOperation.status == 'confirmed',
        models.NetworkOperation.request_payload['indexing_pending'].as_boolean() == True)).all()
    for op in operations:
        expected = op.request_payload.get('_indexing')
        if expected and verified(state, expected):
            queue_indexing(db, site, state, op.id, op.initiator)
            op.request_payload = {**op.request_payload, 'indexing_pending': False}


def submit_network_indexing(db, operation_id, *, client=None):
    from app.project_network import network_lock
    with network_lock(db, 'indexing:' + operation_id):
        op = db.get(models.NetworkOperation, operation_id)
        if not op or op.action != 'indexing' or op.status != 'index_queued':
            return
        payload = {key: op.request_payload[key] for key in ('domains', 'engines')}
        op.status = 'index_submitting'
        op.message = 'Отправляем задачу индексации. Повторная отправка заблокирована.'
        db.commit()  # Claim before HTTP, including process crashes after the send.
        active_client = client or httpx.Client(timeout=30.0)
        try:
            response = active_client.post(get_settings().indexing_endpoint, json=payload)
            op.response_status = response.status_code
            try:
                body = response.json()
            except ValueError:
                body = None
            task_id = _indexing_task_id(body) if 200 <= response.status_code < 300 else None
            if task_id:
                op.status = 'index_submitted'
                op.request_payload = {**op.request_payload, 'task_id': task_id}
                op.message = f'Задача индексации {task_id} создана. Домены: {len(payload["domains"])}. AMP исключены. Это подтверждение приёма задачи, а не завершения индексации.'
            else:
                op.status = 'index_unknown'
                op.message = f'Сервис не подтвердил номер задачи (HTTP {response.status_code}). Автоматическая повторная отправка отключена: проверьте результат в сервисе индексации.'
        except Exception as error:
            op.status = 'index_unknown'
            op.message = f'Ответ сервиса индексации не подтверждён ({type(error).__name__}). Запрос мог выполниться; повторная отправка отключена.'
        finally:
            if client is None:
                active_client.close()
        db.commit()


def process_network_indexing(db, limit=20):
    from app.project_network import read_network, NetworkConflict
    # Recover confirmation when the browser closed or Webdev answered late.
    pending = db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.action == 'reglue',
        models.NetworkOperation.status.in_(['pending', 'unknown', 'confirmed']),
        models.NetworkOperation.request_payload['indexing_pending'].as_boolean() == True)
        .order_by(models.NetworkOperation.created_at).limit(limit)).all()
    for site_id in dict.fromkeys(op.site_id for op in pending):
        site = db.get(models.Site, site_id)
        if site:
            try:
                read_network(db, site)
            except Exception:
                db.rollback()  # A later tick will reread, never repeat the reglue.
    stale = db.scalars(select(models.NetworkOperation).where(
        models.NetworkOperation.action == 'indexing', models.NetworkOperation.status == 'index_submitting',
        models.NetworkOperation.updated_at < datetime.now(timezone.utc) - timedelta(minutes=5))).all()
    for op in stale:
        op.status = 'index_unknown'
        op.message = 'Отправка прервалась; результат неизвестен. Проверьте задачу в сервисе индексации. Автоматического повтора не будет.'
    db.commit()
    ids = db.scalars(select(models.NetworkOperation.id).where(
        models.NetworkOperation.action == 'indexing', models.NetworkOperation.status == 'index_queued')
        .order_by(models.NetworkOperation.created_at).limit(limit)).all()
    for operation_id in ids:
        try:
            submit_network_indexing(db, operation_id)
        except NetworkConflict:
            db.rollback()
    return {'processed': len(ids)}
