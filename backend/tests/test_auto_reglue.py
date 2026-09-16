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
    cfg=auto.ProjectConfig(enabled=True,drop_domain='clubheavenjax.com',language='az',fake_main_path='/events/',profile_id='pinup:az:clubheavenjax.com',variant='after')
    return site,state,auto.GlobalConfig(enabled=True,scheme_mode='add_auxiliary',auxiliary_hreflangs=['fr-FR']),cfg


def test_next_unused_subdomain_and_fixed_drop_with_preserved_extras():
    site,state,global_cfg,cfg=fixture()
    plan=auto.build_plan(site,state,global_cfg,cfg)
    assert plan['new_main']=='next.clubheavenjax.com'
    assert 'https://next.clubheavenjax.com/events/' in plan['alternateMarkup']
    assert 'hreflang="tr" href="https://next.clubheavenjax.com/extra/"' in plan['alternateMarkup']
    assert 'hreflang="fr-FR"' in plan['alternateMarkup']
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


def setup_run(monkeypatch, unknown_action=None, create=False):
    client,sessions=make_client()
    _,state,g,cfg=fixture()
    with sessions() as db:
        site=db.scalar(select(models.Site));site.name='clubheavenjax.com';site.project_status='mass_actions';site.cache_geo='AZ';site.main_domain_history=['old.clubheavenjax.com','used.clubheavenjax.com'];db.commit()
        if create:
            cfg.create_subdomains=True; cfg.subdomain_name_style='joined'
            site.brand='Pinco'; site.domain_types={'clubheavenjax.com':'drop'}
            state['domains'].append('clubheavenjax.com'); site.cache_domains=list(state['domains']); db.commit()
        auto.save_config(db,g);auto.save_config(db,cfg,site.id)
        plan=auto.build_plan(site,state,g,cfg)
        run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='admin',plan=plan,status='queued',phase='prepared');db.add(run);db.commit();run_id=run.id
    calls=[]
    def read(db,site):return dict(state,revision=state_revision(state))
    def change(db,site,payload,username,**kwargs):
        calls.append(payload.action)
        if payload.action=='create_subdomains': pass
        elif payload.action=='reserve':state['reserve']=payload.domain
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
    monkeypatch.setattr(auto, 'verify_pages', lambda urls: None)
    db,site,remote=env
    site.project_status='mass_actions';site.cache_geo='AZ';db.commit()
    remote.data['settings']['domains']=['main.test','next.project.test']
    cfg=auto.ProjectConfig(enabled=True,drop_domain='project.test',language='az',fake_main_path='/events/')
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


def test_scheme_modes_add_one_then_preserve_when_exhausted():
    from app.network_state import alternate_links
    site, state, g, cfg = fixture()
    cfg.profile_id = ''
    g.auxiliary_hreflangs = ['az-AZ', 'tr', 'de-DE', 'fr-FR']
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['added_hreflang'] == 'de-DE'
    assert 'fr-FR' not in plan['alternateMarkup']
    state['alternateMarkup'] = plan['alternateMarkup']
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['added_hreflang'] == 'fr-FR'
    state['alternateMarkup'] = plan['alternateMarkup']
    exhausted = auto.build_plan(site, state, g, cfg)
    assert exhausted['pool_exhausted']
    g.scheme_mode = 'preserve'
    g.auxiliary_hreflangs.append('es-ES')
    preserved = auto.build_plan(site, state, g, cfg)
    assert 'es-ES' not in preserved['alternateMarkup']
    assert [x['hreflang'] for x in alternate_links(preserved['alternateMarkup'])] == [x['hreflang'] for x in alternate_links(state['alternateMarkup'])]


def test_personal_overrides_mass_status_and_global_rules():
    site, state, g, cfg = fixture()
    cfg.scope = 'personal'; cfg.scheme_mode = 'preserve'
    site.project_status = 'working'; g.enabled = False
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['scope'] == 'personal' and plan['scheme_mode'] == 'preserve'
    assert 'fr-FR' not in plan['alternateMarkup']


