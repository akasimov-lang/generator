"""Scoped, journalled one-time reglue. Run inside backend with PYTHONPATH=/app.
prepare is read-only remotely. apply never repeats an ambiguous write.
rollback restores the saved settings version, refusing concurrent edits.
"""
import argparse
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid5

import httpx
from sqlalchemy import select
from app import models
from app.core.config import get_settings
from app.db import SessionLocal
from app.fake_main import normalize_fake_path, fake_paths
from app.network_state import project_network_state, observe_network, domain_name, validate_markup
from app.project_network import network_lock
from app.network_indexing import queue_indexing, submit_network_indexing

BATCH = '7b9d5b4b-5a1c-4904-b3dc-c36a8b0cae47'
HEAD = ('enableCanonical', 'canonicalDefaultMarkup', 'canonicalFakeMainMarkup', 'enableAlternates', 'alternateMarkup')

def now(): return datetime.now(timezone.utc).isoformat()
def snap(p): return copy.deepcopy({k: p[k] for k in ('settings', 'head')})
def desired(p):
    return dict(enableCanonical=True, canonicalDefaultMarkup=p['canonical_other_pages'],
                canonicalFakeMainMarkup=p['canonical_template'], enableAlternates=True, alternateMarkup=p['alternate_markup'])
def matches(project, plan):
    s = project_network_state(project)
    return (s['canon'] == plan['new_main'] and s['fake_main_enabled'] and
            s['fake_main_current'] == plan['fake_path'] and plan['fake_path'] in s['fake_main_paths'] and
            all(project['head'].get(k) == v for k,v in desired(plan).items()))
def validate(project, plan, site):
    s = project_network_state(project)
    assert not plan['excluded'] and plan['source_ids'] not in ('276','2367'), 'Excluded project'
    assert site.name == plan['project'] and site.cache_server_ip == plan['server'], 'Identity/server changed'
    assert site.project_status == 'mass_actions', 'Project no longer in mass_actions'
    assert s['canon'] == plan['old_main'], 'Main changed since approved model'
    assert all(k in project.get('head', {}) for k in HEAD), 'Incomplete head snapshot'
    assert all(k in project['settings'] for k in ('canon','prev','reserve','alternate','redirects')), 'Incomplete settings snapshot'
    for d in (plan['new_main'],plan['alternate_domain']):
        assert d in s['domains'], 'Planned domain absent from current network: '+d
        assert d not in s['amp_domains'] and (site.domain_types or {}).get(d) != 'amp', 'AMP target'
    path = normalize_fake_path(plan['fake_path'])
    occupied = s['fake_main_paths'] + s['content_page_paths'] + [s['fake_main_current']] + (site.network_state or {}).get('fake_main_history',[])
    assert path not in occupied, 'Planned fake path now occupied'
    validate_markup(plan['alternate_markup'])
    assert plan['canonical_main_and_fake'] == 'https://'+plan['new_main']+path
    return s

def settings_equal(a,b):
    # update-value persists routing metadata folder even if absent before.
    return {k:v for k,v in a.items() if k!='folder'}=={k:v for k,v in b.items() if k!='folder'}

def restore_values(before, after, current):
    # Refuse overwriting edits made after this operation, including unrelated settings.
    assert current == after, 'Settings changed after operation; rollback requires reconciliation'
    extra = set(after['settings']) - set(before['settings']) - {'folder'}
    assert not extra, 'Webdev introduced settings requiring explicit removal: '+','.join(sorted(extra))
    return {k:v for k,v in before['settings'].items() if after['settings'].get(k) != v}, {k:before['head'][k] for k in HEAD}

