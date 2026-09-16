from types import SimpleNamespace
from uuid import uuid4, uuid5, UUID

import pytest
from sqlalchemy import select

from app import auto_reglue as auto, models
from app.network_state import state_revision
from test_api_serialization import make_client


def fixture():
    site = SimpleNamespace(id='site', name='clubheavenjax.com', project_status='mass_actions', cache_geo='AZ', main_domain_history=['old.clubheavenjax.com','used.clubheavenjax.com'])
    state = dict(fake_main_current='/events/',fake_main_paths=['/events/'],fake_main_enabled=True,canon='old.clubheavenjax.com', prev='', reserve='', domains=['first.clubheavenjax.com','old.clubheavenjax.com','used.clubheavenjax.com','next.clubheavenjax.com','last.clubheavenjax.com'], has_head=True, enableAlternates=True, alternateMarkup='<link rel="alternate" hreflang="tr" href="https://old.clubheavenjax.com/extra/" />')
    cfg=auto.ProjectConfig(use_current_fake_main=True,enabled=True,drop_domain='clubheavenjax.com',language='az',fake_main_path='/events/',profile_id='pinup:az:clubheavenjax.com',variant='after')
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


def setup_run(monkeypatch, unknown_action=None, create=False, fake=False):
    client,sessions=make_client()
    _,state,g,cfg=fixture()
    with sessions() as db:
        site=db.scalar(select(models.Site));site.name='clubheavenjax.com';site.project_status='mass_actions';site.cache_geo='AZ';site.main_domain_history=['old.clubheavenjax.com','used.clubheavenjax.com'];db.commit()
        if create:
            cfg.create_subdomains=True; cfg.subdomain_name_style='joined'
            site.brand='Pinco'; site.domain_types={'clubheavenjax.com':'drop'}
            state['domains'].append('clubheavenjax.com'); site.cache_domains=list(state['domains']); db.commit()
        cfg.create_fake_main=fake;cfg.use_current_fake_main=not fake
        auto.save_config(db,g);auto.save_config(db,cfg,site.id)
        plan=auto.build_plan(site,state,g,cfg)
        run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='admin',plan=plan,status='queued',phase='prepared');db.add(run);db.commit();run_id=run.id
    calls=[]
    def read(db,site):return dict(state,revision=state_revision(state))
    def change(db,site,payload,username,**kwargs):
        calls.append(payload.action)
        if payload.action=='create_fake_main':
            state['fake_main_paths']=[payload.fake_main_path];state['fake_main_enabled']=True
        elif payload.action=='create_subdomains': pass
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


@pytest.mark.parametrize('brand', ['Общие ключи', '', None])
@pytest.mark.parametrize('style', ['joined', 'hyphen', 'mixed'])
def test_general_keywords_names_and_exhaustion(brand, style):
    from app.subdomain_naming import next_subdomain
    site,state,g,cfg=fixture()
    site.brand=brand; site.cache_language='ru'; site.domain_types={'clubheavenjax.com':'drop'}
    state['domains'].append('clubheavenjax.com'); site.cache_domains=list(state['domains'])
    cfg.create_subdomains=True; cfg.subdomain_name_style=style; cfg.subdomain_add_casino=True
    dashed={'online-casino-az-ru', 'casino-online-az', 'casinos-top-az'}
    joined={x.replace('-','') for x in dashed}
    expected=dashed if style=='hyphen' else joined if style=='joined' else dashed|joined
    generated=set()
    for _ in expected:
        name=next_subdomain(site,state,cfg,cfg.drop_domain)
        assert name==next_subdomain(site,state,cfg,cfg.drop_domain)
        generated.add(name.split('.')[0]); state['domains'].append(name)
    assert generated==expected
    with pytest.raises(ValueError,match='заняты'):
        next_subdomain(site,state,cfg,cfg.drop_domain)