def test_schedule_due_time_personal_priority_and_mass_exclusion(monkeypatch):
    from datetime import datetime, timedelta, timezone
    _, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site))
        g = auto.GlobalConfig(enabled=True, schedule_enabled=True, interval_days=3)
        cfg = auto.ProjectConfig(enabled=True, drop_domain='drop.test', language='az',fake_main_path='/events/')
        site.project_status = 'mass_actions'; db.commit()
        auto.save_config(db, g); auto.save_config(db, cfg, site.id)
        initial = auto.next_scheduled_at(db, site)
        assert abs((initial - datetime.now(timezone.utc)).total_seconds()) < 5
        auto.save_config(db, cfg, site.id)
        assert auto.next_scheduled_at(db, site) == initial
        cfg.scope = 'personal'; cfg.interval_days = 14; cfg.schedule_enabled = True
        auto.save_config(db, cfg, site.id)
        g.enabled = False; auto.save_config(db, g)
        site.project_status = 'working'; db.commit()
        assert auto.next_scheduled_at(db, site) == initial
        with pytest.raises(ValueError, match='персональные'):
            auto.prepare_run(db, site, uuid4(), 'irrelevant', 'admin', 'mass')
        cfg.schedule_enabled = False; auto.save_config(db, cfg, site.id)
        assert auto.next_scheduled_at(db, site) is None


def test_schedule_queues_once_blocks_overlap_and_records_preflight_error(monkeypatch):
    from datetime import datetime, timedelta, timezone
    _, sessions = make_client()
    _, state, g, cfg = fixture()
    g.schedule_enabled = True; g.interval_days = 3
    monkeypatch.setattr(auto.project_network, 'read_network', lambda db, site: dict(state, revision=state_revision(state)))
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.name = 'clubheavenjax.com'; site.cache_geo = 'AZ'; site.project_status = 'mass_actions'
        db.commit()
        auto.save_config(db, g); auto.save_config(db, cfg, site.id)
        anchor = datetime.now(timezone.utc)
        schedule = db.get(models.AutoReglueSchedule, site.id)
        schedule.next_run_at = anchor
        db.commit()
        queued = []
        ids = auto.schedule_tick(db, queued.append)
        assert ids == queued and len(ids) == 1
        run = db.get(models.AutoReglueRun, ids[0])
        assert run.plan['scheduled'] and run.status == 'queued'
        run.status = 'running'; db.commit()
        assert auto.schedule_tick(db, queued.append) == []
        run.status = 'completed'; run.updated_at = datetime.now(timezone.utc); db.commit()
        assert auto.next_scheduled_at(db, site) > datetime.now(timezone.utc) + timedelta(days=2)
        run.updated_at = anchor + timedelta(hours=1); db.commit()
        def fail(*_): raise ValueError('no candidate')
        monkeypatch.setattr(auto, 'preview', fail)
        failed_ids = auto.schedule_tick(db, queued.append, anchor + timedelta(days=3, seconds=1))
        assert len(failed_ids) == 1 and len(queued) == 1
        assert db.get(models.AutoReglueRun, failed_ids[0]).status == 'failed'
        assert auto.schedule_tick(db, queued.append, anchor + timedelta(days=3, seconds=2)) == []


def test_supported_intervals_and_language_pool():
    from app.alternate_language_pool import COUNTRY_LANGUAGES, default_language_pool
    assert len(COUNTRY_LANGUAGES) == 38
    assert len(default_language_pool()) == len(set(default_language_pool()))
    assert 'cs-CZ' in default_language_pool() and 'kk-KZ' in default_language_pool()
    for days in [3,4,5,7,14]:
        assert auto.GlobalConfig(interval_days=days).interval_days == days
    with pytest.raises(ValueError):
        auto.GlobalConfig(interval_days=6)


def test_base_scheme_uses_project_language_geo_and_explicit_xdefault_newreg():
    from app.network_state import alternate_links
    site, state, g, cfg = fixture()
    site.cache_language = 'az-AZ'
    cfg.language = 'en'; cfg.profile_id = ''; g.scheme_mode = 'preserve'
    state['alternateMarkup'] = ''
    links = alternate_links(auto.build_plan(site, state, g, cfg)['alternateMarkup'])
    assert [(x['hreflang'], x['href']) for x in links] == [
        ('az', 'https://next.clubheavenjax.com/'),
        ('az-AZ', 'https://next.clubheavenjax.com/events/'),
        ('x-default', 'https://clubheavenjax.com/'),
    ]
    cfg.x_default_use_newreg = True
    with pytest.raises(ValueError, match='новорег'):
        auto.build_plan(site, state, g, cfg)
    cfg.x_default_newreg_domain = 'newreg.test'
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['x_default_domain'] == 'newreg.test'
    assert 'hreflang="x-default" href="https://newreg.test/"' in plan['alternateMarkup']
    cfg.x_default_use_newreg = False
    site.domain_types = {'clubheavenjax.com': 'newreg'}
    with pytest.raises(ValueError, match='отмечен как новорег'):
        auto.build_plan(site, state, g, cfg)


