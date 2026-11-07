from datetime import date, datetime, timedelta, timezone
from copy import deepcopy

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import models, weekly_digests as digests
from test_project_network import env
from test_weekly_digest_text import row

NOW = datetime(2026,11,7,7,tzinfo=timezone.utc)


def empty(db,start,end):
    return {'rows':[], 'operations':[], 'runs':[], 'review':[]}


@pytest.fixture
def schedule(env, monkeypatch):
    monkeypatch.setattr(digests,'install_chat_snapshot',lambda db:None)
    return env[0]


def test_monday_changes_at_moscow_midnight_and_year_boundary():
    assert digests.week_start('2026-11-08T20:59:59Z') == date(2026,11,2)
    assert digests.week_start('2026-11-08T21:00:00Z') == date(2026,11,9)
    assert digests.week_start('2027-01-01T09:00:00Z') == date(2026,12,28)
    start,end = digests.bounds('2026-11-09')
    assert start.isoformat() == '2026-11-08T21:00:00+00:00'
    assert end-start == timedelta(days=7)


def test_tick_is_idempotent_and_refreshes_only_when_due(schedule):
    calls=[]
    def collect(db,start,end):
        calls.append((start,end)); return empty(db,start,end)
    digests.tick(schedule,NOW,collector=collect)
    digests.tick(schedule,NOW+timedelta(minutes=1),collector=collect)
    assert len(calls)==1
    digests.tick(schedule,NOW+timedelta(minutes=15),collector=collect)
    assert len(calls)==2
    records=list(schedule.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.like(digests.PREFIX+'%'))))
    assert len(records)==1 and records[0].value['status']=='open'


def test_monday_closes_previous_week_and_creates_next_report(schedule):
    calls=[]
    def collect(db,start,end):
        calls.append((start,end)); return empty(db,start,end)
    digests.tick(schedule,NOW,collector=collect)
    monday=datetime(2026,11,8,21,tzinfo=timezone.utc)
    digests.tick(schedule,monday,collector=collect)
    previous=schedule.get(models.AutoReglueConfig,digests.PREFIX+'2026-11-02')
    current=schedule.get(models.AutoReglueConfig,digests.PREFIX+'2026-11-09')
    assert previous.value['status']=='closed' and current.value['status']=='open'
    assert calls[-1][1] == monday
    assert current.value['period_start']==monday.isoformat()
    frozen=deepcopy(previous.value)
    digests.tick(schedule,monday+timedelta(hours=1),force=True,collector=collect)
    assert schedule.get(models.AutoReglueConfig,previous.key).value==frozen


def test_exact_midnight_never_calls_collector_with_empty_interval(schedule):
    def collect(db,start,end):
        assert end>start
        return empty(db,start,end)
    monday=datetime(2026,11,8,21,tzinfo=timezone.utc)
    digests.tick(schedule,monday,collector=collect)
    current=schedule.get(models.AutoReglueConfig,digests.PREFIX+'2026-11-09')
    assert current.value['stats']['overall']['projects']==0
    assert current.value['status']=='open'


def test_missed_weeks_are_created_once_after_server_downtime(schedule):
    digests.tick(schedule,NOW,collector=empty)
    later=datetime(2026,11,23,9,tzinfo=timezone.utc)
    digests.tick(schedule,later,collector=empty)
    digests.tick(schedule,later,collector=empty)
    records=list(schedule.scalars(select(models.AutoReglueConfig).where(models.AutoReglueConfig.key.like(digests.PREFIX+'%')).order_by(models.AutoReglueConfig.key)))
    assert [r.value['week_start'] for r in records]==['2026-11-02','2026-11-09','2026-11-16','2026-11-23']
    assert [r.value['status'] for r in records]==['closed','closed','closed','open']


def test_original_chat_text_survives_refresh_and_archive(schedule):
    text='**Новости PagePilot**\n\n- 128 смен Main.\n'
    digests.preserve_chat(schedule,date(2026,11,2),text,at=NOW,site_ids=['site'])
    schedule.commit()
    digests.tick(schedule,NOW,collector=empty)
    digests.preserve_chat(schedule,date(2026,11,2),'new unwanted text',at=NOW,site_ids=[])
    digests.tick(schedule,datetime(2026,11,8,21,tzinfo=timezone.utc),collector=empty)
    value=schedule.get(models.AutoReglueConfig,digests.PREFIX+'2026-11-02').value
    assert value['saved_text']==text and value['status']=='closed'


def test_report_refresh_failure_preserves_last_successful_snapshot(schedule):
    digests.tick(schedule,NOW,collector=empty)
    key=digests.PREFIX+'2026-11-02'
    original=deepcopy(schedule.get(models.AutoReglueConfig,key).value)
    def failed(*args):raise RuntimeError('read failed')
    with pytest.raises(RuntimeError):digests.tick(schedule,NOW+timedelta(hours=1),collector=failed)
    schedule.rollback()
    assert schedule.get(models.AutoReglueConfig,key).value==original


def test_restricted_reader_gets_only_allowed_counts_and_never_global_chat(schedule):
    def collect(*args):return {'rows':[
        row('allowed',events=[{'id':'a','kind':'page_added','path':'/a/','words':10}]),
        row('secret',events=[{'id':'s','kind':'page_added','path':'/s/','words':1000}]),
    ],'operations':[],'runs':[],'review':[{'key':'private','site_id':'secret','kind':'text'}]}
    digests.tick(schedule,NOW,collector=collect)
    record=schedule.get(models.AutoReglueConfig,digests.PREFIX+'2026-11-02')
    record.value={**record.value,'saved_text':'secret global text'}
    result=digests.public_view(record,{'allowed_site_ids':['allowed']})
    assert result['projects']==1 and result['manual_review_count']==0
    assert 'saved_text' not in result and 'secret' not in result['text']
    no_access=digests.public_view(record,{'allowed_site_ids':[]})
    assert no_access['projects']==0 and no_access['manual_review_count']==0
    assert 'saved_text' not in no_access
    assert digests.public_view(record,{'allowed_site_ids':None})['saved_text']=='secret global text'


def test_api_requires_auth_and_rejects_non_monday_dates(schedule):
    from app.main import app
    from fastapi.testclient import TestClient
    response=TestClient(app).get('/api/weekly-digests')
    assert response.status_code==401
    response=TestClient(app).get('/api/weekly-digests/2026-11-02')
    assert response.status_code==401
    for invalid in ['2026-11-03','2026-02-30','secret']:
        with pytest.raises(HTTPException) as error:digests.detail(invalid,{'allowed_site_ids':None},schedule)
        assert error.value.status_code==422


def test_weekly_schedule_is_registered_without_starting_generations():
    from app.worker import celery_app
    entry=celery_app.conf.beat_schedule['weekly-work-digests']
    assert entry['task']=='app.worker.refresh_weekly_digests'
    assert entry['options']['expires']==60
    assert celery_app.conf.task_routes[entry['task']]['queue']=='maintenance'
