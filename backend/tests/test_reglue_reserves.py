from uuid import uuid4
from sqlalchemy import select
import pytest
from app import models, reglue_reserves as stock, cross_reglue as cross, cross_reglue_batch as batch, auto_reglue as auto
from app.reglue_reserves_api import BrandRequest, brand as edit_brand, inventory
from fastapi import HTTPException
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool, reserve, finish


def upload(db, domains, kind='drop', brand=''):
    return stock.import_domains(db, domains, kind, brand, 'test')


def test_import_normalizes_separators_and_preserves_bad_input(pool):
    db,source,target,remotes,add=pool
    result=upload(db,' HTTPS://WWW.Example.com/\nsecond.org, third.net third.net bad https://x.com/path 127.0.0.1 localhost')
    assert result['added']==['example.com','second.org','third.net']
    assert result['duplicates']==['third.net']
    assert len(result['errors'])==4
    row=db.scalar(select(models.ReglueReserveDomain).where(models.ReglueReserveDomain.domain=='example.com'))
    assert row.status=='available' and row.brand is None and row.created_at
    assert not upload(db,'example.com')['added']
    assert all(not r.calls for r in remotes.values())


def test_brand_and_azerbaijan_rules_and_exact_root_history(pool):
    db,source,target,remotes,add=pool
    upload(db,'common.test specific.test foreign.test used.test')
    rows=list(db.scalars(select(models.ReglueReserveDomain)))
    by={r.domain:r for r in rows};by['specific.test'].brand='Pin-Up';by['foreign.test'].brand='Other'
    target.main_domain_history=['www.used.test'];db.commit()
    state=cross.network.read_network(db,target)
    assert stock.candidate(db,target,state,['drop']) is None  # AZ blocks all stock drops
    target.cache_geo='PL';db.commit()
    assert stock.candidate(db,target,state,['drop']).domain=='specific.test'
    assert stock.candidate(db,target,state,['drop'],{'specific.test','common.test'}) is None
    target.brand='Other';db.commit()
    assert stock.candidate(db,target,state,['drop']).domain=='foreign.test'
    assert stock.candidate(db,target,state,['drop'],{'foreign.test'}).domain=='common.test'


def test_explicit_stock_exception_is_bound_to_one_project_domain_and_run(pool):
    db, source, target, remotes, add = pool
    upload(db, 'one.test two.test')
    row = db.scalar(select(models.ReglueReserveDomain).where(models.ReglueReserveDomain.domain == 'one.test'))
    state = cross.network.read_network(db, target)
    rid = str(uuid4())
    key = stock.permit_key(target.id, row.id)
    assert len(key) <= models.AutoReglueConfig.__table__.c.key.type.length
    assert key != stock.permit_key(source.id, row.id)
    db.add(models.AutoReglueConfig(key=key,
        value={'site_id': target.id, 'domain': row.domain, 'run_id': rid, 'authorized_by': 'anton', 'reason': 'Explicit replacement request'})); db.commit()
    assert stock.candidate(db, target, state, ['drop']) is None
    db.info['stock_permit_run_id'] = rid
    assert stock.candidate(db, target, state, ['drop']).id == row.id
    assert stock.candidate(db, target, state, ['drop'], {row.domain}) is None
    assert stock.candidate(db, source, cross.network.read_network(db, source), ['drop']) is None
    db.info['stock_permit_run_id'] = str(uuid4())
    assert stock.candidate(db, target, state, ['drop']) is None