class Remote:
    def __init__(self, site, token):
        c=get_settings()
        self.base='https://'+site.cache_server_ip+'.'+c.alfan_url.strip('/')
        self.folder=site.name
        self.client=httpx.Client(timeout=httpx.Timeout(60,connect=12),headers={'Authorization':'Bearer '+token})
    def project(self):
        r=self.client.get(self.base+'/projects/one/'+quote(self.folder,safe=''));r.raise_for_status()
        p=r.json();assert isinstance(p.get('settings'),dict) and isinstance(p.get('head'),dict), 'Missing settings/head'
        return p
    def request(self,method,path,payload):
        r=self.client.request(method,self.base+path,json=payload);r.raise_for_status()
        try:
            body=r.json()
            if isinstance(body,str):
                try:body=json.loads(body)
                except ValueError:pass
        except ValueError:body=None
        if isinstance(body,dict) and (body.get('error') or body.get('errors') or body.get('success') is False):
            raise ValueError('Webdev rejected request: '+str(body)[:600])
        return body
    def close(self):self.client.close()

def save(db,op,**values):
    op.request_payload={**op.request_payload,**values};db.commit()

def step(db,op,remote,name,method,path,payload,check):
    steps=copy.deepcopy(op.request_payload.get('steps',{}))
    if name in steps:
        if check(remote.project()):return
        raise RuntimeError('Unconfirmed prior write '+name+'; automatic repeat blocked')
    steps[name]={'status':'sending','at':now(),'method':method,'path':path,'payload':payload}
    save(db,op,steps=steps)
    error=None
    try:remote.request(method,path,payload)
    except Exception as e:error=type(e).__name__+': '+str(e)[:700]
    for attempt in range(6):
        p=remote.project()
        if check(p):
            steps[name].update(status='confirmed',confirmed_at=now(),transport_warning=error)
            save(db,op,steps=steps,after=snap(p));return
        if attempt<5:time.sleep(2)
    steps[name].update(status='unconfirmed',error=error or 'Read-back mismatch')
    save(db,op,steps=steps,after=snap(p))
    raise RuntimeError('Write not confirmed: '+name+'; '+str(error))

def prepare(db,site,remote,plan,opid):
    existing=db.get(models.NetworkOperation,opid)
    if existing:return existing
    p=remote.project();validate(p,plan,site)
    pending=db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id==site.id,models.NetworkOperation.status.in_(['pending','unknown','running','prepared','partial']))).all()
    assert not pending, 'Another unresolved operation exists'
    if plan['new_main'] != plan['old_main']:
        check=remote.request('POST','/projects/check-domain',{'domain':plan['new_main']})
        assert isinstance(check,dict) and check.get('reachable') is True, 'Target domain is not reachable: '+str(check)[:300]
    op=models.NetworkOperation(id=opid,site_id=site.id,action='reglue',status='prepared',initiator='anton',
        request_payload={'batch_id':BATCH,'source_domain':plan['old_main'],'reserve':plan['new_main'],
        'plan':plan,'before':snap(p),'prepared_at':now(),'steps':{},'rollback_command':'one_time_reglue.py rollback --operation '+opid},
        message='Одноразовый массовый переклей: сохранена исходная версия настроек. Запись ещё не выполнялась.')
    db.add(op);db.commit();return op

def apply(db,site,remote,op):
    if op.request_payload.get('rolled_back_by'):return
    if op.status=='confirmed':return
    assert op.status=='prepared', 'Only prepared operations may start; use reconcile for interrupted runs'
    plan=op.request_payload['plan'];before=op.request_payload['before'];p=remote.project()
    assert snap(p)==before, 'Settings changed after preparation'
    validate(p,plan,site)
    op.status='running';op.message='Выполняется массовый переклей; исходная версия сохранена для отката.';db.commit()
    alt=copy.deepcopy(p['settings']['alternate'] or {})
    alt.update(fakeMain=[*(alt.get('fakeMain') or []),plan['fake_path']],currentFakeMain=plan['fake_path'],enableDynamicRoutes=True)
    step(db,op,remote,'fake','POST','/projects/update-value',{'folder':site.name,'alternate':alt},lambda q:q['settings'].get('alternate')==alt)
    if plan['new_main']!=plan['old_main']:
        reserve={'reserve':plan['new_main']}
        if 'reserveOption' in before['settings']:reserve['reserveOption']=plan['new_main']
        step(db,op,remote,'reserve','POST','/projects/update-value',{'folder':site.name,**reserve},lambda q:all(q['settings'].get(k)==v for k,v in reserve.items()))
        step(db,op,remote,'reglue','POST','/projects/update-reglue',{'folder':site.name,'reserve':plan['new_main'],'trigger':'webdev:settings','initiator':get_settings().project_cache_username},lambda q:domain_name(q['settings'].get('canon'))==plan['new_main'])
    head=desired(plan)
    step(db,op,remote,'head','PATCH','/projects/update-head',{'folder':site.name,**head},lambda q:all(q['head'].get(k)==v for k,v in head.items()))
    finish(db,site,remote,op)

