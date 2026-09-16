from types import SimpleNamespace
from uuid import uuid4, uuid5, UUID

import pytest
from sqlalchemy import select

from app import auto_reglue as auto, models
from app.network_state import state_revision
from test_api_serialization import make_client


def fixture():
    site = SimpleNamespace(id='site', name='clubheavenjax.com', project_status='mass_actions', cache_geo='AZ', main_domain_history=['old.clubheavenjax.com','used.clubheavenjax.com'])
    state = dict(canon='old.clubheavenjax.com', prev='', reserve='', domains=['first.clubheavenjax.com','old.clubheavenjax.com','used.clubheavenjax.com','next.clubheavenjax.com','last.clubheavenjax.com'], has_head=True, enableAlternates=True, alternateMarkup='<link rel="alternate" hreflang="tr" href="https://old.clubheavenjax.com/extra/" />')
    cfg=auto.ProjectConfig(enabled=True,drop_domain='clubheavenjax.com',language='az',profile_id='pinup:az:clubheavenjax.com',variant='after')
    return site,state,auto.GlobalConfig(enabled=True,auxiliary_hreflangs=['fr-AZ']),cfg


def test_next_unused_subdomain_and_fixed_drop_with_preserved_extras():
    site,state,global_cfg,cfg=fixture()
    plan=auto.build_plan(site,state,global_cfg,cfg)
    assert plan['new_main']=='next.clubheavenjax.com'
    assert 'https://next.clubheavenjax.com/events/' in plan['alternateMarkup']
    assert 'hreflang="tr" href="https://next.clubheavenjax.com/extra/"' in plan['alternateMarkup']
    assert 'hreflang="fr-AZ"' in plan['alternateMarkup']
    assert 'hreflang="x-default" href="https://clubheavenjax.com/"' in plan['alternateMarkup']
    assert 'rel="canonical"' not in plan['alternateMarkup']


def test_newreg_and_geo_validation():
    site,state,g,cfg=fixture()
    cfg.parent_kind='newreg';cfg.newreg_domain='newreg.test'
    state['domains'].append('next.newreg.test')
    assert auto.build_plan(site,state,g,cfg)['new_main']=='next.newreg.test'
    site.cache_geo='PL'
    with pytest.raises(ValueError,match='GEO'):auto.build_plan(site,state,g,cfg)
    site.cache_geo='AZ';site.project_status='working'
    with pytest.raises(ValueError,match='Массовые'):auto.build_plan(site,state,g,cfg)


def test_exhaustion_does_not_recycle_or_wrap():
    site,state,g,cfg=fixture()
    state['canon']='last.clubheavenjax.com'
    with pytest.raises(ValueError,match='нет неиспользованного'):auto.build_plan(site,state,g,cfg)


def setup_run(monkeypatch, unknown_action=None):
    client,sessions=make_client()
    _,state,g,cfg=fixture()
    with sessions() as db:
        site=db.scalar(select(models.Site));site.name='clubheavenjax.com';site.project_status='mass_actions';site.cache_geo='AZ';site.main_domain_history=['old.clubheavenjax.com','used.clubheavenjax.com'];db.commit()
        auto.save_config(db,g);auto.save_config(db,cfg,site.id)
        plan=auto.build_plan(site,state,g,cfg)
        run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='admin',plan=plan,status='queued',phase='prepared');db.add(run);db.commit();run_id=run.id
    calls=[]
    def read(db,site):return dict(state,revision=state_revision(state))
    def change(db,site,payload,username,**kwargs):
        calls.append(payload.action)
        if payload.action=='reserve':state['reserve']=payload.domain
        elif payload.action=='reglue':state['canon']=payload.domain
        else:state['alternateMarkup']=payload.alternate_markup
        op=models.NetworkOperation(id=str(payload.request_id),site_id=site.id,action=payload.action,status='unknown' if payload.action==unknown_action else 'confirmed',initiator=username,request_payload={},message='test')
        db.add(op);db.commit()
    monkeypatch.setattr(auto.project_network,'read_network',read)
    monkeypatch.setattr(auto.project_network,'change_network',change)
    monkeypatch.setattr(auto,'verify_pages',lambda urls:None)
    return sessions,run_id,calls,state