def test_pool_drop_is_added_and_promoted_once_without_extraction(pool):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit()
    upload(db,'new-drop.test',brand='Pin-Up')
    preview=batch.build(db,[target],'test');plan=preview['plans'][0]
    assert plan['reserve_pool_id'] and plan['new_main']=='new-drop.test'
    row=db.get(models.ReglueReserveDomain,plan['reserve_pool_id'])
    assert row.status=='available' and row.assigned_at is None
    assert all(not r.calls for r in remotes.values())
    runs=reserve(db,preview)
    assert row.status=='reserved' and row.site_id==target.id
    finish(db,runs)
    assert row.status=='assigned' and row.assigned_at and not row.error
    assert remotes[target.id].data['settings']['canon']=='new-drop.test'
    assert target.domain_types['new-drop.test']=='drop'
    assert not remotes[source.id].calls
    calls=list(remotes[target.id].calls)
    auto.execute(db,runs[0].id)
    assert remotes[target.id].calls==calls


def test_az_uses_cross_network_when_stock_only_has_drops(pool):
    db,source,target,remotes,add=pool
    upload(db,'never-az.test')
    preview=batch.build(db,[target],'test')
    assert preview['plans'][0]['source_site_id']==source.id
    assert not preview['plans'][0].get('reserve_pool_id')
    assert db.scalar(select(models.ReglueReserveDomain)).status=='available'


def test_competing_previews_cannot_claim_same_domain(pool):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit();second=add('second-project.test',geo='PL')
    upload(db,'one-only.test')
    first=batch.build(db,[target],'test');other=batch.build(db,[second],'test')
    assert first['plans'][0]['new_main']==other['plans'][0]['new_main']
    reserve(db,first)
    with pytest.raises(ValueError,match='занят'):reserve(db,other)
    db.rollback()
    assert all(not r.calls for r in remotes.values())


def test_brand_change_invalidates_preview_and_claim_freezes_brand(pool):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit();upload(db,'brand.test')
    preview=batch.build(db,[target],'test');row=db.scalar(select(models.ReglueReserveDomain))
    edit_brand(row.id,BrandRequest(brand='Other'),{'username':'test'},db)
    with pytest.raises(ValueError,match='бренда'):reserve(db,preview)
    db.rollback();edit_brand(row.id,BrandRequest(brand='Pin-Up'),{'username':'test'},db)
    reserve(db,preview)
    with pytest.raises(HTTPException) as e:edit_brand(row.id,BrandRequest(brand='Other'),{'username':'test'},db)
    assert e.value.status_code==409


def test_batch_allocates_unique_roots_with_typed_quotas(pool):
    db,source,target,remotes,add=pool
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='cross_network',main_target_mode='mixed'))
    targets=[add(f'pl{i}.test',geo='PL') for i in range(4)]
    upload(db,'a.test b.test');upload(db,'c.test d.test','newreg')
    preview=batch.build(db,targets,'test')
    assert not preview['skipped'] and len({p['new_main'] for p in preview['plans']})==4
    assert sorted(p['domain_type'] for p in preview['plans'])==['drop','drop','newreg','newreg']
    finish(db,reserve(db,preview))


def test_inventory_redacts_restricted_assignment(pool):
    db,source,target,remotes,add=pool
    upload(db,'secret.test');row=db.scalar(select(models.ReglueReserveDomain));row.site_id=source.id;row.status='assigned';row.error='secret project details';db.commit()
    result=inventory({'allowed_site_ids':[target.id]},db)
    assert result['items'][0]['project'] is None and result['items'][0]['fibery_name'] is None
    assert result['items'][0]['project_restricted'] and result['items'][0]['error'] is None


def test_failure_keeps_domain_claimed_and_records_error(pool,monkeypatch):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit();upload(db,'failure.test')
    preview=batch.build(db,[target],'test');runs=reserve(db,preview)
    original=cross.change
    def broken(db,run,site,action,state,**values):
        if action=='create_domains':raise ValueError('WEBDEV_CREATE_FAILED: добавление не выполнено')
        return original(db,run,site,action,state,**values)
    monkeypatch.setattr(cross,'change',broken)
    auto.execute(db,runs[0].id)
    row=db.scalar(select(models.ReglueReserveDomain))
    assert row.status=='error' and 'WEBDEV_CREATE_FAILED' in row.error and row.assigned_at is None
    assert row.run_id==runs[0].id and stock.candidate(db,target,cross.network.read_network(db,target),['drop']) is None


