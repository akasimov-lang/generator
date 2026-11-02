from collections import Counter
from uuid import uuid4
import pytest
from app import models,auto_pilot as pilot,auto_reglue as auto,mass_reglue_launch as launch,project_network as network
from app.pilot_variations import count_share
from app.canonical_allocation import mode
from test_project_network import env
from test_cross_reglue import setup
from test_cross_reglue_batch import pool,reserve,finish
USER={'username':'test','allowed_site_ids':None}


@pytest.fixture(autouse=True)
def reviewed_titles(monkeypatch):
    from app import reglue_title_h1
    monkeypatch.setattr(reglue_title_h1,'prepare_preview',lambda db,site,job_id,**kwargs:{'draft_id':str(uuid4()),
        'title_before':'Casino bonus online','title_after':'Casino online bonus','h1_before':'Casino games online','h1_after':'Casino online games'})


def test_half_up_and_percent_validation():
    assert count_share(10,15)==2 and count_share(3,20)==1 and count_share(2,20)==0
    for bad in (-1,101,2.5,True):
        with pytest.raises(ValueError):auto.GlobalConfig(title_h1_rewrite_percent=bad)


def make_preview(pool,number=20):
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    cfg=auto.config(db);cfg.scheme_mode='locale_base';auto.save_config(db,cfg)
    sites=[add(f'own-{i}.test',free=2,brand='TestBrand',geo='HU') for i in range(number)]
    for s in sites:
        s.cache_language='hu'
        remotes[s.id].data['data']={'pages':[{'id':'1','slug':'/','title':'Casino Brand bonus online','content':{'blocks':[{'type':'header','data':{'level':1,'text':'Casino Brand games online'}}]}}]}
        remotes[s.id].data['settings']['alternate']={'enableDynamicRoutes':True,'currentFakeMain':'/old/','fakeMain':['/old/']}
        remotes[s.id].data['head'].update(alternateMarkup=f'<link rel="alternate" hreflang="hu-HU" href="https://{s.name}/old/" />',
            canonicalFakeMainMarkup='<link rel="canonical" href="https://{{settings.canon}}/old/" />',
            canonicalDefaultMarkup='<link rel="canonical" href="https://{{settings.canon}}{{reqPath}}" />',enableCanonical=True)
    db.commit();job=pilot.create(db,uuid4(),USER)
    for _ in range(number+1):
        launch.execute_step(db,job.id,lambda _:pytest.fail('preview writes'))
        if job.status=='completed':break
    assert job.status=='completed'
    return db,sites,remotes,job


def test_global_quotas_parent_alternate_variants_and_stable_review(pool):
    db,sites,remotes,job=make_preview(pool)
    plans=[p for g in job.result['groups'] for p in g.get('plans',[])]
    summary=job.result['variation_summary']
    assert summary['total']==20
    assert sum(bool(p.get('create_subdomain')) for p in plans)==2
    assert summary['subdomains_percent']==10 and summary['subdomains_requested']==2
    assert sum(p['redirect_old_main'] for p in plans)==4
    assert sum(p['rewrite_title_h1'] for p in plans)==4
    assert sum(p.get('without_alternates',False) for p in plans)==2
    assert sum(not p['enableAlternates'] for p in plans)==2
    assert all(p['enableAlternates'] for p in plans if p.get('parent_domain'))
    assert Counter(p['canonical_mode'] for p in plans)=={'self':10,'internal':10}
    for p in plans:
        assert p.get('fake_main_path')!=p.get('old_fake_main_path')
        assert p.get('create_fake_main_path')==p.get('fake_main_path')
        assert pilot.describe(db,p)['new_fake_path']==p['fake_main_path']
        if p.get('parent_domain'):
            assert 'https://'+p['parent_domain']+'/' in p['alternateMarkup'] and p['enableAlternates']
        if p['enableAlternates']:
            assert '/old/' not in p['alternateMarkup']
        assert mode(p['canonicalFakeMainMarkup'])==p['canonical_mode']
    assert all(not r.calls for r in remotes.values())
    before=auto.digest(job.result)
    launch.execute_step(db,job.id,lambda _:pytest.fail('preview writes'))
    assert before==auto.digest(job.result)
    assert len({p['new_main'] for p in plans})==20


