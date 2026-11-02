from uuid import uuid4
from collections import Counter
import copy
import pytest
from sqlalchemy import select
from app import models,auto_reglue as auto,move_plus2 as plus,move_batch as batch,domain_transfer_queue as queue
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool
from test_move_plus2 import init


def finish(db,runs):
    for _ in range(12):
        for r in runs:auto.execute(db,r.id)
        if all(r.status=='completed' for r in runs):return
    assert False,[(r.status,r.message) for r in runs]


def test_two_donors_extract_four_roots_then_add_in_order_with_one_request_receipt(pool):
    db,sites,remotes,filters,roots=init(pool)
    id=uuid4();ids=[s.id for s in sites]
    runs,fresh=batch.prepare(db,id,filters,ids,'test')
    assert fresh and len(runs)==2 and len({r.plan['source_site_id'] for r in runs})==2
    assert batch.prepare(db,id,filters,ids,'test')[1] is False
    auto.execute(db,runs[0].id)
    assert runs[0].status=='waiting' and runs[0].plan['source_released']
    assert not any(path=='/site-config/create' for r in remotes.values() for path,_ in r.calls)
    assert len(queue.listing(db,filters.brand,filters.geo)['entries'])==2
    auto.execute(db,runs[1].id)
    assert runs[1].plan['source_released']
    assert len(queue.listing(db,filters.brand,filters.geo)['entries'])==4
    assert not any(path=='/site-config/create' for r in remotes.values() for path,_ in r.calls)
    finish(db,runs)
    assert not queue.listing(db,filters.brand,filters.geo)['entries']
    assert sum(Counter(p for p,_ in r.calls)['/site-config/create'] for r in remotes.values())==2
    assert all(r.plan['source_after']['canon']==r.plan['source_before']['canon'] for r in runs)


def test_two_donors_one_receiver_revalidate_changes_from_own_group(pool):
    db,sites,remotes,filters,roots=init(pool)
    runs,_=batch.prepare(db,uuid4(),filters,[s.id for s in sites[:3]],'test')
    assert len(runs)==1
    finish(db,runs)
    assert len(remotes[runs[0].site_id].data['settings']['domains'])==3


def test_insufficient_newregs_use_at_most_one_drop_in_group(pool):
    db,sites,remotes,filters,roots=init(pool)
    for donor in sites[:2]:
        for n,d in enumerate(donor.domain_types):donor.domain_types={**donor.domain_types,d:'newreg' if n==0 else 'drop'}
    db.commit()
    runs,_=batch.prepare(db,uuid4(),filters,[s.id for s in sites],'test')
    assert sum(d['domain_type']=='drop' for r in runs for d in r.plan['domains'])==1
    assert sum(len(r.plan['domains']) for r in runs)==3
    finish(db,runs)
    for run in runs:plus.validate_intent(db,run)


def test_native_domain_failure_skips_only_failed_candidates_and_queues_replacement(pool):
    db,sites,remotes,filters,roots=init(pool)
    runs,_=batch.prepare(db,uuid4(),filters,[s.id for s in sites],'test')
    bad=[d['domain'] for d in runs[0].plan['domains']]
    tr=remotes[runs[0].site_id];request=tr.request;old_job=tr.job_state;jobs={}
    def native(method,path,payload):
        response=request(method,path,payload)
        if path=='/site-config/create':
            tr.data['settings']['domains']=[d for d in tr.data['settings']['domains'] if d not in bad]
            id=str(uuid4());bad_rows=[{'domain':d['domain'],'status':'error','failedStage':'dns','errorMessage':'DNS unavailable'} for d in payload['domains'] if d['domain'] in bad]
            jobs[id]={'state':'completed','result':{'errorCount':len(bad_rows),'domains':bad_rows}}
            return 201,{'jobId':id}
        return response
    tr.request=native;tr.job_state=lambda id:jobs.get(id,old_job(id))
    auto.execute(db,runs[0].id);auto.execute(db,runs[1].id);auto.execute(db,runs[0].id)
    assert runs[0].status=='partial'
    runs[0].plan={**runs[0].plan,'replacement_error':'Old temporary planning error'};db.commit()
    sent=[];replacement=batch.continue_after_error(db,runs[0],sent.append)
    assert runs[0].plan['replacement_error'] is None
    assert replacement and sent==[replacement[0].id]
    assert set(batch.blocked_domains(db,filters.brand,filters.geo))==set(bad)
    assert not set(d['domain'] for d in replacement[0].plan['domains'])&set(bad)
    finish(db,[runs[1],*replacement])
    assert runs[0].status=='failed'
    assert {e['domain'] for e in queue.listing(db,filters.brand,filters.geo)['entries']}==set(bad)
    assert len(runs[0].plan['domain_errors'])==2
    assert not batch.continue_after_error(db,runs[0],sent.append)


def test_old_single_donor_receipt_is_not_expanded_into_new_transfers_after_upgrade(pool):
    db,sites,remotes,filters,roots=init(pool)
    id=uuid4();ids=[s.id for s in sites]
    original,_=plus.prepare(db,id,filters,ids,'test')
    before=sum(len(r.calls) for r in remotes.values())
    runs,fresh=batch.prepare(db,id,filters,ids,'test')
    assert not fresh and [r.id for r in runs]==[original.id]
    assert sum(len(r.calls) for r in remotes.values())==before


