from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app import models, background_jobs
from app.auto_reglue_api import router
from app.mass_action_scope import MassActionFilter, constrain, matches
from test_project_pages import setup


def add(db, name, brand='Brand', geo='PL', kind='monobrand', **kwargs):
    site = models.Site(name=name, base_url='https://' + name, publication_endpoint='/', brand=brand,
                       cache_geo=geo, site_type=kind, project_status=kwargs.pop('status', 'mass_actions'), **kwargs)
    db.add(site); db.commit()
    return site


def test_filter_requires_brand_and_geo_and_limits_content_before_queuing(setup):
    client, db, site, state = setup
    client.app.include_router(router)
    site.cache_geo='PL'; site.project_status='mass_actions'; db.commit()
    others = [add(db,'other.cz',geo='CZ'), add(db,'other.pl',brand='Other'),
              add(db,'generic.pl',brand='Общие ключи',kind='general'), add(db,'inactive.pl',status='working')]
    body={'request_id':str(uuid4()),'action':'trim_99','site_ids':[site.id]}
    assert client.post('/auto-reglue/content-drafts',json=body).status_code==422
    body['filter']={'brand':'Brand','geo':'PL'}
    for other in others:
        assert client.post('/auto-reglue/content-drafts',json={**body,'site_ids':[site.id,other.id]}).status_code==400
    assert db.scalar(select(func.count()).select_from(models.BackgroundJob))==0
    response=client.post('/auto-reglue/content-drafts',json=body)
    assert response.status_code==200,response.text
    assert [r['site_id'] for r in response.json()['results']]==[site.id]
    assert not state['requests'] and not state['backup_requests']


def test_general_is_opt_in_and_only_in_same_geo(setup):
    _, db, site, _ = setup
    site.cache_geo='PL';site.project_status='mass_actions';db.commit()
    general=add(db,'generic.pl',brand='Other',kind='general')
    foreign=add(db,'generic.cz',brand='Общие ключи',geo='CZ',kind='general')
    filters=MassActionFilter(brand='Brand',geo='pl-PL')
    assert matches(site,filters) and not matches(general,filters)
    filters.include_general=True
    assert matches(general,filters) and not matches(foreign,filters)
    assert constrain(db,filters,None,[site,general])=={site.id,general.id}
    assert constrain(db,filters,{site.id},[site])=={site.id}
    with pytest.raises(ValueError):constrain(db,filters,{site.id},[general])


def test_worker_rechecks_scope_before_backup_or_trimming(setup):
    client,db,site,state=setup
    client.app.include_router(router)
    site.project_status='mass_actions';site.cache_geo='PL';db.commit()
    response=client.post('/auto-reglue/content-drafts',json={'request_id':str(uuid4()),'site_ids':[site.id],
        'action':'trim_50','filter':{'brand':'Brand','geo':'PL'}})
    assert response.status_code==200
    job=db.scalar(select(models.BackgroundJob))
    site.cache_geo='CZ';db.commit()
    assert background_jobs.run_job(db,job.id)['status']=='failed'
    draft=db.get(models.ProjectPageDraft,job.payload['draft_id'])
    assert 'фильтру' in draft.error and draft.result_content is None
    assert not state['backup_requests'] and not state['requests']


def test_global_schedule_needs_saved_filter_but_personal_schedule_is_independent(setup):
    from app import auto_reglue as auto
    _,db,site,_=setup
    site.project_status='mass_actions';site.cache_geo='PL';db.commit()
    cfg=auto.ProjectConfig(enabled=True)
    global_cfg=auto.GlobalConfig(enabled=True,schedule_enabled=True)
    assert not auto.schedule_eligible(site,global_cfg,cfg)
    global_cfg.selection_filter=MassActionFilter(brand='Brand',geo='CZ')
    assert not auto.schedule_eligible(site,global_cfg,cfg)
    global_cfg.selection_filter.geo='PL'
    assert auto.schedule_eligible(site,global_cfg,cfg)
    cfg.scope='personal';cfg.schedule_enabled=True
    global_cfg.selection_filter=None
    assert auto.schedule_eligible(site,global_cfg,cfg)


def test_unset_filter_keeps_legacy_configuration_fingerprint_compatible():
    from app import auto_reglue as auto
    config=auto.GlobalConfig()
    assert config.selection_filter is None
    assert 'selection_filter' not in config.model_dump()
    config.selection_filter=MassActionFilter(brand='Brand',geo='PL')
    assert config.model_dump()['selection_filter']['geo']=='PL'
