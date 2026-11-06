from uuid import uuid4
from app import models, auto_pilot as pilot, mass_reglue_launch as launch, reglue_reserves as stock
from app.pilot_replanning import request
from app.pilot_scope import selection
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_auto_pilot import USER


def test_stock_checkbox_defaults_enabled_and_false_survives_replanning(pool):
    db,source,target,remotes,add=pool
    job=pilot.create(db,uuid4(),USER)
    assert pilot.view(db,job)['allow_stock_drops'] is True
    request(db,job.id,uuid4(),USER,scope=selection(),percentages=None,title_rewrite_mode='minimal',allow_stock_drops=False)
    assert job.payload['allow_stock_drops'] is False
    launch.execute_step(db,job.id,lambda _:None)
    assert pilot.view(db,job)['allow_stock_drops'] is False
    assert not any(p.get('reserve_pool_id') and p.get('domain_type')=='drop' for g in job.result['groups'] for p in g.get('plans',[]))
    assert 'pilot_allow_stock_drops' not in db.info


def test_disabled_stock_drops_keeps_stock_newregs_available(pool):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit()
    stock.import_domains(db,'stock-drop.test','drop','', 'test')
    stock.import_domains(db,'stock-newreg.test','newreg','', 'test')
    state=remotes[target.id].data
    from app.network_state import project_network_state
    state=project_network_state(state)
    assert stock.candidate(db,target,state,['drop']).domain=='stock-drop.test'
    db.info['pilot_allow_stock_drops']=False
    assert stock.candidate(db,target,state,['drop']) is None
    assert stock.candidate(db,target,state,['newreg']).domain=='stock-newreg.test'
    assert all(not r.calls for r in remotes.values())
