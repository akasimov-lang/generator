from uuid import uuid4
from collections import Counter
import copy
import pytest
from app import auto_reglue as auto, domain_redistribution as move, models, project_network as network
from app.domain_transfer_policy import set_ban
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool


def prepare(pool, kinds=('drop','newreg')):
    db,source,target,remotes,add=pool
    remotes[source.id].data['settings']['domains']=['main.test','one.test','two.test','three.test']
    source.domain_types={'one.test':kinds[0],'two.test':kinds[1],'three.test':kinds[1]};db.commit()
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='transfer_only'))
    plan=auto.preview(db,target)
    run,_=auto.prepare_run(db,target,uuid4(),plan['preview_token'],'test','mass')
    return run


@pytest.mark.parametrize('kinds,expected',[ (('drop','newreg'),['drop','newreg']), (('drop','drop'),['drop','drop']), (('newreg','newreg'),['newreg','newreg']) ])
def test_two_domains_mix_fallback_main_and_head_preserved(pool,kinds,expected):
    db,source,target,remotes,add=pool
    run=prepare(pool,kinds)
    before={site_id:copy.deepcopy(remote.data) for site_id,remote in remotes.items()}
    assert [d['domain_type'] for d in run.plan['domains']]==expected
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert len(run.plan['domains'])==2
    for site_id,remote in remotes.items():
        assert remote.data['settings']['canon']==before[site_id]['settings']['canon']
        assert remote.data['head']==before[site_id]['head']
        assert all(path in {'/site-config/create','/site-config/delete'} for path,_ in remote.calls)
    assert len(run.plan['source_before']['domains'])-len(run.plan['source_after']['domains'])==2
    assert len(run.plan['target_after']['domains'])-len(run.plan['target_before']['domains'])==2
    calls=sum(len(r.calls) for r in remotes.values())
    auto.execute(db,run.id)
    assert calls==sum(len(r.calls) for r in remotes.values())