def test_reviewed_canonical_and_redirects_reach_webdev(pool,monkeypatch):
    from app import reglue_title_h1
    monkeypatch.setattr(reglue_title_h1,'finish',lambda *args:True)
    db,sites,remotes,job=make_preview(pool,4)
    pilot.start(db,job.id,USER);sent=[]
    launch.execute_step(db,job.id,sent.append)
    runs=[db.get(models.AutoReglueRun,id) for id in sent]
    # Native test remote supports create_subdomains through settings.domains.
    for remote in remotes.values():
        original=remote.request
        def request(method,path,payload,original=original,remote=remote):
            if path=='/site-config/create-subdomains':
                remote.data['settings']['domains'] += payload['domains'];return 200,{'ok':True}
            return original(method,path,payload)
        remote.request=request
    finish(db,runs)
    for run in runs:
        p=run.plan;remote=remotes[run.site_id]
        assert remote.data['head']['alternateMarkup']==p['alternateMarkup']
        assert remote.data['head']['enableAlternates']==p['enableAlternates']
        from app.cross_reglue import receipt_id
        operation=db.get(models.NetworkOperation,receipt_id(run,'create_fake_main'))
        assert operation.request_payload['head_sync']['alternateMarkup']!=p['alternates_before']['markup']
        assert operation.status=='confirmed'
        if p.get('fake_main_path'):assert remote.data['head']['canonicalFakeMainMarkup']==p['canonicalFakeMainMarkup']
        if p['redirect_old_main']:
            expected=p['new_main']+(p.get('fake_main_path','') if p['canonical_mode']=='internal' else '')
            assert {'url':p['old_main'],'value':expected} in remote.data['settings']['redirects']


def test_fake_hreflang_rotates_across_canonical_types_and_projects(pool):
    from app.network_state import alternate_links
    db,sites,remotes,job=make_preview(pool,20)
    previous=None;roles=[]
    for p in [p for g in job.result['groups'] for p in g.get('plans',[])]:
        if p.get('without_alternates'):continue
        assert p.get('fake_hreflang_role'), 'Enabled alternates must retain the generated fake path'
        links=alternate_links(p['alternateMarkup'])
        codes=[link['hreflang'] for link in links if link['href'].endswith(p['fake_main_path'])]
        assert codes
        assert p['fake_hreflang_role'] != previous
        previous=p['fake_hreflang_role'];roles.append(previous)
    assert {'lang','locale'}.issubset(roles)


def test_one_row_refresh_is_idempotent_and_exact_plan_executes(pool,monkeypatch):
    from copy import deepcopy
    from app import reglue_title_h1
    monkeypatch.setattr(reglue_title_h1,'finish',lambda *args:True)
    db,sites,remotes,job=make_preview(pool,4)
    plans=[p for g in job.result['groups'] for p in g.get('plans',[])]
    row=next(p for p in plans if p['canonical_mode']=='internal')
    other={p['site_id']:deepcopy(p) for p in plans if p!=row}
    before=deepcopy(row);request=uuid4()
    pilot.refresh_row(db,job.id,row['site_id'],request,USER)
    changed=next(p for g in job.result['groups'] for p in g.get('plans',[]) if p['site_id']==row['site_id'])
    assert changed['alternateMarkup']!=before['alternateMarkup']
    assert changed['new_main']==before['new_main']
    for p in [p for g in job.result['groups'] for p in g.get('plans',[]) if p['site_id']!=row['site_id']]:assert p==other[p['site_id']]
    digest=auto.digest(job.result)
    pilot.refresh_row(db,job.id,row['site_id'],request,USER)
    assert auto.digest(job.result)==digest
    assert all(not r.calls for r in remotes.values())
    pilot.start(db,job.id,USER);sent=[];launch.execute_step(db,job.id,sent.append)
    runs=[db.get(models.AutoReglueRun,id) for id in sent];finish(db,runs)
    assert remotes[row['site_id']].data['head']['alternateMarkup']==changed['alternateMarkup']
    with pytest.raises(ValueError):pilot.refresh_row(db,job.id,row['site_id'],uuid4(),USER)


