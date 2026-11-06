from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app import models,auto_pilot as pilot,mass_reglue_launch as launch
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_pilot_variations import make_preview,USER


def test_finished_and_excluded_rows_do_not_block_independent_preview(pool,monkeypatch):
    db,sites,_,preview=make_preview(pool,2)
    monkeypatch.setattr('app.pilot_text_jobs.independent_start',lambda _:True)
    old=deepcopy(preview.result)
    for row in old['items'].values():row['status']='completed'
    old['items']['unrelated']={'status':'waiting'}
    job=models.BackgroundJob(kind=launch.KIND,status='queued',payload={'site_ids':[s.id for s in sites]+['unrelated']},result=old)
    db.add(job);db.commit()
    assert pilot.pending_participants(db,job)=={'unrelated'}
    pilot.start(db,preview.id,USER)
    assert preview.kind==launch.KIND


def test_actual_partial_run_still_blocks_both_donor_and_recipient(env):
    db,site,_=env
    run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='test',status='partial',plan={'source_site_id':'donor'})
    db.add(run);db.commit()
    job=SimpleNamespace(result={'items':{site.id:{'status':'completed','run_id':run.id}},'groups':[]})
    assert pilot.pending_participants(db,job)=={site.id,'donor'}


def test_pending_plan_keeps_donor_reserved_before_native_run_exists(env):
    db,site,_=env
    job=SimpleNamespace(result={'items':{site.id:{'status':'ready'}},'groups':[{'plans':[{'site_id':site.id,'source_site_id':'donor'}]}]})
    assert pilot.pending_participants(db,job)=={site.id,'donor'}
