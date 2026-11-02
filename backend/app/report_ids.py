"""Permanent human-readable IDs for saved AutoPilot reports, across all actors.

Assignments live outside worker-owned payload/result documents. Allocation uses an
independent transaction: reading a report never commits the caller's pending edits.
Call only after the report itself has been committed.
"""
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app import models

FIRST = 3000
KINDS = ('auto_pilot_preview', 'mass_reglue_list', 'maintenance_report')
PREFIX = 'pilot-report-id:'
COUNTER = 'pilot-report-sequence'
LOCK_ID = 7319043000


def ensure(db):
    """Backfill once in creation order, then append without renumbering old IDs."""
    with Session(bind=db.get_bind(), expire_on_commit=False) as allocation:
        with allocation.begin():
            dialect = allocation.get_bind().dialect.name
            if dialect == 'postgresql':
                # The transaction lock also serializes the first counter insert.
                allocation.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': LOCK_ID})
            elif dialect == 'sqlite':
                # Acquire the SQLite write lock before reading any counter/mapping.
                # ON CONFLICT preserves existing values and supports separate workers.
                from sqlalchemy.dialects.sqlite import insert
                allocation.execute(insert(models.AutoReglueConfig).values(
                    key=COUNTER, value={'next': FIRST}).on_conflict_do_nothing(index_elements=['key']))
            else:
                raise RuntimeError('Report ID allocation requires PostgreSQL or SQLite.')
            sequence = allocation.get(models.AutoReglueConfig, COUNTER, with_for_update=True)
            if sequence is None:
                sequence = models.AutoReglueConfig(key=COUNTER, value={'next': FIRST})
                allocation.add(sequence)
            assigned = {}
            for row in allocation.scalars(select(models.AutoReglueConfig).where(
                    models.AutoReglueConfig.key.startswith(PREFIX))):
                number = (row.value or {}).get('number')
                if type(number) is not int or number < FIRST:
                    raise ValueError('Некорректный сохранённый ID отчёта.')
                assigned[row.key[len(PREFIX):]] = number
            if len(set(assigned.values())) != len(assigned):
                raise ValueError('Обнаружены повторяющиеся ID отчётов.')
            saved_next = (sequence.value or {}).get('next', FIRST)
            if type(saved_next) is not int or saved_next < FIRST:
                raise ValueError('Некорректная последовательность ID отчётов.')
            next_number = max(saved_next, max(assigned.values(), default=FIRST - 1) + 1)
            reports = allocation.scalars(select(models.BackgroundJob.id).where(
                models.BackgroundJob.kind.in_(KINDS)).order_by(
                models.BackgroundJob.created_at, models.BackgroundJob.id))
            for job_id in reports:
                if job_id in assigned:
                    continue
                allocation.add(models.AutoReglueConfig(key=PREFIX + job_id, value={'number': next_number}))
                assigned[job_id] = next_number
                next_number += 1
            sequence.value = {'next': next_number}
        return assigned


def get(db, job):
    """Return a report's number; UUID identity and permission checks stay unchanged."""
    if isinstance(job, models.BackgroundJob):
        # Accessing an expired .id can autoflush unrelated dirty caller state.
        identity = inspect(job).identity
        if not identity:
            raise ValueError('Сначала сохраните отчёт для назначения ID.')
        job_id = str(identity[0])
    else:
        job_id = str(job)
    number = ensure(db).get(job_id)
    if number is None:
        raise ValueError('Сохранённый отчёт для назначения ID не найден.')
    return number
