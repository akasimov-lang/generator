from copy import deepcopy
from uuid import uuid4

from app import models
from app.reglue_combinations import History, identity, settings
from app import pilot_schemes
from test_project_network import env


def plan(site_id, **changes):
    return {'site_id': site_id, 'brand': 'Pinco', 'geo': 'PL', 'language': 'pl',
            'new_main': 'new.test', 'old_main': 'old.test', 'domain_type': 'newreg',
            'fake_main_path': '/offer/', 'create_fake_main_path': '/offer/',
            'canonical_mode': 'self', 'canonicalFakeMainMarkup': '<link rel="canonical" href="https://{{settings.canon}}/" />',
            'alternateMarkup': '<link rel="alternate" hreflang="pl" href="https://new.test/offer/" />', **changes}


def completed(db, value, status='completed'):
    run = models.AutoReglueRun(id=str(uuid4()), site_id=value['site_id'], initiator='test', status=status, plan=deepcopy(value))
    db.add(run); db.commit()
    return run


def test_identity_ignores_domain_and_generated_path_but_tracks_settings():
    a = plan('a')
    b = plan('b', new_main='different.test', fake_main_path='/welcome/', create_fake_main_path='/welcome/',
             alternateMarkup='<link rel="alternate" hreflang="pl" href="https://different.test/welcome/" />')
    assert identity(a) == identity(b)
    assert identity(a) != identity({**a, 'redirect_old_main': True})
    assert identity(a) != identity({**a, 'rewrite_title_h1': True, 'title_rewrite_mode': 'full'})
    assert identity(a) != identity({**a, 'create_fake_main_path': None})


def test_failed_and_drafts_are_not_tested_history(env):
    db, site, _ = env
    a = plan(site.id)
    completed(db, a, 'failed'); completed(db, a, 'planned')
    history = History(db, [a]); history.stamp(a)
    assert a['combination_history']['brand_geo_completed'] == 0
    assert a['combination_history']['project_completed'] == 0
    assert a['combination_history']['planned_in_group'] == 1


def test_history_is_scoped_to_brand_geo_and_keeps_project_history(env):
    db, site, _ = env
    a = plan(site.id); run = completed(db, a)
    history = History(db)
    history.stamp(a)
    assert a['combination_history']['brand_geo_completed'] == 1
    assert a['combination_history']['project_completed'] == 1
    assert a['combination_history']['last_completed']['run_id'] == run.id
    other_geo = plan(site.id, geo='CZ')
    history.stamp(other_geo)
    assert other_geo['combination_history']['brand_geo_completed'] == 0
    assert other_geo['combination_history']['project_completed'] == 1


def test_untried_combination_wins_and_saved_plan_is_immutable(env):
    db, site, _ = env
    site.brand='Pinco'; site.cache_geo='PL'; site.cache_language='pl'; db.commit()
    a=plan(site.id); pilot_schemes.assign(db, [a]); saved=deepcopy(a)
    completed(db, a)
    b=plan(site.id); pilot_schemes.assign(db, [b])
    assert b['combination_id'] != a['combination_id']
    assert b['combination_history']['brand_geo_completed'] == 0
    assert a == saved
    assert identity(b) == b['combination_id']


def test_parent_final_placement_is_in_identity_and_deduplicated(env):
    db, site, _ = env
    site.brand='Pinco'; site.cache_geo='PL'; site.cache_language='pl'; db.commit()
    a=plan(site.id, new_main='pl.new.test', parent_domain='new.test')
    pilot_schemes.assign(db, [a])
    assert a['combination_id'] == identity(a)
    assert a['combination_history']['compatible_variants'] < len(pilot_schemes.CATALOGUE) // 2
    b=deepcopy(a)
    pilot_schemes.apply_parent_x_default(b, use_internal=not(a['x_default_parent_path'] != '/'))
    assert identity(a) != identity(b)


def test_explicit_template_does_not_get_overwritten(env):
    db, site, _ = env
    a=plan(site.id, planning_options={'profile_id':'chosen-template'})
    before=a['alternateMarkup']
    pilot_schemes.assign(db, [a])
    assert a['alternateMarkup'] == before
    assert a['combination_id'] == identity(a)