def test_domain_never_reused_in_receiving_network(pool):
    db,source,target,remotes,add=pool
    target.main_domain_history=['www.next.test'];db.commit()
    result=batch.build(db,[target],'test')
    assert not result['plans']
    with pytest.raises(ValueError,match='Нет подходящего'):auto.preview(db,target)


def test_single_preview_claim_and_execution(pool):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit();upload(db,'single.test')
    preview=auto.preview(db,target)
    run,_=auto.prepare_run(db,target,uuid4(),preview['preview_token'],'test','mass')
    assert db.scalar(select(models.ReglueReserveDomain)).run_id==run.id
    finish(db,[run])


def test_scoped_user_can_import_and_use_shared_inventory(pool):
    from app import project_access
    db,source,target,remotes,add=pool
    db.info['allowed_site_ids']={target.id}
    upload(db,'shared.test')
    row=db.scalar(select(models.ReglueReserveDomain))
    assert row is not None
    edit_brand(row.id,BrandRequest(brand='Pin-Up'),{'username':'test'},db)
    assert inventory({'allowed_site_ids':[target.id]},db)['available']==1
    db.info.pop('allowed_site_ids')


def test_az_rule_rechecked_after_preview(pool):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit();upload(db,'no-az.test')
    preview=batch.build(db,[target],'test')
    target.cache_geo='AZ';db.commit()
    with pytest.raises(ValueError,match='Азербайджан'):reserve(db,preview)
    assert all(not r.calls for r in remotes.values())


def test_confirmation_wait_does_not_resend_create(pool,monkeypatch):
    db,source,target,remotes,add=pool
    target.cache_geo='PL';db.commit();upload(db,'waiting.test')
    preview=batch.build(db,[target],'test');runs=reserve(db,preview)
    original=cross.completed_job; attempts=[]
    def pending(db,site,operation):
        if operation.action=='create_domains' and not attempts:
            attempts.append(True);return False
        return original(db,site,operation)
    monkeypatch.setattr(cross,'completed_job',pending)
    auto.execute(db,runs[0].id)
    assert runs[0].status=='waiting'
    row=db.scalar(select(models.ReglueReserveDomain))
    assert row.status=='reserved' and row.error and row.assigned_at is None
    before=len(remotes[target.id].calls)
    finish(db,runs)
    assert row.status=='assigned' and not row.error
    # FakeRemote records route/payload; exactly one create request is permitted.
    assert sum(c[0] == '/site-config/create' for c in remotes[target.id].calls)==1,remotes[target.id].calls


def test_reserve_that_previously_was_main_is_rejected(pool):
    db,source,target,remotes,add=pool
    remote=remotes[target.id];remote.data['settings']['domains'].append('old-reserve.test')
    remote.data['settings']['reserve']='old-reserve.test'
    target.main_domain_history=['old-reserve.test'];db.commit()
    state=cross.network.read_network(db,target)
    with pytest.raises(ValueError,match='Main'):cross.require_selected_reserve(db,target,state,'old-reserve.test')


def test_general_keyword_site_can_receive_unbranded_stock(pool):
    db,source,target,remotes,add=pool
    target.brand='Общие ключи';target.site_type='general';target.cache_geo='PL';db.commit()
    upload(db,'general.test')
    preview=batch.build(db,[target],'test')
    assert preview['plans'][0]['new_main']=='general.test'
    finish(db,reserve(db,preview))


def test_missing_drop_quota_can_use_newreg_stock(pool):
    db,source,target,remotes,add=pool
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='cross_network',main_target_mode='drop'))
    source.project_status='working';db.commit()
    upload(db,'fallback-newreg.test','newreg')
    preview=batch.build(db,[target],'test');plan=preview['plans'][0]
    assert plan['requested_target_kind']=='drop' and plan['main_target_kind']=='newreg' and plan['target_fallback']
    finish(db,reserve(db,preview))
