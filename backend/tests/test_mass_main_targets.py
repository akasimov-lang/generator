from collections import Counter
from uuid import uuid4
import pytest
from app import auto_reglue as auto, cross_reglue as cross, cross_reglue_batch as batch, project_network as network, models
from app.mass_main_targets import quotas
from app.domain_transfer_policy import set_ban
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, reserve, finish


def rules(db, mode='mixed', **extra):
    cfg=auto.GlobalConfig(enabled=True,execution_mode='cross_network',main_target_mode=mode,**extra)
    auto.save_config(db,cfg)
    return cfg


@pytest.mark.parametrize('n,expected',[(0,(0,0,0,0)),(4,(2,2,0,0)),(5,(2,1,1,1)),(15,(6,5,2,2)),(16,(6,6,2,2)),(25,(10,9,3,3)),(100,(40,40,10,10))])
def test_math_rounding_and_percentages_of_whole_cycle(n,expected):
    cfg=auto.GlobalConfig(main_target_mode='mixed',newreg_subdomain_share=True,drop_subdomain_share=True)
    result=quotas(n,cfg)
    assert tuple(result.values())==expected and sum(result.values())==n


def test_legacy_config_digest_is_unchanged():
    values=auto.GlobalConfig().model_dump()
    assert 'main_target_mode' not in values and 'newreg_subdomain_share' not in values and 'drop_subdomain_share' not in values
    with pytest.raises(ValueError):auto.GlobalConfig(main_target_mode='newreg',drop_subdomain_share=True)
    with pytest.raises(ValueError):auto.GlobalConfig(main_target_mode='drop',newreg_subdomain_share=True)


def make_pool(pool, count=16):
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    donors=[]
    for kind in ['newreg','drop']:
        donor=add('donor-'+kind+'.test',40,20)
        donor.domain_types={d:kind for d in donor.domain_types};db.commit();donors.append(donor)
    recipients=[add(f'project-{i}.test',3) for i in range(count)]
    for i,site in enumerate(recipients):
        parent=f'parent-{i}.test';remotes[site.id].data['settings']['domains'].append(parent)
        site.domain_types={parent:'newreg' if i%2==0 else 'drop'};site.cache_language='az';db.commit()
    return db,remotes,donors,recipients


def test_mixed_cycle_has_6_6_2_2_and_no_webdev_writes(pool):
    db,remotes,donors,recipients=make_pool(pool)
    rules(db,newreg_subdomain_share=True,drop_subdomain_share=True)
    preview=batch.build(db,recipients,'test')
    assert not preview['skipped'],preview['skipped']
    assert Counter(p['main_target_kind'] for p in preview['plans'])=={'newreg':6,'drop':6,'sub_newreg':2,'sub_drop':2}
    assert preview['distribution']['fallbacks']==0
    assert all(not r.calls for r in remotes.values())
    assert len({p['new_main'] for p in preview['plans']})==16
    assert all(p.get('parent_domain') not in {q['new_main'] for q in preview['plans'] if not q.get('local_target')} for p in preview['plans'])


def test_newreg_and_drop_modes_choose_exact_type_and_execute_drop(pool):
    db,source,target,remotes,add=pool
    remotes[source.id].data['settings']['domains'].append('drop.test')
    source.domain_types={**source.domain_types,'drop.test':'drop'};db.commit()
    rules(db,'drop')
    preview=batch.build(db,[target],'test');plan=preview['plans'][0]
    assert plan['new_main']=='drop.test' and plan['main_target_kind']=='drop' and not plan['target_fallback']
    runs=reserve(db,preview);finish(db,runs)
    assert remotes[target.id].data['settings']['canon']=='drop.test'
    assert target.domain_types['drop.test']=='drop'


def test_missing_drop_falls_back_to_newreg_from_larger_network(pool):
    db,source,target,remotes,add=pool
    rules(db,'drop')
    result=batch.build(db,[target],'test');plan=result['plans'][0]
    assert plan['new_main']=='next.test' and plan['target_fallback'] and plan['requested_target_kind']=='drop'
    assert plan['main_target_kind']=='newreg' and result['distribution']['fallbacks']==1
    runs=reserve(db,result);finish(db,runs)


def test_fallback_uses_available_smaller_donor_but_excludes_foreign_networks(pool):
    db,source,target,remotes,add=pool
    remotes[target.id].data['settings']['domains']+=['filler.target.test']*4
    add('wrong-brand.test',20,10,brand='Other');add('wrong-geo.test',20,10,geo='PL')
    rules(db,'drop')
    result=batch.build(db,[target],'test')
    assert len(result['plans'])==1 and not result['skipped']
    assert result['plans'][0]['source_site_id']==source.id
    assert all(not r.calls for r in remotes.values())


def test_type_change_after_preview_stops_before_any_extraction(pool):
    db,source,target,remotes,add=pool
    rules(db,'newreg');preview=batch.build(db,[target],'test')
    source.domain_types={**source.domain_types,'next.test':'drop'};db.commit()
    with pytest.raises(ValueError,match='Тип'):reserve(db,preview)
    assert all(not r.calls for r in remotes.values())


def test_subdomain_slots_use_local_parent_then_execute_without_extracting_it(pool):
    db,remotes,donors,recipients=make_pool(pool,5)
    rules(db,newreg_subdomain_share=True,drop_subdomain_share=True)
    result=batch.build(db,recipients,'test');runs=reserve(db,result)
    finish(db,runs)
    assert Counter(p['main_target_kind'] for p in result['plans'])=={'newreg':2,'drop':1,'sub_newreg':1,'sub_drop':1}
    for run in runs:
        if not run.plan.get('local_target'):continue
        assert run.plan['parent_domain'] in remotes[run.site_id].data['settings']['domains']
        assert run.plan['new_main']==remotes[run.site_id].data['settings']['canon']
        assert sum(path=='/site-config/create' for path,_ in remotes[run.site_id].calls)==1
        assert not any(path=='/site-config/delete' for path,_ in remotes[run.site_id].calls)
    before=sum(len(r.calls) for r in remotes.values());finish(db,runs)
    assert before==sum(len(r.calls) for r in remotes.values())