def test_personal_project_not_listed_or_accepted_in_mass_api():
    from app.auto_reglue_api import router
    client, sessions = make_client()
    client.app.include_router(router, prefix='/api')
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.project_status = 'mass_actions'; db.commit()
        site_id = site.id
        auto.save_config(db, auto.ProjectConfig(scope='personal', enabled=True, drop_domain='drop.test', language='az'), site.id)
    assert client.get('/api/auto-reglue').json()['projects'] == []
    result = client.post('/api/auto-reglue/start', json={'items':[{'site_id':site_id, 'request_id':str(uuid4()), 'preview_token':'a'*64}]})
    assert 'персональные' in result.json()['results'][0]['error']


def test_root_canonical_and_xdefault_rotate_together_with_child_languages():
    from app.network_state import alternate_links
    site, state, g, cfg = fixture()
    cfg.domain_layout = 'root_main'; cfg.profile_id = ''; g.scheme_mode = 'preserve'
    site.domain_types = {'old.test':'drop', 'used.test':'drop', 'next.test':'drop', 'newreg.test':'newreg'}
    site.main_domain_history = ['old.test','used.test']
    site.alternate_domain_history = ['used.next.test']
    state.update(canon='old.test', prev='', domains=['old.test','used.test','next.test','used.next.test','az.next.test','newreg.test','az.newreg.test'])
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['new_main'] == plan['x_default_domain'] == 'next.test'
    assert plan['language_domain'] == 'az.next.test'
    links = {x['hreflang']: x['href'] for x in alternate_links(plan['alternateMarkup'])}
    assert links['az'] == 'https://az.next.test/'
    assert links['az-AZ'] == 'https://az.next.test/events/'
    assert links['x-default'] == 'https://next.test/'
    cfg.x_default_use_newreg = True
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['new_main'] == plan['x_default_domain'] == 'newreg.test'
    assert plan['language_domain'] == 'az.newreg.test'


def test_missing_child_blocks_root_change_before_any_write():
    site, state, g, cfg = fixture()
    cfg.domain_layout = 'root_main'
    site.domain_types = {'next.test':'drop'}
    state.update(canon='old.test', domains=['old.test','next.test'])
    with pytest.raises(ValueError, match='нет неиспользованного поддомена'):
        auto.build_plan(site, state, g, cfg)


@pytest.mark.parametrize('personal', [False, True])
@pytest.mark.parametrize('newreg', [False, True])
def test_base_only_keeps_exactly_three_links_despite_template_and_existing_extras(personal, newreg):
    from app.network_state import alternate_links
    site, state, g, cfg = fixture()
    g.scheme_mode = 'base_only'
    state['domains'].extend(['fresh-drop.test', 'newreg.test'])
    site.domain_types = {'fresh-drop.test': 'drop', 'newreg.test': 'newreg'}
    cfg.scheme_mode = 'base_only' if personal else 'add_auxiliary'
    cfg.scope = 'personal' if personal else 'mass'
    cfg.x_default_use_newreg = newreg
    cfg.x_default_newreg_domain = 'newreg.test'
    plan = auto.build_plan(site, state, g, cfg)
    links = alternate_links(plan['alternateMarkup'])
    assert [x['hreflang'] for x in links] == ['az', 'az-AZ', 'x-default']
    assert links[0]['href'] == 'https://next.clubheavenjax.com/'
    assert links[1]['href'] == 'https://next.clubheavenjax.com/events/'
    assert links[2]['href'] == ('https://newreg.test/' if newreg else 'https://fresh-drop.test/')
    assert plan['added_hreflang'] is None and not plan['pool_exhausted']