def test_space_ban_all_geos_roots_subdomains_manual_and_stock(pool):
    from app.domain_transfer_policy import banned_domains,set_ban
    from app import reglue_reserves as stock
    db,source,target,remotes,add=pool
    for s in (source,target):
        assert banned_domains(db,s,['new.space','az.new.space','www.NEW.SPACE.'])=={'new.space':True,'az.new.space':True,'www.NEW.SPACE.':True}
        assert not banned_domains(db,s,['space.example.com'])['space.example.com']
        with pytest.raises(ValueError,match='БАН'):set_ban(db,s,'new.space',False,'test')
    imported=stock.import_domains(db,'never.space','drop','','test')
    assert not imported['added'] and imported['errors']
    with pytest.raises(ValueError,match='БАН'):
        network.require_domain({'domains':['new.space'],'canon':'old.test'},'new.space')


def test_within_network_preview_can_reserve_exact_reviewed_plan(pool,monkeypatch):
    monkeypatch.setattr("app.reglue_title_h1.finish",lambda *args:True)
    db,source,target,remotes,add=pool
    source.project_status=target.project_status='working';db.commit()
    cfg=auto.config(db);cfg.execution_mode='within_network';cfg.scheme_mode='locale_base';auto.save_config(db,cfg)
    sites=[add(f'local-{i}.test',free=2,brand='Test',geo='PL') for i in range(4)]
    for s in sites:
        s.cache_language='pl'
        auto.save_config(db,auto.ProjectConfig(enabled=True,domain_layout="root_main",parent_kind="newreg",create_fake_main=True),s.id)
    db.commit();job=pilot.create(db,uuid4(),USER)
    launch.execute_step(db,job.id,lambda _:pytest.fail('preview writes'))
    assert job.status=='completed'
    ready=[r for r in pilot.view(db,job)['items'] if r['status']=='ready']
    assert ready,job.result
    pilot.start(db,job.id,USER);sent=[]
    launch.execute_step(db,job.id,sent.append)
    assert len(sent)==len(ready),[(r['status'],r.get('reason')) for r in job.result['items'].values()]
    finish(db,[db.get(models.AutoReglueRun,id) for id in sent])


def test_refresh_no_alternates_row_changes_path_preserving_quota(pool):
    from copy import deepcopy
    db,sites,remotes,job=make_preview(pool,20)
    p=next(p for g in job.result['groups'] for p in g.get('plans',[]) if p.get('without_alternates'))
    old=deepcopy(p)
    pilot.refresh_row(db,job.id,p['site_id'],uuid4(),USER)
    new=next(p for g in job.result['groups'] for p in g.get('plans',[]) if p['site_id']==old['site_id'])
    assert new['fake_main_path']!=old['fake_main_path'] and not new['enableAlternates']
    assert new['new_main']==old['new_main'] and new['canonical_mode']=='self'
    assert job.result['variation_summary']['without_alternates']==2