def test_global_domain_rules_override_mass_and_preserve_personal():
    site,state,g,cfg=fixture()
    site.brand='Pinco'; site.domain_types={'clubheavenjax.com':'drop'}
    state['domains'].append('clubheavenjax.com'); site.cache_domains=list(state['domains'])
    g.apply_domain_settings=True
    g.domain_settings=auto.DomainOptions(create_subdomains=True,subdomain_name_style='hyphen',subdomain_add_casino=True)
    plan=auto.build_plan(site,state,g,cfg)
    assert plan['create_subdomain']=='pinco-az.clubheavenjax.com'
    assert not cfg.create_subdomains
    assert auto.effective_project_config(g,cfg).drop_domain==cfg.drop_domain
    cfg.scope='personal'
    assert auto.effective_project_config(g,cfg) is cfg
    assert auto.build_plan(site,state,g,cfg)['create_subdomain'] is None
    cfg.scope='mass';g.apply_domain_settings=False
    assert auto.build_plan(site,state,g,cfg)['create_subdomain'] is None


def test_global_domain_rules_saved_and_default_opt_out():
    _,sessions=make_client()
    with sessions() as db:
        assert not auto.config(db).apply_domain_settings
        value=auto.GlobalConfig(apply_domain_settings=True,domain_settings=auto.DomainOptions(parent_kind='newreg',create_subdomains=True,subdomain_name_style='joined'))
        auto.save_config(db,value)
        db.expire_all()
        saved=auto.config(db)
        assert saved.apply_domain_settings
        assert saved.domain_settings.parent_kind=='newreg'
        assert saved.domain_settings.create_subdomains
        assert saved.domain_settings.subdomain_name_style=='joined'


def test_auto_fake_main_waits_and_never_resends(monkeypatch):
    sessions,run_id,calls,state=setup_run(monkeypatch,'create_fake_main',fake=True)
    with sessions() as db:
        auto.execute(db,run_id);auto.execute(db,run_id)
        assert calls==['create_fake_main']
        run=db.get(models.AutoReglueRun,run_id)
        assert run.status=='waiting'
        receipt=str(uuid5(UUID(run_id),'create_fake_main'))
        db.get(models.NetworkOperation,receipt).status='confirmed';db.commit()
        auto.execute(db,run_id);auto.execute(db,run_id)
        assert calls==['create_fake_main','reserve','reglue','alternates']
        assert run.status=='completed'


def test_fake_page_then_subdomain_then_reglue(monkeypatch):
    sessions,run_id,calls,state=setup_run(monkeypatch,'create_subdomains',create=True,fake=True)
    with sessions() as db:
        auto.execute(db,run_id); auto.execute(db,run_id)
        assert calls==['create_fake_main','create_subdomains']
        run=db.get(models.AutoReglueRun,run_id)
        state['domains'].append(run.plan['create_subdomain'])
        receipt=str(uuid5(UUID(run_id),'create_subdomains'))
        db.get(models.NetworkOperation,receipt).status='confirmed';db.commit()
        auto.execute(db,run_id)
        assert calls==['create_fake_main','create_subdomains','reserve','reglue','alternates']
        assert run.status=='completed'


@pytest.mark.parametrize('scheme', ['preserve','add_auxiliary','base_only'])
def test_fake_disabled_uses_only_root_urls_even_with_old_template_paths(scheme):
    from app.network_state import alternate_links
    site,state,g,cfg=fixture()
    cfg.use_current_fake_main=False;cfg.create_fake_main=False;cfg.fake_main_path=''
    g.scheme_mode=scheme
    site.domain_types={'unused.test':'drop'};state['domains'].append('unused.test')
    plan=auto.build_plan(site,state,g,cfg)
    links=alternate_links(plan['alternateMarkup'])
    assert plan['create_fake_main_path'] is None
    assert plan['required_page_urls']==[]
    assert next(x['href'] for x in links if x['hreflang']=='az')==next(x['href'] for x in links if x['hreflang']=='az-AZ')
    assert all(x['href']=='https://'+x['domain']+'/' for x in links)