def finish(db,site,remote,op):
    p=remote.project();plan=op.request_payload['plan']
    save(db,op,after=snap(p),checked_at=now())
    assert matches(p,plan), 'Final settings mismatch'
    state=observe_network(site,p);site.cache_canon=state['canon'];site.cache_domains=state['domains']
    op.status='confirmed';op.message=('Массовый переклей '+plan['old_main']+' → '+plan['new_main'] if plan['old_main']!=plan['new_main'] else 'Main сохранён: '+plan['new_main'])+'; новый внутряк '+plan['fake_path']+', canonical и альтернейты проверены. Версия ДО сохранена; откат по операции '+op.id+'.'
    extra=set(p['settings'])-set(op.request_payload['before']['settings'])
    save(db,op,rollback_extra_settings=sorted(extra),completed_at=now())
    ix=queue_indexing(db,site,state,op.id,'anton');db.commit()
    save(db,op,indexing_operation_id=ix.id)

def rollback(db,site,remote,op):
    assert op.status in ('confirmed','partial'), 'Operation cannot be rolled back in this state'
    before=op.request_payload['before'];after=op.request_payload['after'];current=snap(remote.project())
    values,head=restore_values(before,after,current)
    rid=str(uuid5(UUID(op.id),'rollback'))
    assert not db.get(models.NetworkOperation,rid), 'Rollback receipt already exists; reconcile, do not resend'
    rev=models.NetworkOperation(id=rid,site_id=site.id,action='reglue',status='running',initiator='anton',request_payload={'rollback_of':op.id,'source_domain':after['settings']['canon'],'reserve':before['settings']['canon'],'before':current,'steps':{}},message='Возврат к сохранённой версии настроек.')
    db.add(rev);db.commit()
    if before['settings']['canon'] != after['settings']['canon']:
        target=before['settings']['canon']
        step(db,rev,remote,'reserve','POST','/projects/update-value',{'folder':site.name,'reserve':target},lambda q:q['settings'].get('reserve')==target)
        step(db,rev,remote,'reglue','POST','/projects/update-reglue',{'folder':site.name,'reserve':target,'trigger':'webdev:settings','initiator':get_settings().project_cache_username},lambda q:q['settings'].get('canon')==target)
    # Restore all original settings, including redirects and service-maintained chains.
    actual=remote.project()['settings']
    values={k:copy.deepcopy(v) for k,v in before['settings'].items() if actual.get(k)!=v and k!='folder'}
    step(db,rev,remote,'settings','POST','/projects/update-value',{'folder':site.name,**values},lambda q:settings_equal(q['settings'],before['settings']))
    step(db,rev,remote,'head','PATCH','/projects/update-head',{'folder':site.name,**head},lambda q:q['head']==before['head'])
    p=remote.project();assert settings_equal(p['settings'],before['settings']) and p['head']==before['head'], 'Rollback verification failed'
    state=observe_network(site,p);site.cache_canon=state['canon'];site.cache_domains=state['domains']
    rev.status='confirmed';rev.message='Переклей и настройки восстановлены из версии ДО; проверено чтением Webdev.'
    save(db,rev,after=snap(p),completed_at=now());save(db,op,rolled_back_by=rid)

