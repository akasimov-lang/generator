from copy import deepcopy
from app import models,auto_pilot as pilot,auto_reglue as auto,project_network as network,cross_reglue_batch as batch
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool,reserve,finish
from test_pilot_variations import make_preview


def test_one_donor_transfers_twelve_distinct_drops_and_newregs(pool):
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    donor=add('large-donor.test',free=12)
    donor.domain_types={d:('drop' if i%2 else 'newreg') for i,d in enumerate(donor.domain_types)};db.commit()
    recipients=[add(f'recipient-{i}.test') for i in range(12)]
    preview=batch.build(db,recipients,'test')
    assert not preview['skipped'] and len(preview['plans'])==12
    assert len({p['new_main'] for p in preview['plans']})==12
    assert {p['domain_type'] for p in preview['plans']}=={'drop','newreg'}
    runs=reserve(db,preview);finish(db,runs)
    assert remotes[donor.id].data['settings']['canon']==donor.name
    assert remotes[donor.id].data['settings']['domains']==[donor.name]
    assert all(r.status=='completed' for r in runs)


def test_typed_refresh_excludes_domains_already_assigned_in_other_groups(pool):
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    donor=add('only-donor.test',free=2);recipient=add('only-recipient.test')
    cfg=auto.config(db);cfg.main_target_mode='newreg';auto.save_config(db,cfg)
    first=next(iter(donor.domain_types));db.info['reglue_preview_domains']={first}
    preview=batch.build(db,[recipient],'test')
    assert len(preview['plans'])==1
    assert preview['plans'][0]['new_main']!=first


def test_skipped_preview_does_not_show_stale_domain_assignment(pool,monkeypatch):
    monkeypatch.setattr('app.reglue_title_h1.prepare_for_plan',lambda *a,**k:None)
    db,sites,remotes,job=make_preview(pool,2)
    result=deepcopy(job.result);sid=sites[0].id
    stale=next(p for g in result['groups'] for p in g.get('plans',[]) if p['site_id']==sid)
    result['items'][sid].update(status='skipped',reason='No unused domain',**pilot.describe(db,stale))
    for g in result['groups']:g['plans']=[p for p in g.get('plans',[]) if p['site_id']!=sid]
    job.result=result;db.commit()
    row=next(r for r in pilot.view(db,job)['items'] if r['site_id']==sid)
    assert row['status']=='skipped' and not row.get('new_main') and not row.get('source_project')
    assert row['reason']=='No unused domain'
    assert job.result['items'][sid]['new_main']==stale['new_main']  # history retained