@pytest.mark.parametrize('language,geo', [('de','DE'), ('pl','PL'), ('en','CA')])
def test_base_only_uses_each_projects_language_and_geo(language, geo):
    from app.network_state import alternate_links
    site, state, g, cfg = fixture()
    site.cache_language = language
    site.cache_geo = geo
    cfg.profile_id = ''
    g.scheme_mode = 'base_only'
    state['domains'].extend(['fresh-drop.test', 'newreg.test'])
    site.domain_types = {'fresh-drop.test': 'drop', 'newreg.test': 'newreg'}
    plan = auto.build_plan(site, state, g, cfg)
    assert [x['hreflang'] for x in alternate_links(plan['alternateMarkup'])] == [language, f'{language}-{geo}', 'x-default']


def test_unused_xdefault_excludes_all_history_current_markup_aliases_and_main_parent():
    site, state, g, cfg = fixture()
    g.scheme_mode = 'base_only'
    candidates = ['clubheavenjax.com', 'former-main.test', 'www.former-default.test', 'former-alternate.test', 'current-default.test', 'untyped.test', 'newreg.test', 'fresh-drop.test']
    state['domains'].extend(candidates)
    site.domain_types = {d: 'drop' for d in candidates if d != 'untyped.test'}
    site.domain_types['newreg.test'] = 'newreg'
    site.main_domain_history.append('former-main.test')
    site.x_default_history = ['former-default.test']
    site.alternate_domain_history = ['former-alternate.test']
    state['alternateMarkup'] += '\n<link rel="alternate" hreflang="x-default" href="https://current-default.test/" />'
    plan = auto.build_plan(site, state, g, cfg)
    assert plan['x_default_domain'] == 'fresh-drop.test'
    assert plan['new_main'] == plan['language_domain']
    assert plan['x_default_domain'] != plan['new_main']
    site.x_default_history.append('fresh-drop.test')
    with pytest.raises(ValueError, match='нет неиспользованного дропа'):
        auto.build_plan(site, state, g, cfg)


def test_schedule_recovers_queue_failure_and_keeps_calendar(monkeypatch):
    from datetime import datetime, timedelta, timezone
    _, sessions = make_client()
    _, state, g, cfg = fixture()
    g.schedule_enabled = True; g.interval_days = 3
    monkeypatch.setattr(auto.project_network, 'read_network', lambda db, site: dict(state, revision=state_revision(state)))
    anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with sessions() as db:
        site = db.scalar(select(models.Site))
        site.name = 'clubheavenjax.com'; site.cache_geo = 'AZ'; site.project_status = 'mass_actions'
        db.commit()
        auto.save_config(db, g); auto.save_config(db, cfg, site.id)
        schedule = db.get(models.AutoReglueSchedule, site.id)
        schedule.anchor_at = anchor; schedule.next_run_at = anchor; db.commit()
        def unavailable(_): raise RuntimeError('queue unavailable')
        with pytest.raises(RuntimeError):
            auto.schedule_tick(db, unavailable, anchor + timedelta(days=10))
        run = db.scalar(select(models.AutoReglueRun))
        receipt = run.id
        assert run.status == 'queued'
        assert auto.next_scheduled_at(db, site) == anchor + timedelta(days=12)
    with sessions() as db:
        site = db.scalar(select(models.Site))
        queued = []
        assert auto.schedule_tick(db, queued.append, anchor + timedelta(days=10)) == [receipt]
        assert queued == [receipt]
        assert len(db.scalars(select(models.AutoReglueRun)).all()) == 1
        run = db.get(models.AutoReglueRun, receipt)
        run.status = 'completed'; db.commit()
        auto.save_config(db, cfg, site.id)
        assert auto.next_scheduled_at(db, site) == anchor + timedelta(days=12)
        g.schedule_enabled = False; auto.save_config(db, g)
        assert auto.next_scheduled_at(db, site) is None
        g.schedule_enabled = True; auto.save_config(db, g)
        assert auto.next_scheduled_at(db, site) == anchor + timedelta(days=12)
        g.interval_days = 14; auto.save_config(db, g)
        assert auto.next_scheduled_at(db, site) == anchor + timedelta(days=14)