def test_new_mass_plan_replay_keeps_exact_combination_metadata(env, monkeypatch):
    from app import auto_reglue as auto, canonical_allocation
    from test_auto_reglue import prepare_fake_run
    db, site, _ = env
    run = prepare_fake_run(env, monkeypatch)
    reviewed=deepcopy(run.plan)
    with canonical_allocation.replay(db, reviewed):
        actual=auto.preview(db, site)
    assert {k:v for k,v in actual.items() if k != 'preview_token'} == {k:v for k,v in reviewed.items() if k != 'preview_token'}
    assert actual['preview_token'] == reviewed['preview_token']


def test_all_compatible_variants_are_used_before_repeating_for_brand_geo(env):
    db, site, _ = env
    site.brand='Pinco'; site.cache_geo='PL'; site.cache_language='pl'; db.commit()
    first=plan(site.id); pilot_schemes.assign(db,[first])
    count=first['combination_history']['compatible_variants']; seen=set()
    for index in range(count):
        value=plan(site.id); pilot_schemes.assign(db,[value])
        assert value['combination_id'] not in seen
        assert value['combination_history']['brand_geo_completed'] == 0
        seen.add(value['combination_id']); completed(db,value)
    repeated=plan(site.id); pilot_schemes.assign(db,[repeated])
    assert repeated['combination_history']['brand_geo_completed'] == 1


def test_fixed_batch_reduces_duplicates_without_counting_as_tested(env):
    db, site, _ = env
    site.brand='Pinco'; site.cache_geo='PL'; site.cache_language='pl'; db.commit()
    first=plan(site.id); pilot_schemes.assign(db,[first])
    fixed={**first,'site_id':'another-project'}
    value=plan(site.id); pilot_schemes.assign(db,[value],fixed=[fixed])
    assert value['combination_id'] != first['combination_id']
    assert value['combination_history']['brand_geo_completed'] == 0


def test_renderer_preserves_configured_hosts_and_auxiliary_roles():
    value=plan('a',language_domain='pl.new.test',x_default_domain='drop.test',scheme_mode='add_auxiliary',
               alternateMarkup='<link rel="alternate" hreflang="de" href="https://pl.new.test/" />')
    chosen=next(c for c in pilot_schemes.CATALOGUE if c['canonical']=='self' and c['links']==('lang','locale','x-default') and c['fake_on']=='lang')
    pilot_schemes.render(value,chosen,'','pl','PL')
    from app.network_state import alternate_links
    links={l['hreflang']:l['href'] for l in alternate_links(value['alternateMarkup'])}
    assert links == {'de':'https://pl.new.test/','pl':'https://pl.new.test/offer/','pl-PL':'https://pl.new.test/','x-default':'https://drop.test/'}


def test_effective_project_naming_options_reach_mass_subdomain_selection(env,monkeypatch):
    from app import auto_reglue as auto, mass_main_targets as targets
    db,site,_=env
    site.cache_geo='PL';site.cache_language='pl';site.brand='Pinco';site.domain_types={'new.test':'newreg'};db.commit()
    auto.save_config(db, auto.ProjectConfig(subdomain_name_style='hyphen', subdomain_add_casino=True), site.id)
    observed=[]
    def name(site,state,options,parent,**kwargs):
        observed.append((options.subdomain_name_style,options.subdomain_add_casino))
        return 'pinco-casino.'+parent
    monkeypatch.setattr(targets,'next_subdomain',name)
    monkeypatch.setattr(targets,'banned_domains',lambda db,site,domains:{d:False for d in domains})
    from app import cross_reglue
    monkeypatch.setattr(cross_reglue,'unique_membership',lambda *args:None)
    state={'domains':['new.test'],'canon':'old.test'}
    targets.subdomain_candidate(db,site,state,'sub_newreg',auto.GlobalConfig())
    assert observed[-1] == ('hyphen',True)
    cfg=auto.GlobalConfig(apply_domain_settings=True,domain_settings=auto.DomainOptions(subdomain_name_style='joined',subdomain_add_casino=False))
    targets.subdomain_candidate(db,site,state,'sub_newreg',cfg)
    assert observed[-1] == ('joined',False)