def test_new_fake_chooses_unused_path_each_iteration_and_current_stays_fixed():
    site,state,g,cfg=fixture()
    cfg.use_current_fake_main=False;cfg.create_fake_main=True
    state['content_page_paths']=['/az/','/az1/']
    first=auto.build_plan(site,state,g,cfg)
    assert first['create_fake_main_path']=='/az2/'
    state['fake_main_paths'].append('/az2/')
    second=auto.build_plan(site,state,g,cfg)
    assert second['create_fake_main_path']=='/az3/'
    cfg.create_fake_main=False;cfg.use_current_fake_main=True;cfg.fake_main_path='/ignored/'
    current=auto.build_plan(site,state,g,cfg)
    assert current['create_fake_main_path'] is None
    assert 'https://next.clubheavenjax.com/events/' in current['alternateMarkup']
    state['fake_main_enabled']=False
    with pytest.raises(ValueError,match='текущей фейковой'):
        auto.build_plan(site,state,g,cfg)


def test_fake_modes_mutually_exclusive():
    for cls in (auto.ProjectConfig,auto.DomainOptions):
        with pytest.raises(ValueError,match='один режим'):
            cls(create_fake_main=True,use_current_fake_main=True)


@pytest.mark.parametrize('brand', ['', 'Общие ключи', 'Pin-Up', 'Casino'])
def test_fake_path_templates_exhaustion_and_brand(brand):
    from app.fake_main import next_fake_path
    site, state, _, cfg = fixture()
    site.brand = brand; site.cache_geo = 'CZ'; site.cache_language = 'cs-CZ'
    state['fake_main_paths'] = []; state['content_page_paths'] = []; state['fake_main_current'] = ''
    expected = ['/cz/', *[f'/cz{i}/' for i in range(1, 11)], '/cz-cs/']
    if brand == 'Pin-Up':
        expected += ['/pinup-cz/', '/pinup-cs/', '/pinup-casino-cz/', '/pinup-casino-cs/']
    elif brand == 'Casino':
        expected += ['/casino-cz/', '/casino-cs/']
    for path in expected:
        assert next_fake_path(site, state, cfg) == path
        state['fake_main_paths'].append(path)
    with pytest.raises(ValueError, match='заняты'):
        next_fake_path(site, state, cfg)


def test_fake_path_skips_normalized_content_and_current_and_validates_metadata():
    from app.fake_main import next_fake_path
    site, state, _, cfg = fixture()
    state['content_page_paths'] = ['az', '/az1']
    state['fake_main_current'] = 'az2/'
    assert next_fake_path(site, state, cfg) == '/az3/'
    site.cache_geo = ''
    with pytest.raises(ValueError, match='GEO'):
        next_fake_path(site, state, cfg)