def test_executor_sequence_and_duplicate_delivery(monkeypatch):
    sessions,run_id,calls,state=setup_run(monkeypatch)
    with sessions() as db:
        auto.execute(db,run_id);auto.execute(db,run_id)
        assert db.get(models.AutoReglueRun,run_id).status=='completed'
    assert calls==['reserve','reglue','alternates']
    assert state['canon']=='next.clubheavenjax.com'


def test_timeout_pauses_and_never_resends_unknown_step(monkeypatch):
    sessions,run_id,calls,state=setup_run(monkeypatch,'reglue')
    with sessions() as db:
        auto.execute(db,run_id)
        assert db.get(models.AutoReglueRun,run_id).status=='waiting'
        auto.execute(db,run_id)
        assert calls==['reserve','reglue']
        receipt=str(uuid5(UUID(run_id),'reglue'))
        db.get(models.NetworkOperation,receipt).status='confirmed';db.commit()
        auto.execute(db,run_id)
        assert db.get(models.AutoReglueRun,run_id).status=='completed'
    assert calls==['reserve','reglue','alternates']


def test_api_is_admin_only_and_defaults_disabled():
    from app.auto_reglue_api import router
    from app.security import require_auth
    client,_=make_client();client.app.include_router(router,prefix='/api')
    response=client.get('/api/auto-reglue')
    assert response.status_code==200
    assert response.json()['settings']['enabled'] is False
    assert response.json()['projects']==[]
    client.app.dependency_overrides[require_auth]=lambda:{'id':'user','username':'user','is_admin':False}
    assert client.get('/api/auto-reglue').status_code==403


def test_missing_copy_page_stops_before_reserve(monkeypatch):
    sessions,run_id,calls,_=setup_run(monkeypatch)
    def missing(urls): raise ValueError('Copy page not found')
    monkeypatch.setattr(auto,'verify_pages',missing)
    with sessions() as db:
        auto.execute(db,run_id)
        assert db.get(models.AutoReglueRun,run_id).status=='failed'
    assert not calls


def test_preview_becomes_invalid_when_settings_change(monkeypatch):
    sessions,run_id,calls,_=setup_run(monkeypatch)
    with sessions() as db:
        cfg=auto.config(db);cfg.auxiliary_hreflangs=['ru'];auto.save_config(db,cfg)
        auto.execute(db,run_id)
        assert db.get(models.AutoReglueRun,run_id).status=='failed'
    assert not calls


# Use the real network service with an in-memory Webdev transport.
from test_project_network import env


def test_real_receipts_confirm_entire_automatic_sequence(env,monkeypatch):
    db,site,remote=env
    site.project_status='mass_actions';site.cache_geo='AZ';db.commit()
    remote.data['settings']['domains']=['main.test','next.project.test']
    cfg=auto.ProjectConfig(enabled=True,drop_domain='project.test',language='az')
    auto.save_config(db,auto.GlobalConfig(enabled=True));auto.save_config(db,cfg,site.id)
    plan=auto.preview(db,site)
    run,fresh=auto.prepare_run(db,site,uuid4(),plan['preview_token'],'admin')
    assert fresh
    duplicate,is_fresh=auto.prepare_run(db,site,UUID(run.id),plan['preview_token'],'admin')
    assert duplicate.id==run.id and not is_fresh
    # Manual writes must not race an automatic run.
    from app import project_network
    with pytest.raises(project_network.NetworkConflict,match='автопереклей'):
        project_network.change_network(db,site,project_network.NetworkChange(request_id=uuid4(),action='reserve',revision='stale',domain='next.project.test'),'admin')
    auto.execute(db,run.id)
    db.refresh(run)
    assert run.status=='completed',run.message
    assert [call[1] for call in remote.calls]==['/projects/update-value','/projects/check-domain','/projects/update-reglue','/projects/update-head']
    assert remote.data['settings']['canon']=='next.project.test'
    assert 'hreflang="x-default" href="https://project.test/"' in remote.data['head']['alternateMarkup']
    assert 'next.project.test' in site.main_domain_history
    assert remote.data['settings']['alternate']['fakeMain']==['/cz/']