def test_legacy_schedule_keeps_due_date_on_upgrade():
    from datetime import datetime, timedelta, timezone
    _, sessions = make_client()
    anchor = datetime(2026, 9, 15, tzinfo=timezone.utc)
    with sessions() as db:
        site = db.scalar(select(models.Site)); site.project_status = 'mass_actions'
        db.add(models.AutoReglueConfig(key='global', value={**auto.GlobalConfig(enabled=True, schedule_enabled=True, interval_days=3).model_dump(), '_schedule_since': anchor.isoformat()}))
        db.add(models.AutoReglueConfig(key=site.id, value={**auto.ProjectConfig(enabled=True).model_dump(), '_schedule_since': anchor.isoformat()}))
        db.commit()
        auto.sync_schedules(db, anchor + timedelta(days=1)); db.commit()
        assert auto.next_scheduled_at(db, site) == anchor + timedelta(days=3)


def test_once_default_all_mass_projects_personal_excluded_and_no_repeats(monkeypatch):
    from datetime import datetime, timedelta, timezone
    _, sessions = make_client()
    assert auto.GlobalConfig().interval_days == auto.ProjectConfig().interval_days == 0
    monkeypatch.setattr(auto, 'preview', lambda db, site: {'project': site.name})
    with sessions() as db:
        original = db.scalar(select(models.Site))
        original.project_status = 'mass_actions'
        # Copy required Site fields without copying relationships.
        from sqlalchemy.inspection import inspect
        values = {c.key: getattr(original, c.key) for c in inspect(models.Site).columns
                  if c.key not in {'id', 'name', 'created_at', 'updated_at'}}
        second = models.Site(id=str(uuid4()), name='second.test', **values)
        personal = models.Site(id=str(uuid4()), name='personal.test', **values)
        db.add_all([second, personal]); db.commit()
        for site in [original, second]:
            auto.save_config(db, auto.ProjectConfig(enabled=True), site.id)
        auto.save_config(db, auto.ProjectConfig(enabled=True, scope='personal', schedule_enabled=False), personal.id)
        g = auto.GlobalConfig(enabled=True, schedule_enabled=True, max_projects=1)
        auto.save_config(db, g)
        queued = []
        now = datetime.now(timezone.utc)
        first = auto.schedule_tick(db, queued.append, now)
        assert len(first) == 1
        run = db.get(models.AutoReglueRun, first[0])
        # Queue recovery uses the same receipt even though this was the only slot.
        assert auto.schedule_tick(db, queued.append, now) == first
        run.status = 'completed'; db.commit()
        second_run = auto.schedule_tick(db, queued.append, now)
        assert len(second_run) == 1 and second_run != first
        db.get(models.AutoReglueRun, second_run[0]).status = 'completed'; db.commit()
        auto.save_config(db, g)
        assert auto.schedule_tick(db, queued.append, now + timedelta(days=90)) == []
        runs = db.scalars(select(models.AutoReglueRun)).all()
        assert {r.site_id for r in runs} == {original.id, second.id}
        assert all(auto.next_scheduled_at(db, site) is None for site in [original, second, personal])


def test_amp_excluded_from_next_main_and_fixed_xdefault():
    site,state,global_cfg,cfg=fixture()
    state['amp_domains']=['next.clubheavenjax.com']
    assert auto.build_plan(site,state,global_cfg,cfg)['new_main']=='last.clubheavenjax.com'
    state['amp_domains'].append('clubheavenjax.com')
    with pytest.raises(ValueError,match='AMP'):
        auto.build_plan(site,state,global_cfg,cfg)


def test_amp_excluded_from_root_child_and_unused_xdefault():
    site,state,global_cfg,cfg=fixture()
    site.domain_types={'amp.test':'drop','clean.test':'drop','last.test':'drop'}
    state['domains']=[state['canon'],'amp.test','child.amp.test','clean.test','amp.clean.test','child.clean.test','last.test']
    state['amp_domains']=['amp.test','amp.clean.test']
    assert auto.select_root_and_subdomain(site,state,cfg)==('clean.test','child.clean.test')
    assert auto.select_unused_xdefault(site,state,cfg,'next.clubheavenjax.com')=='clean.test'