@pytest.mark.parametrize('selected',[False,True])
def test_refresh_redetects_headings_and_regenerates_only_selected_draft(pool,monkeypatch,selected):
    from copy import deepcopy
    from app import reglue_title_h1 as rewrite
    db,sites,remotes,job=make_preview(pool,10)
    all_plans=lambda:[p for g in job.result['groups'] for p in g.get('plans',[])]
    old=deepcopy(next(p for p in all_plans() if bool(p.get('rewrite_title_h1'))==selected and not p.get('without_alternates')))
    neighbours={p['site_id']:deepcopy(p) for p in all_plans() if p['site_id']!=old['site_id']}
    remote=remotes[old['site_id']]
    homepage=remote.data['data']['pages'][0]
    homepage['title']='Updated Casino Brand title'
    homepage['content']['blocks'][0]['data']['text']='Casino Brand fresh games online'
    generated=[]
    def generate(db,site,request,**kwargs):
        generated.append(request)
        assert kwargs['project']['data']['pages'][0]==homepage
        return {'draft_id':str(uuid4()),'title_before':homepage['title'],'title_after':'Casino Brand title updated',
            'h1_before':'Casino Brand fresh games online','h1_after':'Casino Brand online games'}
    monkeypatch.setattr(rewrite,'prepare_preview',generate)
    request=uuid4();pilot.refresh_row(db,job.id,old['site_id'],request,USER)
    new=next(p for p in all_plans() if p['site_id']==old['site_id'])
    assert new['title_h1_current']['title']==homepage['title']
    assert new['title_h1_current']['h1']=='Casino Brand fresh games online'
    assert new['alternateMarkup']!=old['alternateMarkup']
    assert new['new_main']==old['new_main'] and new['rewrite_title_h1']==selected
    assert len(generated)==int(selected)
    if selected:assert new['title_h1_preview']['draft_id']!=old['title_h1_preview']['draft_id']
    assert {p['site_id']:p for p in all_plans() if p['site_id']!=old['site_id']}==neighbours
    saved=deepcopy(job.result)
    remote.data['data']['pages'][0]['title']='Later change'
    pilot.refresh_row(db,job.id,old['site_id'],request,USER)
    assert job.result==saved and len(generated)==int(selected)
    assert all(not r.calls for r in remotes.values())
    assert not list(db.scalars(__import__('sqlalchemy').select(models.AutoReglueRun)))


@pytest.mark.parametrize('failure',['main_changed','pages_missing'])
def test_refresh_invalid_remote_keeps_reviewed_plan_and_receipt(pool,failure):
    from copy import deepcopy
    from app.cross_reglue_batch import key
    db,sites,remotes,job=make_preview(pool,4)
    before=deepcopy(job.result)
    group=next(g for g in before['groups'] if g.get('plans'))
    ledger=db.get(models.AutoReglueConfig,key(group['batch_id']));receipt=deepcopy(ledger.value)
    old=group['plans'][0];remote=remotes[old['site_id']]
    if failure=='main_changed':remote.data['settings']['canon']='changed.test'
    else:remote.data['data']['pages']=[]
    with pytest.raises(network.NetworkConflict):pilot.refresh_row(db,job.id,old['site_id'],uuid4(),USER)
    assert job.result==before and ledger.value==receipt
    assert all(not r.calls for r in remotes.values())


def test_title_progress_is_durable_and_cancel_stops_before_next_draft(pool,monkeypatch):
    from copy import deepcopy
    db,sites,remotes,job=make_preview(pool,10)
    result=deepcopy(job.result);result.pop('variations_finalized',None)
    selected=[p for g in result['groups'] for p in g.get('plans',[]) if p.get('rewrite_title_h1')]
    for p in selected:p.pop('title_h1_preview',None);p.pop('title_h1_error',None)
    job.result=result;job.status='queued';db.commit()
    seen=[]
    def generate(db,plan,jid):
        seen.append(deepcopy(job.result['title_h1_progress']))
        plan['title_h1_preview']={'h1_before':'Casino Brand games','h1_after':'Casino Brand online'}
        # Simulates a restart arriving while the next provider request is active.
        if len(seen)==2:
            db.add(models.AutoReglueConfig(key=launch.cancel_key(job.id),value={'replacement':'new'}));db.commit()
    monkeypatch.setattr('app.reglue_title_h1.prepare_for_plan',generate)
    launch.execute_step(db,job.id,lambda _:pytest.fail('No reglues during planning'))
    assert seen==[{'done':0,'total':2},{'done':1,'total':2}]
    assert job.status=='cancelled'
    assert job.result['title_h1_progress']=={'done':1,'total':2}
    assert all(not r.calls for r in remotes.values())