def test_rollback_restores_memberships_keeps_history_and_bypasses_only_own_cooldown(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    before={sid:set(r.data['settings']['domains']) for sid,r in remotes.items()}
    auto.execute(db,run.id)
    inverse,fresh=move.prepare_rollback(db,run,'user')
    assert fresh
    again,fresh=move.prepare_rollback(db,run,'user')
    assert again.id==inverse.id and not fresh
    auto.execute(db,inverse.id)
    assert inverse.status=='completed',inverse.message
    assert run.status=='completed' and run.plan['rolled_back_at']
    assert inverse.plan['rollback_of']==run.id
    for sid,r in remotes.items():assert set(r.data['settings']['domains'])==before[sid]
    assert len(source.network_state['domain_membership_history'])>len(before[source.id])


def test_rollback_cannot_move_new_main_or_banned_domain(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);auto.execute(db,run.id)
    domain=run.plan['domains'][0]['domain']
    set_ban(db,target,domain,True,'user')
    with pytest.raises(ValueError,match='БАН'):
        move.prepare_rollback(db,run,'user')
    set_ban(db,target,domain,False,'user')
    remotes[target.id].data['settings']['canon']=domain
    with pytest.raises(ValueError):move.prepare_rollback(db,run,'user')


def test_waits_for_each_remote_job_and_never_resends_delete(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);remotes[source.id].job_ready=False
    auto.execute(db,run.id)
    assert run.status=='waiting' and not remotes[target.id].calls
    deletes=[payload for path,payload in remotes[source.id].calls if path=='/site-config/delete']
    assert len(deletes)==1
    assert deletes[0]['domains']==[item['domain'] for item in run.plan['domains']]
    remotes[source.id].job_ready=True
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert Counter(path for path,_ in remotes[source.id].calls)['/site-config/delete']==1
    creates=[payload for path,payload in remotes[target.id].calls if path=='/site-config/create']
    assert len(creates)==1
    assert [item['domain'] for item in creates[0]['domains']]==deletes[0]['domains']


def test_batch_waits_until_both_domains_are_absent_even_after_job_completed(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    sr=remotes[source.id]
    request=sr.request
    names=[item['domain'] for item in run.plan['domains']]
    def incomplete_delete(method,path,payload):
        response=request(method,path,payload)
        if path=='/site-config/delete':
            sr.data['settings']['domains'].append(names[1])
        return response
    sr.request=incomplete_delete
    auto.execute(db,run.id)
    assert run.status=='waiting' and not remotes[target.id].calls
    sr.data['settings']['domains'].remove(names[1])
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert Counter(path for path,_ in sr.calls)['/site-config/delete']==1


def test_failed_batch_deletion_never_adds_domains(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);remotes[source.id].fail_job=True
    auto.execute(db,run.id)
    assert run.status=='partial' and not remotes[target.id].calls
    auto.execute(db,run.id)
    assert not remotes[target.id].calls
    assert Counter(path for path,_ in remotes[source.id].calls)['/site-config/delete']==1


def test_batch_write_guard_rejects_unplanned_domains_and_early_creation(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    state=network.read_network(db,source)
    names=[item['domain'] for item in run.plan['domains']]
    for domains in [names[:1],names+['third.test']]:
        payload=network.NetworkChange(request_id=move.receipt(run,'delete_batch'),
            action='delete_domain',revision=state['revision'],domains=domains)
        with pytest.raises(ValueError,match='согласованные'):
            move.validate_write(db,run,source,payload)
    payload=network.NetworkChange(request_id=move.receipt(run,'create'),
        action='create_domains',revision=state['revision'],domains=names)
    with pytest.raises(ValueError,match='согласованные'):
        move.validate_write(db,run,target,payload)
    assert all(not remote.calls for remote in remotes.values())


def test_destination_presence_completes_transfer_even_while_native_job_is_pending(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);remotes[target.id].job_ready=False
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    auto.execute(db,run.id)
    assert Counter(path for path,_ in remotes[target.id].calls)['/site-config/create']==1


def test_pending_addition_without_destination_membership_is_not_resent(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool);remote=remotes[target.id];remote.job_ready=False
    request=remote.request
    names=[d['domain'] for d in run.plan['domains']]
    def delayed(method,path,payload):
        result=request(method,path,payload)
        if path=='/site-config/create':remote.data['settings']['domains']=[d for d in remote.data['settings']['domains'] if d not in names]
        return result
    remote.request=delayed
    auto.execute(db,run.id)
    assert run.status=='waiting'
    auto.execute(db,run.id)
    assert run.status=='waiting'
    remote.data['settings']['domains'].extend(names)
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert Counter(path for path,_ in remote.calls)['/site-config/create']==1


def test_legacy_individual_deletions_keep_receipts_and_resume_without_replay(pool):
    db,source,target,remotes,add=pool
    run=prepare(pool)
    run.plan={k:v for k,v in run.plan.items() if k!='deletion_mode'};db.commit()
    remotes[source.id].job_ready=False
    auto.execute(db,run.id)
    assert run.status=='waiting' and not remotes[target.id].calls
    assert db.get(models.NetworkOperation,move.receipt(run,'delete:'+run.plan['domains'][0]['domain']))
    remotes[source.id].job_ready=True
    auto.execute(db,run.id)
    assert run.status=='completed',run.message
    assert Counter(path for path,_ in remotes[source.id].calls)['/site-config/delete']==2
    assert not db.get(models.NetworkOperation,move.receipt(run,'delete_batch'))


def test_one_available_domain_is_allowed_and_manual_limit_is_not_schedulable(pool):
    db,source,target,remotes,add=pool
    auto.save_config(db,auto.GlobalConfig(enabled=True,execution_mode='transfer_only'))
    plan=auto.preview(db,target)
    assert len(plan['domains'])==1
    with pytest.raises(ValueError,match='вручную'):
        auto.GlobalConfig(enabled=True,execution_mode='transfer_only',schedule_enabled=True)
    assert not auto.schedule_eligible(source,auto.config(db),auto.config(db,source.id))