@pytest.mark.parametrize('rules', [dict(create_fake_main=True), dict(interval_days=7), dict(scheme_mode='base_only'), dict(profile_id='custom')])
def test_saved_own_rules_auto_exclude_even_disabled(monkeypatch, rules):
    from app import auto_reglue_api
    monkeypatch.setattr(auto_reglue_api, "kick_due_schedule", lambda db: None)
    from app.auto_reglue_api import router
    client, sessions = make_client()
    client.app.include_router(router, prefix='/api')
    with sessions() as db:
        site = db.scalar(select(models.Site)); site.project_status = 'mass_actions'; db.commit(); site_id = site.id
    payload = auto.ProjectConfig(drop_domain='drop.test', language='az', schedule_enabled=True, **rules).model_dump()
    result = client.put(f'/api/auto-reglue/projects/{site_id}', json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['scope'] == 'personal'
    assert not result.json()['enabled'] and result.json()['schedule_enabled']
    assert client.get('/api/auto-reglue').json()['projects'] == []
    denied = client.post('/api/auto-reglue/start', json={'items':[{'site_id':site_id, 'request_id':str(uuid4()), 'preview_token':'a'*64}]})
    assert 'персональные' in denied.json()['results'][0]['error']
    with sessions() as db:
        auto.save_config(db, auto.GlobalConfig(enabled=True, schedule_enabled=True))
        site = db.get(models.Site, site_id)
        assert auto.next_scheduled_at(db, site) is None
    # Clearing rules and explicitly returning to mass is required.
    reset = auto.ProjectConfig(drop_domain='drop.test', language='az').model_dump()
    assert client.put(f'/api/auto-reglue/projects/{site_id}', json=reset).json()['scope'] == 'mass'
    assert len(client.get('/api/auto-reglue').json()['projects']) == 1


def test_project_addresses_and_language_do_not_create_personal_rules():
    cfg = auto.ProjectConfig(enabled=True, drop_domain='drop.test', newreg_domain='new.test', x_default_newreg_domain='default.test', language='az')
    assert auto.saved_project_rules(cfg).scope == 'mass'
    cfg.scope = 'personal'
    assert auto.saved_project_rules(cfg).scope == 'mass'
    cfg.schedule_enabled = True
    assert auto.saved_project_rules(cfg).scope == 'personal'


@pytest.mark.parametrize('status,listed', [('mass_actions', True), ('working', False)])
def test_disabling_personal_schedule_returns_to_mass_and_keeps_rules(monkeypatch, status, listed):
    from app import auto_reglue_api
    monkeypatch.setattr(auto_reglue_api, 'kick_due_schedule', lambda db: None)
    client, sessions = make_client(); client.app.include_router(auto_reglue_api.router, prefix='/api')
    with sessions() as db:
        site = db.scalar(select(models.Site)); site.project_status = status; db.commit(); site_id = site.id
        auto.save_config(db, auto.GlobalConfig(enabled=True, schedule_enabled=True, interval_days=3))
    payload = auto.ProjectConfig(enabled=True, schedule_enabled=True, interval_days=14, drop_domain='drop.test', language='az', create_fake_main=True).model_dump()
    saved = client.put(f'/api/auto-reglue/projects/{site_id}', json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()['scope'] == 'personal'
    assert client.get('/api/auto-reglue').json()['projects'] == []
    payload = saved.json(); payload['schedule_enabled'] = False
    saved = client.put(f'/api/auto-reglue/projects/{site_id}', json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()['scope'] == 'mass'
    assert saved.json()['interval_days'] == 14 and saved.json()['create_fake_main']
    assert bool(client.get('/api/auto-reglue').json()['projects']) == listed
    with sessions() as db:
        cfg = auto.config(db, site_id); site = db.get(models.Site, site_id)
        assert auto.schedule_eligible(site, auto.config(db), cfg) == listed
        assert auto.effective_config(auto.config(db), cfg).interval_days == 3
    payload = saved.json(); payload['schedule_enabled'] = True
    assert client.put(f'/api/auto-reglue/projects/{site_id}', json=payload).json()['scope'] == 'personal'
    assert client.get('/api/auto-reglue').json()['projects'] == []


def test_mass_status_is_permission_without_project_enabled_or_saved_config():
    _, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site)); site.project_status = 'mass_actions'; db.commit()
        g = auto.GlobalConfig(enabled=True, schedule_enabled=True)
        auto.save_config(db, g)
        cfg = auto.config(db, site.id)
        assert not cfg.enabled
        auto.require_eligible(site, g, cfg)
        assert auto.schedule_eligible(site, g, cfg)
        assert auto.next_scheduled_at(db, site) is not None
        site.project_status = 'working'
        db.flush()
        from datetime import datetime, timezone
        auto.sync_schedules(db, datetime.now(timezone.utc))
        assert not db.get(models.AutoReglueSchedule, site.id).enabled
        assert not auto.schedule_eligible(site, g, cfg)
        with pytest.raises(ValueError, match='Массовые действия'):
            auto.require_eligible(site, g, cfg)


def test_explicit_project_launch_ignores_global_rules_and_does_not_enable_schedule(monkeypatch):
    sessions, old_run_id, calls, state = setup_run(monkeypatch)
    with sessions() as db:
        old = db.get(models.AutoReglueRun, old_run_id); old.status = 'cancelled'
        site = db.get(models.Site, old.site_id); site.project_status = 'working'; db.commit()
        cfg = auto.config(db, site.id); cfg.enabled = False; cfg.schedule_enabled = False; cfg.scheme_mode = 'preserve'
        auto.save_config(db, cfg, site.id)
        g = auto.GlobalConfig(enabled=False, apply_domain_settings=True, scheme_mode='base_only', domain_settings=auto.DomainOptions(domain_layout='root_main', create_subdomains=True))
        auto.save_config(db, g)
        plan = auto.preview(db, site, 'project')
        assert plan['launch_scope'] == 'project' and plan['scope'] == 'personal'
        assert plan['scheme_mode'] == 'preserve' and plan['domain_layout'] == 'subdomain_main'
        assert plan['create_subdomain'] is None
        g.scheme_mode = 'add_auxiliary'; auto.save_config(db, g)
        assert auto.preview(db, site, 'project')['preview_token'] == plan['preview_token']
        run, fresh = auto.prepare_run(db, site, uuid4(), plan['preview_token'], 'admin', 'project')
        assert fresh
        auto.execute(db, run.id)
        assert db.get(models.AutoReglueRun, run.id).status == 'completed'
        assert auto.config(db, site.id) == cfg
        assert auto.next_scheduled_at(db, site) is None
    assert calls == ['reserve', 'reglue', 'alternates']


def test_project_preview_cannot_be_used_for_mass_launch(monkeypatch):
    sessions, run_id, _, _ = setup_run(monkeypatch)
    with sessions() as db:
        run = db.get(models.AutoReglueRun, run_id); run.status = 'cancelled'; db.commit()
        site = db.get(models.Site, run.site_id)
        plan = auto.preview(db, site, 'project')
        with pytest.raises(auto.project_network.NetworkConflict, match='предпросмотра'):
            auto.prepare_run(db, site, uuid4(), plan['preview_token'], 'admin', 'mass')


def test_auto_indexing_only_after_alternates_confirmed_and_once(monkeypatch):
    sessions, run_id, calls, state = setup_run(monkeypatch, 'alternates')
    with sessions() as db:
        auto.execute(db, run_id)
        assert not db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.action == 'indexing')).all()
        operation = db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.action == 'alternates'))
        operation.status = 'confirmed'; db.commit()
        state['amp_domains'] = ['mobile.test']; state['domains'].append('mobile.test')
        auto.execute(db, run_id); auto.execute(db, run_id)
        queued = db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.action == 'indexing')).all()
        assert len(queued) == 1
        assert 'https://mobile.test/' not in queued[0].request_payload['domains']
        assert queued[0].status == 'index_queued'
        assert db.get(models.AutoReglueRun, run_id).status == 'completed'


def test_saved_schedule_exposes_task_link_and_personal_task_in_global_view(monkeypatch):
    from app import auto_reglue_api
    monkeypatch.setattr(auto_reglue_api, 'kick_due_schedule', lambda db: None)
    client, sessions = make_client(); client.app.include_router(auto_reglue_api.router, prefix='/api')
    with sessions() as db:
        site = db.scalar(select(models.Site)); site_id = site.id
    assert client.get(f'/api/auto-reglue/projects/{site_id}').json()['task'] is None
    saved = client.put(f'/api/auto-reglue/projects/{site_id}', json=auto.ProjectConfig(enabled=True, schedule_enabled=True, drop_domain='drop.test', language='az').model_dump())
    assert saved.status_code == 200
    task = client.get(f'/api/auto-reglue/projects/{site_id}').json()['task']
    assert task['scope'] == 'personal' and task['enabled']
    assert task['url'] == f'/auto-reglue?project_id={site_id}#auto-task-{site_id}'
    overview = client.get(f'/api/auto-reglue?project_id={site_id}').json()
    assert overview['tasks'] == [task]
    assert overview['projects'] == []  # Listing a task never admits it to mass runs.