def test_create_wait_resume_https_and_no_duplicate_creation(monkeypatch):
    sessions,run_id,calls,state=setup_run(monkeypatch,'create_subdomains',create=True)
    def unavailable(urls): raise ValueError('not ready')
    monkeypatch.setattr(auto,'verify_pages',unavailable)
    with sessions() as db:
        run=db.get(models.AutoReglueRun,run_id)
        target=run.plan['create_subdomain']
        assert target=='pincoaz.clubheavenjax.com'
        auto.execute(db,run_id); auto.execute(db,run_id)
        assert calls==['create_subdomains']
        assert run.status=='waiting'
        receipt=str(uuid5(UUID(run_id),'create_subdomains'))
        db.get(models.NetworkOperation,receipt).status='confirmed'
        state['domains'].append(target); db.commit()
        auto.execute(db,run_id)
        assert run.phase=='subdomain_ready' and run.status=='waiting'
        assert calls==['create_subdomains']
        monkeypatch.setattr(auto,'verify_pages',lambda urls:None)
        auto.execute(db,run_id); auto.execute(db,run_id)
        assert run.status=='completed'
        assert calls==['create_subdomains','reserve','reglue','alternates']
        assert state['canon']==target


def test_subdomain_names_collisions_casino_and_exhaustion():
    from app.subdomain_naming import next_subdomain
    site,state,g,cfg=fixture()
    cfg.create_subdomains=True; cfg.subdomain_name_style='joined'
    site.brand='Pinco'; site.domain_types={'clubheavenjax.com':'drop'}
    state['domains'].append('clubheavenjax.com'); site.cache_domains=list(state['domains'])
    assert next_subdomain(site,state,cfg,cfg.drop_domain)=='pincoaz.clubheavenjax.com'
    state['domains'].append('pincoaz.clubheavenjax.com')
    site.main_domain_history.append('pincoaz1.clubheavenjax.com')
    assert next_subdomain(site,state,cfg,cfg.drop_domain)=='pincoaz2.clubheavenjax.com'
    state['domains'] += ['pincoaz'+str(i)+'.clubheavenjax.com' for i in range(1,11)]
    assert next_subdomain(site,state,cfg,cfg.drop_domain)=='pincoazaz.clubheavenjax.com'
    state['domains'].append('pincoazaz.clubheavenjax.com')
    with pytest.raises(ValueError,match='заняты'):next_subdomain(site,state,cfg,cfg.drop_domain)
    cfg.subdomain_add_casino=True
    assert next_subdomain(site,state,cfg,cfg.drop_domain)=='pincocasinoaz.clubheavenjax.com'
    cfg.parent_kind='newreg'
    with pytest.raises(ValueError,match='Тип родителя'):next_subdomain(site,state,cfg,cfg.drop_domain)
    site.domain_types[cfg.drop_domain]='newreg'
    assert next_subdomain(site,state,cfg,cfg.drop_domain)=='pincocasinoaz.clubheavenjax.com'
    state['amp_domains']=[cfg.drop_domain]
    with pytest.raises(ValueError,match='AMP'):next_subdomain(site,state,cfg,cfg.drop_domain)


def test_mixed_naming_is_stable_and_varies_after_each_creation():
    from app.subdomain_naming import next_subdomain
    site,state,g,cfg=fixture()
    site.brand='Pinco'; site.domain_types={'clubheavenjax.com':'drop'}
    state['domains'].append('clubheavenjax.com'); site.cache_domains=list(state['domains'])
    cfg.create_subdomains=True; cfg.subdomain_add_casino=True
    generated=[]
    for _ in range(48):
        name=next_subdomain(site,state,cfg,cfg.drop_domain)
        assert name==next_subdomain(site,state,cfg,cfg.drop_domain)
        generated.append(name); state['domains'].append(name)
    assert len(set(generated))==48
    assert any('-' in name.split('.')[0] for name in generated)
    assert any('-' not in name.split('.')[0] for name in generated)
    assert any('casino' in name for name in generated)
    with pytest.raises(ValueError,match='заняты'):next_subdomain(site,state,cfg,cfg.drop_domain)


def test_root_main_creation_uses_new_child_for_languages_only():
    site,state,g,cfg=fixture()
    site.brand='Pinco'; site.domain_types={'newroot.test':'drop'}
    state['domains'].append('newroot.test'); site.cache_domains=list(state['domains'])
    cfg.domain_layout='root_main'; cfg.create_subdomains=True; cfg.subdomain_name_style='hyphen'
    plan=auto.build_plan(site,state,g,cfg)
    assert plan['new_main']==plan['x_default_domain']=='newroot.test'
    assert plan['language_domain']==plan['create_subdomain']=='pinco-az.newroot.test'
    assert 'https://pinco-az.newroot.test/events/' in plan['alternateMarkup']
