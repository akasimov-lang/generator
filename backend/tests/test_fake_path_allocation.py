from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models, auto_reglue as auto, cross_reglue_batch as batch, project_network as network
from app.fake_path_allocation import next_path, require_available, group_lock
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, reserve


def peer(db, name, brand='Fontan', geo='PL', **values):
    site=models.Site(name=name,base_url='https://'+name,publication_endpoint='/',brand=brand,
                     cache_geo=geo,cache_language='pl',**values)
    db.add(site);db.commit()
    return site


def test_paths_share_a_scope_across_geo_and_brand_spellings_but_not_other_groups(env):
    db,site,_=env;site.brand='Fontan';site.cache_geo='PL';site.cache_language='pl';db.commit()
    peer(db,'same.test',brand='fontan',geo='pl_PL',network_state={'fake_main_current':'/PL1/','fake_main_history':['/pl2/']})
    peer(db,'other-brand.test',brand='Lemon Casino',network_state={'fake_main_current':'/pl3/'})
    peer(db,'other-geo.test',geo='CZ',network_state={'fake_main_current':'/pl3/'})
    peer(db,'inactive.test',is_active=False,network_state={'fake_main_current':'/pl3/'})
    state={'fake_main_current':'/pl/','content_page_paths':['//']}
    assert next_path(db,site,state,SimpleNamespace(language='pl'))=='/pl3/'
    with pytest.raises(ValueError,match='другой сетке'):
        require_available(db,site,'/pl1/')
    require_available(db,site,'/pl3/')


@pytest.mark.parametrize('status',['queued','running','waiting','partial'])
def test_pending_run_and_uncertain_native_assignment_reserve_paths(env,status):
    db,site,_=env;site.brand='Fontan';site.cache_geo='PL';site.cache_language='pl';db.commit()
    other=peer(db,'other.test')
    run=models.AutoReglueRun(id=str(uuid4()),site_id=other.id,initiator='test',status=status,
                            phase='prepared',plan={'create_fake_main_path':'/pl1/'})
    op=models.NetworkOperation(id=str(uuid4()),site_id=other.id,initiator='test',status='unknown',
        action='create_fake_main',request_payload={'alternate':{'fakeMain':['/pl2/'],'currentFakeMain':'/pl2/'}})
    db.add_all([run,op]);db.commit()
    assert next_path(db,site,{'fake_main_current':'/pl/'},SimpleNamespace(language='pl'))=='/pl3/'
    run.status='failed';op.status='failed';db.commit()
    assert next_path(db,site,{'fake_main_current':'/pl/'},SimpleNamespace(language='pl'))=='/pl1/'


def local_reserve_group(pool):
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    sites=[add(f'fontan-{i}.test',size=2,free=1,brand='Fontan',geo='PL',cache_language='pl') for i in range(3)]
    for site in sites:
        data=remotes[site.id].data
        data['settings'].update(reserve=data['settings']['domains'][1],reserveOption=data['settings']['domains'][1],
            alternate={'fakeMain':['/pl/'],'currentFakeMain':'/pl/','enableDynamicRoutes':True})
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='cross_network',scheme_mode='locale_base'))
    return db,sites,remotes


def test_batch_allocates_different_paths_before_any_worker_starts(pool):
    db,sites,remotes=local_reserve_group(pool)
    preview=batch.build(db,sites,'test')
    paths=[p['create_fake_main_path'] for p in preview['plans']]
    assert set(paths)=={'/pl1/','/pl2/','/pl3/'}
    runs=reserve(db,preview)
    assert len(runs)==3
    for run in runs:
        auto.execute(db,run.id)
        assert run.status=='completed',run.message
        assert run.plan['create_fake_main_path'] in run.plan['alternates_after']['markup']
    assert len({remotes[s.id].data['settings']['alternate']['currentFakeMain'] for s in sites})==3


def test_second_prepared_batch_cannot_reserve_a_path_claimed_by_first_batch(pool):
    db,sites,remotes=local_reserve_group(pool)
    first=batch.build(db,[sites[0]],'test');second=batch.build(db,[sites[1]],'test')
    assert first['plans'][0]['fake_main_path']==second['plans'][0]['fake_main_path']
    reserve(db,first)
    with pytest.raises(ValueError,match='зарезервирован'):
        reserve(db,second)
    db.rollback()
    assert not db.scalar(select(models.AutoReglueRun.id).where(models.AutoReglueRun.site_id==sites[1].id))
    assert all(not remotes[s.id].calls for s in sites)
    assert batch.build(db,[sites[1]],'test')['plans'][0]['fake_main_path']!=first['plans'][0]['fake_main_path']


@pytest.mark.parametrize('action',['create_fake_main','select_fake_main'])
def test_manual_assignment_rejects_peer_path_before_remote_write(env,action):
    db,site,remote=env;site.brand='Fontan';site.cache_geo='PL';db.commit()
    peer(db,'peer.test',network_state={'fake_main_current':'/cz/'})
    state=network.read_network(db,site)
    with pytest.raises(ValueError,match='другой сетке'):
        network.change_network(db,site,network.NetworkChange(request_id=uuid4(),action=action,
            revision=state['revision'],fake_main_path='/cz/',activate_fake_main=True),'test')
    assert not remote.calls


def test_preserved_scheme_replaces_old_fake_path_with_group_unique_path(pool):
    db,sites,remotes=local_reserve_group(pool)
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='cross_network',scheme_mode='preserve'))
    site=sites[0];remote=remotes[site.id]
    remote.data['head']['alternateMarkup']=(
        '<link rel="alternate" hreflang="pl" href="https://{{settings.canon}}/" />\n'
        '<link rel="alternate" hreflang="pl-PL" href="https://{{settings.canon}}/pl/" />')
    plan=batch.build(db,[site],'test')['plans'][0]
    assert plan['create_fake_main_path']=='/pl1/'
    assert 'https://{{settings.canon}}/pl1/' in plan['alternateMarkup']
    assert 'https://{{settings.canon}}/"' in plan['alternateMarkup']
    assert plan['canonicalFakeMainMarkup']==auto.fake_canonical_markup('/pl1/')


def test_reservers_use_same_normalized_group_lock(env,monkeypatch):
    db,site,_=env;site.brand='Fontan';site.cache_geo='PL'
    keys=[]
    from contextlib import nullcontext
    monkeypatch.setattr(network,'network_lock',lambda db,key:(keys.append(key) or nullcontext()))
    with group_lock(db,site):pass
    site.brand='fontan';site.cache_geo='pl_PL'
    with group_lock(db,site):pass
    assert keys[0]==keys[1]=='fake-path-group:fontan:PL'
