"""Durable Monday–Sunday digests. The scheduler reads evidence, never changes sites."""
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.reglue_history import utc
from app.security import AuthUser
from app.weekly_digest_text import aggregate, render

MSK = ZoneInfo('Europe/Moscow')
PREFIX = 'weekly-digest:'
CONTROL = 'weekly-digest-schedule'
REFRESH_INTERVAL = timedelta(minutes=15)
router = APIRouter(prefix='/weekly-digests', tags=['weekly-digests'])


def week_start(now=None):
    local = (utc(now) or datetime.now(timezone.utc)).astimezone(MSK)
    return local.date() - timedelta(days=local.weekday())


def bounds(monday):
    if isinstance(monday, str):
        monday = date.fromisoformat(monday)
    if monday.weekday() != 0:
        raise ValueError('Неделя должна начинаться в понедельник.')
    start = datetime.combine(monday, time.min, MSK).astimezone(timezone.utc)
    return start, start + timedelta(days=7)


def title(monday):
    sunday = monday + timedelta(days=6)
    return f'Новости PagePilot · {monday:%d.%m}–{sunday:%d.%m.%Y}'


def ensure_week(db, monday, now):
    key = PREFIX + monday.isoformat()
    record = db.get(models.AutoReglueConfig, key)
    if record is not None:
        return record
    start, end = bounds(monday)
    record = models.AutoReglueConfig(key=key, value={
        'id': monday.isoformat(), 'week_start': monday.isoformat(),
        'week_end': (monday + timedelta(days=7)).isoformat(),
        'title': title(monday), 'status': 'open', 'format_version': 1,
        'period_start': start.isoformat(), 'period_end': start.isoformat(),
        'created_at': now.isoformat(), 'updated_at': None,
        'rows': [], 'operations': [], 'runs': [], 'review': [],
    })
    db.add(record)
    db.flush()
    return record


def preserve_chat(db, monday, content, *,at, site_ids):
    """Save the requested original once. Refreshes never rewrite this version."""
    record = ensure_week(db, monday, utc(at))
    value = deepcopy(record.value)
    if not value.get('saved_text'):
        value.update(saved_text=content, saved_text_at=utc(at).isoformat(),
                     saved_text_site_ids=sorted(set(site_ids)))
        record.value = value
        db.flush()
    return record


def install_chat_snapshot(db):
    path = Path(__file__).parent / 'data' / 'weekly_reports' / '2026-11-02-chat.txt'
    if not path.exists():
        return
    key = PREFIX + '2026-11-02'
    existing = db.get(models.AutoReglueConfig, key)
    if existing is not None and existing.value.get('saved_text'):
        return
    # This is the exact text requested in chat, not a regenerated claim.
    preserve_chat(db, date(2026,11,2), path.read_text(encoding='utf-8'),
                  at=datetime(2026,11,7,4,tzinfo=timezone.utc), site_ids=[])


def refresh(db, record, now, collector=None):
    from app.weekly_digest_sources import collect
    value = deepcopy(record.value)
    start, week_end = bounds(value['week_start'])
    end = min(now, week_end)
    evidence = (collector or collect)(db, start, end) if end > start else {
        'rows': [], 'operations': [], 'runs': [], 'review': []}
    stats = aggregate(evidence['rows'], evidence['operations'], evidence['runs'],
                      manual_review_count=len(evidence['review']))
    value.update(evidence)
    value.update(status='closed' if now >= week_end else 'open',
                 period_end=end.isoformat(), updated_at=now.isoformat(),
                 stats=stats, text=render(stats,start,end,observed_at=now))
    value.pop('refresh_error', None)
    record.value = value
    db.flush()
    return value


def tick(db, now=None, *, force=False, collector=None):
    """One atomic refresh; PostgreSQL lock suppresses concurrent beat deliveries."""
    now = utc(now) or datetime.now(timezone.utc)
    if db.bind.dialect.name == 'postgresql':
        locked = db.scalar(text('SELECT pg_try_advisory_xact_lock(741905119)'))
        if not locked:
            db.rollback()
            return {'status': 'busy'}
    monday = week_start(now)
    control = db.get(models.AutoReglueConfig, CONTROL)
    if control is None:
        control = models.AutoReglueConfig(key=CONTROL, value={
            'first_week': monday.isoformat(), 'timezone': 'Europe/Moscow',
            'week_starts': 'Monday 00:00', 'refresh_minutes': 15,
        })
        db.add(control)
        db.flush()
    install_chat_snapshot(db)
    # Catch up after downtime, creating one durable report for every missed week.
    first = date.fromisoformat(control.value['first_week'])
    cursor = first
    while cursor <= monday:
        ensure_week(db, cursor, now)
        cursor += timedelta(days=7)
    records = list(db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.like(PREFIX+'%'),
        models.AutoReglueConfig.value['status'].as_string() == 'open'
    ).order_by(models.AutoReglueConfig.key)))
    refreshed = []
    for record in records:
        value = record.value
        if value.get('status') == 'closed':
            continue
        _, end = bounds(value['week_start'])
        updated = utc(value.get('updated_at'))
        if not force and now < end and updated and now-updated < REFRESH_INTERVAL:
            continue
        refresh(db, record, now, collector)
        refreshed.append(value['week_start'])
    db.commit()
    return {'status': 'updated', 'weeks': refreshed, 'current_week': monday.isoformat()}


def public_view(record, user, *, detail=True):
    value = record.value
    allowed = user.get('allowed_site_ids')
    restricted = allowed is not None
    if restricted:
        allowed = set(allowed)
        rows = [r for r in value.get('rows',[]) if r.get('site_id') in allowed]
        operations = [o for o in value.get('operations',[]) if o.get('site_id') in allowed]
        runs = [r for r in value.get('runs',[]) if r.get('site_id') in allowed]
        review = [r for r in value.get('review',[]) if r.get('site_id') in allowed]
        stats = aggregate(rows,operations,runs,manual_review_count=len(review))
    else:
        stats = value.get('stats') or aggregate([],[],[])
    result = {k:value.get(k) for k in ('id','week_start','week_end','title','status',
              'period_start','period_end','updated_at')}
    result.update(projects=stats['overall']['projects'],
                  manual_review_count=stats['manual_review_count'])
    if detail:
        result['text'] = render(stats,value['period_start'],value['period_end'],
                                observed_at=value.get('updated_at')) if restricted else value.get('text','')
        if not restricted and value.get('saved_text'):
            result.update(saved_text=value['saved_text'],saved_text_at=value.get('saved_text_at'))
    return result


@router.get('')
def listing(user: AuthUser, db: Session=Depends(get_db)):
    records = db.scalars(select(models.AutoReglueConfig).where(
        models.AutoReglueConfig.key.like(PREFIX+'%')).order_by(models.AutoReglueConfig.key.desc()))
    return {'reports':[public_view(record,user,detail=False) for record in records],
            'current_week':week_start().isoformat()}


@router.get('/{monday}')
def detail(monday: str, user: AuthUser, db: Session=Depends(get_db)):
    try:
        parsed = date.fromisoformat(monday)
        if parsed.isoformat()!=monday:
            raise ValueError()
        bounds(parsed)
    except ValueError:
        raise HTTPException(422,'Укажите дату понедельника в формате ГГГГ-ММ-ДД.')
    record = db.get(models.AutoReglueConfig,PREFIX+monday)
    if record is None:
        raise HTTPException(404,'Отчёт за эту неделю ещё не подготовлен.')
    return public_view(record,user)