def test_unavailable_subdomain_slot_falls_back_to_larger_newreg(pool):
    db,remotes,donors,recipients=make_pool(pool,5)
    for site in recipients:site.domain_types={};db.commit()
    rules(db,'newreg',newreg_subdomain_share=True)
    result=batch.build(db,recipients,'test')
    assert len(result['plans'])==5 and result['distribution']['fallbacks']==1
    assert all(p['main_target_kind']=='newreg' for p in result['plans'])
    assert sum(p['requested_target_kind']=='sub_newreg' for p in result['plans'])==1


@pytest.mark.parametrize('mode',['legacy','mixed','drop'])
def test_banned_selected_reserve_imports_newreg_even_from_smaller_network(pool,mode):
    db,source,target,remotes,add=pool
    remotes[target.id].data['settings'].update(domains=['target.test','bad.test','padding.target.test','padding2.target.test'],reserve='bad.test',reserveOption='bad.test')
    target.domain_types={'bad.test':'drop'};db.commit();set_ban(db,target,'bad.test',True,'test')
    rules(db,mode)
    preview=batch.build(db,[target],'test');assert not preview['skipped'],preview['skipped']
    plan=preview['plans'][0]
    assert plan['new_main']=='next.test' and plan['replace_banned_reserve']=='bad.test'
    assert plan['balance_mode']=='banned_reserve_fallback'
    runs=reserve(db,preview);finish(db,runs)
    assert remotes[target.id].data['settings']['canon']=='next.test'


def test_banned_reserve_flag_rechecked_after_preview(pool):
    db,source,target,remotes,add=pool
    remotes[target.id].data['settings'].update(domains=['target.test','bad.test'],reserve='bad.test')
    target.domain_types={'bad.test':'drop'};db.commit();set_ban(db,target,'bad.test',True,'test')
    preview=batch.build(db,[target],'test')
    set_ban(db,target,'bad.test',False,'test')
    with pytest.raises(ValueError,match='БАН'):reserve(db,preview)
    assert all(not r.calls for r in remotes.values())


def test_single_preview_and_durable_launch_use_same_typed_policy(pool):
    db,source,target,remotes,add=pool
    rules(db,'drop')
    plan=auto.preview(db,target)
    run,_=auto.prepare_run(db,target,uuid4(),plan['preview_token'],'test','mass')
    auto.execute(db,run.id)
    assert run.status=='completed',run.message


def test_banned_reserve_changed_after_queue_stops_before_write(pool):
    db,source,target,remotes,add=pool
    remotes[target.id].data['settings'].update(domains=['target.test','bad.test'],reserve='bad.test')
    target.domain_types={'bad.test':'drop'};db.commit();set_ban(db,target,'bad.test',True,'test')
    run=reserve(db,batch.build(db,[target],'test'))[0]
    set_ban(db,target,'bad.test',False,'test')
    auto.execute(db,run.id)
    assert run.status=='failed' and 'БАН' in run.message
    assert all(not r.calls for r in remotes.values())


def test_missing_banned_reserve_fallback_does_not_touch_other_geo(pool):
    db,source,target,remotes,add=pool
    source.cache_geo='PL'
    remotes[target.id].data['settings'].update(domains=['target.test','bad.test'],reserve='bad.test')
    target.domain_types={'bad.test':'drop'};db.commit();set_ban(db,target,'bad.test',True,'test')
    preview=batch.build(db,[target],'test')
    assert not preview['plans'] and preview['skipped']
    assert all(not r.calls for r in remotes.values())


def test_subdomain_waits_for_job_without_repeating_create(pool):
    db,remotes,donors,recipients=make_pool(pool,5)
    rules(db,'newreg',newreg_subdomain_share=True)
    result=batch.build(db,recipients,'test');runs=reserve(db,result)
    local=next(run for run in runs if run.plan.get('local_target'))
    remote=remotes[local.site_id];old=remote.data['settings']['canon'];remote.job_ready=False
    auto.execute(db,local.id)
    assert local.status=='waiting' and remote.data['settings']['canon']==old
    auto.execute(db,local.id)
    assert sum(path=='/site-config/create' for path,_ in remote.calls)==1
    remote.job_ready=True;finish(db,runs)
    assert local.status=='completed'
    assert sum(path=='/site-config/create' for path,_ in remote.calls)==1


def test_parent_ban_after_preview_prevents_subdomain_creation(pool):
    db,remotes,donors,recipients=make_pool(pool,5)
    rules(db,'newreg',newreg_subdomain_share=True)
    result=batch.build(db,recipients,'test')
    entry=next(plan for plan in result['plans'] if plan.get('local_target'))
    site=next(site for site in recipients if site.id==entry['site_id'])
    set_ban(db,site,entry['parent_domain'],True,'test')
    with pytest.raises(ValueError,match='БАН'):reserve(db,result)
    assert all(not r.calls for r in remotes.values())


def test_policy_persists_without_becoming_personal_or_changing_schedule(pool):
    db,*_=pool
    cfg=rules(db,newreg_subdomain_share=True,drop_subdomain_share=True)
    current=auto.config(db)
    assert current.model_dump()==cfg.model_dump()
    assert not current.schedule_enabled
    assert current.main_target_mode=='mixed' and current.newreg_subdomain_share and current.drop_subdomain_share
