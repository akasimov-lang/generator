from datetime import datetime, timezone, timedelta
from uuid import uuid4
from app import models
from app.reglue_journal import recent_for_site
from test_project_network import env


def receipt(db,site,action,before,after,at,status='confirmed',actor='other'):
    op=models.NetworkOperation(id=str(uuid4()),site_id=site.id,action=action,status=status,initiator=actor,
        request_payload={'confirmed_at':at.isoformat(),'source_domain':'old.test','reserve':'main.test',
            'journal_before':{'main':'main.test','fake_path':before},'journal_after':{'main':'main.test','fake_path':after},
            'alternate':{'currentFakeMain':after,'enableDynamicRoutes':True}})
    db.add(op);db.commit();return op


def test_fake_replacement_after_reglue_is_separate_and_uses_receipt_time(env):
    db,site,_=env
    at=datetime(2026,11,5,9,0,tzinfo=timezone.utc)
    receipt(db,site,'reglue','/old/','/first/',at)
    receipt(db,site,'create_fake_main','/first/','/next',at+timedelta(minutes=12))
    site.network_state={'fake_main_current':'/unrelated/'}
    items=recent_for_site(db,site)
    assert [x['kind'] for x in items]==['fake_path','reglue']
    assert items[0]['old_path']=='/first/' and items[0]['new_path']=='/next'
    assert items[0]['at']=='2026-11-05T09:12:00+00:00'


def test_recent_changes_limit_twenty_and_exclude_unconfirmed_and_unchanged(env):
    db,site,_=env
    at=datetime(2026,11,5,tzinfo=timezone.utc)
    for i in range(25):receipt(db,site,'select_fake_main',f'/old-{i}',f'/new-{i}',at+timedelta(minutes=i))
    receipt(db,site,'select_fake_main','/same','/same',at+timedelta(days=1))
    receipt(db,site,'create_fake_main','/old','/pending',at+timedelta(days=2),status='unknown')
    items=recent_for_site(db,site)
    assert len(items)==20
    assert [x['new_path'] for x in items]==[f'/new-{i}' for i in range(24,4,-1)]
