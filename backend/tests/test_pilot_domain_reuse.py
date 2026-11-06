from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from app import models, project_network as network, auto_reglue as auto
from app import pilot_domain_reuse as reuse
from app.domain_transfer_policy import require_transfer_allowed, require_main_destination, policy_key
from test_project_network import env
from test_cross_reglue import setup


def historical(db,site,domain,at):
    site.main_domain_history=list(dict.fromkeys([*(site.main_domain_history or []),domain]))
    site.network_state={**(site.network_state or {}),'cache_change_history':[{'id':str(uuid4()),'kind':'reglue','old_main':domain,'new_main':site.cache_canon,'at':at.isoformat()}]}
    db.commit()


def test_former_main_boundary_uses_departure_not_membership_date(env):
    db,site,_=env;now=datetime.now(timezone.utc);at=now-timedelta(days=14)
    historical(db,site,'retired.test',at)
    assert reuse.release_evidence(db,'retired.test',now)['ended_at']==at.isoformat()
    with pytest.raises(ValueError,match='14 дней'):
        reuse.release_evidence(db,'retired.test',now-timedelta(seconds=1))


def test_unknown_departure_is_not_assumed_old(env):
    db,site,_=env;site.main_domain_history=['retired.test'];db.commit()
    with pytest.raises(ValueError,match='Не подтверждена дата'):
        reuse.release_evidence(db,'retired.test')


def test_current_main_cannot_be_reused_even_with_old_departure(env):
    db,site,_=env;historical(db,site,site.cache_canon,datetime.now(timezone.utc)-timedelta(days=50))
    with pytest.raises(ValueError,match='сейчас является Main'):
        reuse.release_evidence(db,site.cache_canon)


def test_recent_return_to_main_restarts_fourteen_days(env):
    db,site,_=env;now=datetime.now(timezone.utc);historical(db,site,'retired.test',now-timedelta(days=50))
    site.network_state={**site.network_state,'cache_change_history':[*site.network_state['cache_change_history'],
        {'kind':'reglue','old_main':site.cache_canon,'new_main':'retired.test','at':(now-timedelta(days=5)).isoformat()},
        {'kind':'reglue','old_main':'retired.test','new_main':site.cache_canon,'at':(now-timedelta(days=2)).isoformat()}]};db.commit()
    with pytest.raises(ValueError,match='14 дней'):
        reuse.release_evidence(db,'retired.test')


def test_fresh_domain_membership_does_not_block_transfer_within_brand_geo(setup):
    db,source,target,sr,tr=setup
    network.read_network(db,source)
    source.network_state={**source.network_state,'domain_added_at':{'next.test':datetime.now(timezone.utc).isoformat()}}
    from app.domain_transfer_policy import record_transfer_cooldown
    record_transfer_cooldown(db,'next.test',datetime.now(timezone.utc).isoformat(),None);db.commit()
    require_transfer_allowed(db,source,'next.test')
    from app.cross_reglue import require_pair
    require_pair(source,target)
    assert sr.calls==tr.calls==[]


def test_unknown_membership_date_allows_unused_donor_within_same_brand_geo(setup):
    db,source,target,sr,tr=setup
    states={s.id:network.read_network(db,s) for s in (source,target)}
    source.network_state={**source.network_state,'domain_added_at':{'next.test':None}}
    db.commit()
    require_transfer_allowed(db,source,'next.test')
    plan=reuse.candidate(db,auto.config(db),target,states,{s.id:s for s in (source,target)},set())
    assert plan['new_main']=='next.test' and plan['source_site_id']==source.id
    assert not plan.get('former_main') and not plan.get('reserve_pool_id')
    assert sr.calls==tr.calls==[]


def test_unknown_membership_does_not_allow_foreign_geo_donor(setup):
    db,source,target,sr,tr=setup
    states={s.id:network.read_network(db,s) for s in (source,target)}
    source.cache_geo='DE';source.network_state={**source.network_state,'domain_added_at':{}};db.commit()
    with pytest.raises(ValueError,match='Нет подходящего домена'):
        reuse.candidate(db,auto.config(db),target,states,{s.id:s for s in (source,target)},set())
    assert sr.calls==tr.calls==[]


def test_unknown_membership_does_not_shorten_former_main_wait(setup):
    db,source,target,sr,tr=setup
    states={s.id:network.read_network(db,s) for s in (source,target)}
    historical(db,source,'next.test',datetime.now(timezone.utc)-timedelta(days=13))
    source.network_state={**source.network_state,'domain_added_at':{}};db.commit()
    with pytest.raises(ValueError,match='14 дней'):
        reuse.candidate(db,auto.config(db),target,states,{s.id:s for s in (source,target)},set())
    assert sr.calls==tr.calls==[]


def test_own_unused_drop_precedes_newreg_and_never_uses_stock(setup):
    db,source,target,sr,tr=setup
    target.domain_types={'spare-new.test':'newreg','spare-drop.test':'drop'}
    tr.data['settings']['domains']+=['spare-new.test','spare-drop.test'];db.commit()
    state=network.read_network(db,target)
    plan=reuse.candidate(db,auto.config(db),target,{target.id:state},{target.id:target},set())
    assert plan['new_main']=='spare-drop.test' and plan['local_target']
    assert not plan.get('reserve_pool_id') and not sr.calls and not tr.calls