@pytest.mark.parametrize('count',[1,2])
def test_five_donors_wait_for_queue_capacity_and_all_finish(pool,count):
    db,sites,remotes,filters,roots=init(pool)
    add=pool[-1]
    for index in range(3):
        donor=add(f'extra-donor-{index}.test')
        donor.site_type='monobrand'; donor.hidden_from_projects=False
        roots(donor,12+index)
        sites.append(donor)
        receiver=add(f'extra-small-{index}.test')
        receiver.site_type='monobrand'; receiver.hidden_from_projects=False
        sites.append(receiver)
    db.commit()
    runs,_=batch.prepare(db,uuid4(),filters,[s.id for s in sites],'test',count=count)
    assert len(runs)==5
    assert len({r.plan['source_site_id'] for r in runs})==5
    peak=0
    for _ in range(14):
        for run in runs:
            auto.execute(db,run.id)
            size=len(queue.listing(db,filters.brand,filters.geo)['entries'])
            assert size<=5
            peak=max(peak,size)
            assert run.status not in {'failed','partial'},run.message
        if all(r.status=='completed' for r in runs):break
    assert all(r.status=='completed' for r in runs)
    assert not queue.listing(db,filters.brand,filters.geo)['entries']
    assert sum(len(r.plan['domains']) for r in runs)==5*count
    assert peak==5 if count==1 else peak==4


@pytest.mark.parametrize('count,receivers',[(1,2),(1,3),(2,2),(1,6)])
def test_single_donor_extracts_demand_together_and_routes_to_separate_networks(pool,count,receivers):
    db,sites,remotes,filters,roots=init(pool)
    donor=sites[0]
    roots(donor,18)
    add=pool[-1]
    targets=[sites[2],sites[3]]+[add(f'new-small-{i}.test',site_type='monobrand',hidden_from_projects=False) for i in range(receivers-2)]
    db.commit()
    runs,_=batch.prepare(db,uuid4(),filters,[donor.id,*[s.id for s in targets]],'test',count=count)
    assert len(runs)==receivers
    assert {r.plan['source_site_id'] for r in runs}=={donor.id}
    assert {r.site_id for r in runs}=={s.id for s in targets}
    assert len({d['domain'] for r in runs for d in r.plan['domains']})==count*receivers
    auto.execute(db,runs[0].id)
    deletes=[body for path,body in remotes[donor.id].calls if path=='/site-config/delete']
    assert len(deletes)==1 and len(deletes[0]['domains'])==min(5//count,receivers)*count
    assert len(queue.listing(db,filters.brand,filters.geo)['entries'])<=5
    finish(db,runs)
    assert not queue.listing(db,filters.brand,filters.geo)['entries']
    for target in targets:assert len(remotes[target.id].data['settings']['domains'])==1+count
    assert all(len(body['domains'])<=5 for path,body in remotes[donor.id].calls if path=='/site-config/delete')


def test_failed_domain_in_shared_extraction_does_not_stop_other_recipient(pool):
    db,sites,remotes,filters,roots=init(pool)
    donor=sites[0];targets=sites[2:]
    runs,_=batch.prepare(db,uuid4(),filters,[donor.id,*[s.id for s in targets]],'test',count=1)
    bad=runs[0].plan['domains'][0]['domain'];good=runs[1].plan['domains'][0]['domain']
    native=remotes[donor.id];request=native.request
    def partial(method,path,payload):
        response=request(method,path,payload)
        if path=='/site-config/delete':native.data['settings']['domains'].append(bad)
        return response
    native.request=partial
    native.job_state=lambda id:{'state':'completed','result':{'errorCount':1,'domains':[{'domain':bad,'status':'error','errorMessage':'Cannot remove configuration'},{'domain':good,'status':'success'}]}}
    auto.execute(db,runs[0].id)
    assert runs[0].status=='partial'
    auto.execute(db,runs[1].id)
    assert runs[1].status=='completed',runs[1].message
    assert good in remotes[runs[1].site_id].data['settings']['domains']
    assert bad in native.data['settings']['domains']
    assert not any(e['domain']==good for e in queue.listing(db,filters.brand,filters.geo)['entries'])


def test_completed_peer_with_expired_native_job_does_not_block_later_transfer(pool):
    db,sites,remotes,filters,roots=init(pool)
    original,_=plus.prepare(db,uuid4(),filters,[s.id for s in sites],'test',count=1)
    auto.execute(db,original.id)
    assert original.status=='completed'
    later,_=plus.prepare(db,uuid4(),filters,[s.id for s in sites],'test',count=1,prefetch={
        'id':original.id,'runs':[original],'index':1,'unique_donors':False,'unique_recipients':True})
    assert later.site_id!=original.site_id
    db.add(models.AutoReglueConfig(key=batch.group_key(original.id),value={'run_ids':[original.id,later.id],'ready':True}));db.commit()
    remotes[original.site_id].job_state=lambda id:None
    auto.execute(db,later.id)
    assert later.status=='completed',later.message


def test_native_dns_errors_do_not_trigger_replacements_when_destination_contains_domains(pool):
    db,sites,remotes,filters,roots=init(pool)
    runs,_=batch.prepare(db,uuid4(),filters,[s.id for s in sites],'test')
    target=remotes[runs[0].site_id]
    target.job_state=lambda id:{'state':'completed','result':{'errorCount':2,'domains':[
        {'domain':d['domain'],'status':'error','failedStage':'dns','errorMessage':'old DNS failure'} for d in runs[0].plan['domains']]}}
    finish(db,runs)
    sent=[]
    assert not batch.continue_after_error(db,runs[0],sent.append)
    assert not sent and not batch.blocked_domains(db,filters.brand,filters.geo)
    assert not batch.domain_errors(db,runs[0])
    assert not runs[0].plan.get('domain_errors')
    assert not queue.listing(db,filters.brand,filters.geo)['entries']
