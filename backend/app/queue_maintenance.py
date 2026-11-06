"""Inspect/compact broker waiting lists without touching active or unacked work."""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4
from redis import Redis
from sqlalchemy import select
from app import models
from app.core.config import get_settings

QUEUES = ('generation', 'pilot_texts', 'short_generation', 'planning', 'automation',
          'publication', 'cache_sync', 'maintenance', 'background_dispatch', 'celery')


def broker():
    return Redis.from_url(get_settings().celery_broker_url, socket_timeout=10)


def lists():
    return [q + (f'\x06\x16{priority}' if priority else '') for q in QUEUES for priority in (0, 3, 6, 9)]


def inflight_job_ids(client):
    pipe = client.pipeline(transaction=False)
    for key in lists(): pipe.lrange(key, 0, -1)
    pipe.hvals('unacked')
    results = pipe.execute()
    ids = set()
    for messages in results[:-1]:
        for raw in messages:
            try: message = json.loads(raw)
            except (ValueError, TypeError): continue
            if message.get('headers', {}).get('task') == 'app.worker.background_operation':
                ids.add(message['headers']['id'])
    for raw in results[-1]:
        try: message = json.loads(raw)[0]
        except (ValueError, TypeError, IndexError): continue
        if message.get('headers', {}).get('task') == 'app.worker.background_operation':
            ids.add(message['headers']['id'])
    return ids


def obsolete_retry(db, job):
    if job.kind != 'generation_retry': return False
    item = db.get(models.ContentItem, job.payload.get('content_id'))
    if not item: return True
    task = db.get(models.GenerationTask, item.task_id)
    current = (item.generation_context or {}).get('automatic_generation_retry', {}).get('job_id')
    return bool(not task or task.archived_at or item.status not in {'generation_queued', 'generating'}
                or current and current != job.id)


def cleanup(db, client, *, apply=False, send=None):
    from app.job_queues import queue_for
    jobs = {job.id: job for job in db.scalars(select(models.BackgroundJob))}
    obsolete = {id for id, job in jobs.items() if job.status == 'queued' and obsolete_retry(db, job)}
    reasons = Counter(); removed = []; seen = set(); reroute = {}
    # Redis lists are consumed right-to-left. Retain the oldest delivery.
    for key in lists():
        for raw in reversed(client.lrange(key, 0, -1)):
            try: message = json.loads(raw); headers = message.get('headers', {})
            except (ValueError, TypeError): continue
            task, id = headers.get('task'), headers.get('id')
            if not task or not id: continue
            identity = (task, id)
            job = jobs.get(id) if task == 'app.worker.background_operation' else None
            target = queue_for(db, job) if job and job.status == 'queued' else None
            reason = ('obsolete_retry' if id in obsolete and job else
                      'finished_job' if job and job.status not in {'queued', 'running', 'generating', 'applying'} else
                      'moved_queue' if target and key.split('\x06\x16')[0] != target else
                      'duplicate_delivery' if identity in seen else None)
            if reason == 'moved_queue': reroute[id] = target
            seen.add(identity)
            if reason:
                removed.append((key, raw)); reasons[reason] += 1
    archive = 'pagepilot:queue-cleanup:' + str(uuid4())
    if apply:
        # Back up exactly the removed messages before mutation; no credentials in logs/Git.
        for key, raw in removed:
            client.rpush(archive, json.dumps({'queue': key, 'message': raw.decode() if isinstance(raw, bytes) else raw}))
        if removed: client.expire(archive, 7 * 86400)
        # Deliver to the new queue before removing the old copy. A lost acknowledgement
        # may duplicate a delivery, but the durable job claim prevents duplicate work.
        if send is None:
            from app.worker import background_operation_job
            send = lambda id, queue: background_operation_job.apply_async(args=[id], queue=queue, task_id=id)
        for id, target in reroute.items(): send(id, target)
        for id in obsolete:
            job = jobs[id]
            job.result = {**(job.result or {}), 'queue_cleanup': {'at': datetime.now(timezone.utc).isoformat(),
                          'previous_error': job.error, 'reason': 'Задание заменено новой попыткой или текст уже обработан.'}}
            job.status = 'cancelled'; job.error = None; job.finished_at = datetime.now(timezone.utc)
        db.commit()
        for key, raw in removed:
            client.lrem(key, 1, raw)  # Concurrently claimed messages are left untouched.
    return {'apply': apply, 'removed_messages': len(removed), 'reasons': dict(reasons),
            'obsolete_retry_jobs': len(obsolete), 'rerouted_jobs': len(reroute),
            'backup_key': archive if apply and removed else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from app.db import SessionLocal
    with SessionLocal() as db: print(json.dumps(cleanup(db, broker(), apply=args.apply)))