def test_cross_network_former_main_is_scoped_and_history_remains(setup):
    db,source,target,sr,tr=setup
    source.cache_canon='main.test';target.cache_canon='target.test'
    network.read_network(db,source);network.read_network(db,target)
    historical(db,source,'next.test',datetime.now(timezone.utc)-timedelta(days=20))
    db.add(models.AutoReglueConfig(key=policy_key('next.test'),value={'domain':'next.test','main_pins':{source.id:{}}}))
    child=models.BackgroundJob(kind='pilot_row_replan',status='queued',payload={'site_id':target.id,'parent_id':str(uuid4())},result={})
    db.add(child);db.commit();db.info['pilot_alternative_id']=child.id
    states={s.id:network.read_network(db,s) for s in (source,target)}
    plan=reuse.candidate(db,auto.config(db),target,states,{s.id:s for s in (source,target)},set())
    assert plan['new_main']=='next.test' and plan['former_main']['days']==14
    require_transfer_allowed(db,source,'next.test',plan=plan)
    require_main_destination(db,target,['next.test'],plan=plan)
    with pytest.raises(ValueError):require_transfer_allowed(db,source,'next.test')
    source.brand='Other';db.commit()
    with pytest.raises(ValueError,match='бренд'):reuse.validate(db,plan)
    assert 'next.test' in source.main_domain_history
    assert db.get(models.AutoReglueConfig,policy_key('next.test')).value['main_pins']
    assert sr.calls==tr.calls==[]


def test_former_main_reuse_reaches_native_transfer_without_removing_history(setup):
    from app import cross_reglue_batch as batch, cross_reglue as cross
    db,source,target,sr,tr=setup
    network.read_network(db,source);network.read_network(db,target)
    historical(db,source,'next.test',datetime.now(timezone.utc)-timedelta(days=20))
    child=models.BackgroundJob(kind='pilot_row_replan',status='queued',payload={'site_id':target.id,'parent_id':str(uuid4())},result={})
    db.add(child);db.commit();db.info['pilot_alternative_id']=child.id
    states={s.id:network.read_network(db,s) for s in (source,target)}
    plan=reuse.candidate(db,auto.config(db),target,states,{s.id:s for s in (source,target)},set())
    plan['batch_id']=child.id;plan.pop('preview_token',None);plan['preview_token']=auto.digest(plan)
    db.add(models.AutoReglueConfig(key=batch.key(child.id),value={'plans':[plan],'run_ids':{},'skipped':[],'filter':None}));db.commit()
    run,_=batch.reserve(db,child.id,[{'site_id':target.id,'request_id':str(uuid4()),'preview_token':plan['preview_token']}],'test')[0]
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert tr.data['settings']['canon']=='next.test'
    assert 'next.test' not in sr.data['settings']['domains']
    # Extraction may remove editable membership history, but the recorded departure
    # and the reviewed release evidence remain in the durable operation/plan.
    assert run.plan['former_main']['ended_at'] and run.plan['former_main']['days']==14


def test_equal_network_unknown_date_donor_executes_without_changing_donor_main(setup):
    from app import cross_reglue_batch as batch
    db,source,target,sr,tr=setup
    tr.data['settings']['domains'].append('old-target.test')
    target.domain_types={'old-target.test':'newreg'}
    target.main_domain_history=['old-target.test']
    source.network_state={'domain_added_at':{'next.test':None}}
    child=models.BackgroundJob(kind='pilot_row_replan',status='queued',payload={'site_id':target.id},result={})
    db.add(child);db.commit();db.info['pilot_alternative_id']=child.id
    states={s.id:network.read_network(db,s) for s in (source,target)}
    plan=reuse.candidate(db,auto.config(db),target,states,{s.id:s for s in (source,target)},set())
    assert plan['source_count']==plan['target_count']==2
    assert plan['new_main']=='next.test'
    plan['batch_id']=child.id;plan.pop('preview_token',None);plan['preview_token']=auto.digest(plan)
    db.add(models.AutoReglueConfig(key=batch.key(child.id),value={'plans':[plan],'run_ids':{},'skipped':[],'filter':None}));db.commit()
    run,_=batch.reserve(db,child.id,[{'site_id':target.id,'request_id':str(uuid4()),'preview_token':plan['preview_token']}],'test')[0]
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert tr.data['settings']['canon']=='next.test'
    assert sr.data['settings']['canon']=='main.test'
    assert 'next.test' not in sr.data['settings']['domains']


def test_general_brand_geo_plan_uses_unused_peer_before_retired_main(setup):
    from app import priority_main_targets, cross_reglue_batch
    db,source,target,sr,tr=setup
    tr.data['settings']['domains'].append('old-target.test')
    target.domain_types={'old-target.test':'newreg'};target.main_domain_history=['old-target.test']
    preview=models.BackgroundJob(kind='auto_pilot_preview',status='queued',payload={'site_ids':[target.id]},result={})
    db.add(preview);db.commit();db.info.update(pilot_job_id=preview.id,auto_pilot_preview=True,pilot_allow_stock_drops=False)
    states={s.id:network.read_network(db,s) for s in (source,target)}
    plans,reasons=priority_main_targets.build(db,auto.config(db),[target],{s.id:s for s in (source,target)},states,{source.id:['next.test'],target.id:[]})
    assert not reasons and len(plans)==1
    assert plans[0]['new_main']=='next.test' and plans[0]['source_site_id']==source.id
    cross_reglue_batch.validate(plans)