def worker(plan,mode,token):
    opid=str(uuid5(UUID(BATCH),plan['site_id']))
    with SessionLocal() as db:
        site=db.get(models.Site,plan['site_id']);remote=Remote(site,token);owns_work=False
        try:
            with network_lock(db,site.id):
                owns_work=True
                op=prepare(db,site,remote,plan,opid)
                if op.request_payload.get('rolled_back_by'):
                    return {'site_id':site.id,'project':site.name,'operation_id':opid,'status':'rolled_back'}
                if mode=='apply':apply(db,site,remote,op)
                elif mode=='reconcile' and op.status in ('running','partial'):finish(db,site,remote,op)
                result={'site_id':site.id,'project':site.name,'operation_id':opid,'status':op.status}
            ixid=op.request_payload.get('indexing_operation_id')
            if ixid and mode!='prepare':
                submit_network_indexing(db,ixid);db.expire_all();ix=db.get(models.NetworkOperation,ixid)
                result.update(indexing_status=ix.status,indexing_task_id=ix.request_payload.get('task_id'))
            return result
        except Exception as e:
            db.rollback();op=db.get(models.NetworkOperation,opid)
            error=type(e).__name__+': '+str(e)[:1000]
            if owns_work and op and op.status=='running':
                op.status='partial';op.message='Требуется сверка: '+error
                try:save(db,op,after=snap(remote.project()),error=error)
                except Exception:db.commit()
            return {'site_id':plan['site_id'],'project':plan['project'],'operation_id':opid,'status':op.status if op else 'blocked','error':error}
        finally:remote.close()

def main():
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','apply','reconcile','export','rollback']);a.add_argument('--plan');a.add_argument('--operation');a.add_argument('--ids',default='');a.add_argument('--workers',type=int,default=3);a.add_argument('--offset',type=int,default=0);args=a.parse_args()
    if args.mode=='export':
        with SessionLocal() as db:
            ops=db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.request_payload['batch_id'].as_string()==BATCH)).all()
            data=[]
            for op in ops:
                item={k:getattr(op,k) for k in ('id','site_id','status','message','request_payload','created_at','updated_at')}
                ixid=op.request_payload.get('indexing_operation_id');ix=db.get(models.NetworkOperation,ixid) if ixid else None
                if ix:item['indexing']={k:getattr(ix,k) for k in ('id','status','message','request_payload')}
                related=db.scalars(select(models.NetworkOperation).where((models.NetworkOperation.request_payload['rollback_of'].as_string()==op.id) | (models.NetworkOperation.request_payload['correction_of'].as_string()==op.id))).all()
                item['related_operations']=[{k:getattr(v,k) for k in ('id','status','message','request_payload','created_at','updated_at')} for v in related]
                rid=op.request_payload.get('rolled_back_by')
                if rid:
                    item['rollback']=next((v for v in item['related_operations'] if v['id']==rid),None)
                    rixid=item['rollback']['request_payload'].get('indexing_operation_id') if item['rollback'] else None
                    rix=db.get(models.NetworkOperation,rixid) if rixid else None
                    if rix:item['rollback_indexing']={k:getattr(rix,k) for k in ('id','status','message','request_payload','response_status')}
                source_ids=[op.id,*[v['id'] for v in item['related_operations']]]
                receipts=db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.action=='indexing',models.NetworkOperation.request_payload['source_id'].as_string().in_(source_ids)).order_by(models.NetworkOperation.created_at)).all()
                item['indexing_history']=[{k:getattr(v,k) for k in ('id','status','message','request_payload','response_status','created_at')} for v in receipts]
                data.append(item)
            print(json.dumps({'batch_id':BATCH,'exported_at':now(),'operations':data},ensure_ascii=False,default=str));return
    cfg=get_settings()
    with httpx.Client(timeout=30) as c:
        r=c.post(cfg.project_cache_url.rstrip('/')+'/auth/login',json={'username':cfg.project_cache_username,'pass':cfg.project_cache_password});r.raise_for_status();token=r.json()['token']
    if args.mode=='rollback':
        with SessionLocal() as db:
            op=db.get(models.NetworkOperation,args.operation);site=db.get(models.Site,op.site_id);remote=Remote(site,token)
            try:
                with network_lock(db,site.id):rollback(db,site,remote,op)
            finally:remote.close()
        return
    plans=json.loads(Path(args.plan).read_text())['projects'];plans=[p for p in plans if not p['excluded']]
    plans=plans[args.offset:]
    if args.ids:plans=[p for p in plans if p['source_ids'] in args.ids.split(';')]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(worker,p,args.mode,token) for p in plans]):print(json.dumps(f.result(),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
