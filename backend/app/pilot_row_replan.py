"""Prepare one alternative in a launched report; publication needs its own start."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid5
from sqlalchemy import select
from app import models, auto_reglue as auto, mass_reglue_launch as launch
from app.project_network import NetworkConflict, network_lock

KIND='pilot_row_replan'


def eligible(db, parent, site_id):
    row=parent.result.get('items',{}).get(site_id)
    if parent.kind!=launch.KIND or not parent.payload.get('auto_pilot') or not row:
        raise NetworkConflict('Обновление доступно для проекта в запущенном плане.')
    if row.get('completed_elsewhere') or row.get('status')=='completed':
        raise NetworkConflict('Проект уже выполнен. Его результат сохраняется.')
    run=db.get(models.AutoReglueRun,row['run_id']) if row.get('run_id') else None
    if run:
        if run.status not in {'failed','cancelled'}:
            raise NetworkConflict('Сначала дождитесь результата или отмените текущую попытку.')
        operations=list(db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.site_id.in_([site_id,run.plan.get('source_site_id',site_id)]))))
        if any(op.request_payload.get('auto_run_id')==run.id for op in operations):
            raise NetworkConflict('У прежней попытки есть операции Webdev. Сначала подтвердите её фактический результат.')
    site=db.get(models.Site,site_id)
    if reason:=launch.skip_reason(db,site):raise NetworkConflict(reason)
    return row


def request(db, parent_id, site_id, request_id, user):
    from app.auto_pilot import get
    with network_lock(db,'mass-reglue-list:'+str(parent_id)):
        parent=get(db,parent_id,user);site_id=str(site_id);request_id=str(request_id)
        row=eligible(db,parent,site_id)
        existing=db.get(models.BackgroundJob,request_id)
        if existing:
            if existing.kind!=KIND or existing.payload.get('parent_id')!=parent.id or existing.payload.get('site_id')!=site_id or existing.payload.get('actor')!=user['username']:
                raise ValueError('Идентификатор запроса уже занят.')
            return parent
        current=(row.get('alternative') or {}).get('id')
        child=db.get(models.BackgroundJob,current) if current else None
        if child and child.status=='queued':return parent
        child=models.BackgroundJob(id=request_id,kind=KIND,status='queued',payload={
            'parent_id':parent.id,'site_id':site_id,'actor':user['username'],'allowed':user.get('allowed_site_ids'),
            'policy':{'stock':False,'former_main_days':14}},result={})
        db.add(child)
        result=deepcopy(parent.result)
        result['items'][site_id]['alternative']={'id':request_id,'status':'queued'}
        parent.result=result;db.commit()
        return parent


def prepare(db, child, parent):
    from app import project_network as network, cross_reglue as cross
    from app.domain_transfer_policy import geo_key, domain_key
    from app.pilot_domain_reuse import candidate
    from app.mass_action_scope import constrain, MassActionFilter
    from app.pilot_donors import grants
    target=db.get(models.Site,child.payload['site_id'])
    filters=MassActionFilter(brand=target.brand,geo=geo_key(target.cache_geo))
    constrain(db,filters,child.payload.get('allowed'),[target])
    db.info.pop('mass_participant_ids',None)
    db.info.update(pilot_job_id=parent.id,pilot_alternative_id=child.id,auto_pilot_preview=True,pilot_allow_stock_drops=False)
    state=network.read_network(db,target);sites={target.id:target};states={target.id:state}
    donors=grants(db,parent.id)
    for source in db.scalars(select(models.Site).where(models.Site.is_active.is_(True),models.Site.project_status=='mass_actions')):
        if source.id==target.id or (child.payload.get('allowed') is not None and source.id not in child.payload['allowed']):continue
        try:cross.require_pair(source,target)
        except ValueError:continue
        if source.hidden_from_projects or (source.reglue_participation is False and source.id not in donors) or auto.config(db,source.id).scope=='personal' or auto.active_run(db,source.id):continue
        try:
            states[source.id]=network.read_network(db,source);sites[source.id]=source
        except Exception:continue
    neighbours=[p for g in parent.result['groups'] for p in g.get('plans',[]) if p['site_id']!=target.id]
    used={domain_key(p['new_main']) for p in neighbours}
    for other in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind==KIND,models.BackgroundJob.status.in_(['queued','completed']))):
        if other.id!=child.id and (other.result or {}).get('plan') and not other.payload.get('started_at'):
            used.add(domain_key(other.result['plan']['new_main']))
    plan=candidate(db,auto.config(db),target,states,sites,used,neighbours)
    old=next((p for g in parent.result['groups'] for p in g.get('plans',[]) if p['site_id']==target.id),{})
    old=old or parent.payload.get('preserved_target_plans',{}).get(target.id,{})
    for key in ('rewrite_paragraphs','paragraphs_preview','short_h1','redirect_old_main','internal_pages'):
        if key in old:plan[key]=deepcopy(old[key])
    plan['rewrite_title_h1']=True
    plan['title_rewrite_mode']=parent.payload.get('title_rewrite_mode','minimal')
    if plan['title_rewrite_mode']=='mixed':plan['title_rewrite_mode']=old.get('title_rewrite_mode','minimal')
    from app.pilot_schemes import assign
    assign(db,[plan],fixed=neighbours,exclude={target.id:old.get('scheme_variant')})
    # A personal row refresh explicitly requests new metadata; paragraphs remain
    # a separate durable generation and do not block the network preview.
    plan.update(pilot_alternative_id=child.id,alternative_parent_id=parent.id,batch_id=child.id)
    plan.pop('preview_token',None);plan['preview_token']=auto.digest(plan)
    return plan, filters.model_dump()


def execute(db, job_id):
    try:
        with network_lock(db,'pilot-row-replan:'+str(job_id)):
            child=db.get(models.BackgroundJob,str(job_id))
            if not child or child.kind!=KIND or child.status!='queued':return {'status':'skipped'}
            try:
                from app.auto_pilot import get
                user={'username':child.payload['actor'],'allowed_site_ids':child.payload.get('allowed')}
                with network_lock(db,'mass-reglue-list:'+child.payload['parent_id']):
                    parent=get(db,child.payload['parent_id'],user)
                    row=eligible(db,parent,child.payload['site_id'])
                    if (row.get('alternative') or {}).get('id')!=child.id:
                        child.status='cancelled';db.commit();return {'status':'cancelled'}
                    child.started_at=child.started_at or datetime.now(timezone.utc);db.commit()
                    if not (child.result or {}).get('plan'):
                        info=dict(db.info)
                        try: plan,filters=prepare(db,child,parent)
                        finally: db.info.clear();db.info.update(info)
                        child.result={'plan':plan,'filter':filters,'phase':'headings'}
                        child.dispatched_at=None;db.commit()
                        return {'status':'queued','phase':'headings'}
                # Metadata uses the short-generation queue, without holding the report lock.
                plan=deepcopy(child.result['plan'])
                from app.reglue_title_h1 import prepare_for_plan
                prepare_for_plan(db,plan,child.id,force=True)
                if plan.get('title_h1_error'):raise ValueError(plan['title_h1_error'])
                plan.pop('preview_token',None);plan['preview_token']=auto.digest(plan)
                with network_lock(db,'mass-reglue-list:'+child.payload['parent_id']):
                    db.refresh(parent);row=eligible(db,parent,child.payload['site_id'])
                    if (row.get('alternative') or {}).get('id')!=child.id:raise NetworkConflict('Вариант заменён новым запросом.')
                    from app.cross_reglue_batch import key, validate
                    validate([plan])
                    receipt=db.get(models.AutoReglueConfig,key(child.id))
                    if not receipt:receipt=models.AutoReglueConfig(key=key(child.id));db.add(receipt)
                    receipt.value={'created_by':child.payload['actor'],'plans':[deepcopy(plan)],'skipped':[],'run_ids':{},'filter':None,'distribution':{}}
                    child.result={**child.result,'plan':plan,'phase':'ready'};child.status='completed';child.error=None
                    alternative={'id':child.id,'status':'ready','policy':child.payload['policy']}
                    result=deepcopy(parent.result);result['items'][child.payload['site_id']]['alternative']=alternative
                    parent.result=result;child.finished_at=datetime.now(timezone.utc);db.commit()
                return {'status':'completed'}
            except Exception as error:
                db.rollback();db.refresh(child)
                with network_lock(db,'mass-reglue-list:'+child.payload['parent_id']):
                    parent=db.get(models.BackgroundJob,child.payload['parent_id']);db.refresh(parent)
                    child.status='failed';child.error=str(error)[:1500];child.finished_at=datetime.now(timezone.utc)
                    result=deepcopy(parent.result)
                    if (result['items'][child.payload['site_id']].get('alternative') or {}).get('id')==child.id:
                        result['items'][child.payload['site_id']]['alternative']={'id':child.id,'status':'failed','error':child.error}
                        parent.result=result
                    db.commit()
                return {'status':'failed'}
    except NetworkConflict:
        db.rollback();return {'status':'busy'}


def start(db,parent_id,site_id,request_id,user):
    from app.auto_pilot import get, describe
    site_id=str(site_id)
    with network_lock(db,'mass-reglue-list:'+str(parent_id)):
        parent=get(db,parent_id,user)
        child=db.get(models.BackgroundJob,str(request_id))
        if not child or child.kind!=KIND or child.payload.get('parent_id')!=parent.id or child.payload.get('site_id')!=site_id or child.payload.get('actor')!=user['username']:
            raise ValueError('Подготовленный вариант не найден.')
        if child.payload.get('started_at'):return parent
        row=eligible(db,parent,site_id)
        if child.status!='completed' or (row.get('alternative') or {}).get('id')!=child.id:raise NetworkConflict('Дождитесь подготовки актуального варианта.')
        plan=deepcopy(child.result['plan'])
        if auto.digest(auto.config(db).model_dump())!=plan['config_hash']:raise NetworkConflict('Настройки изменились. Обновите план проекта.')
        from app.pilot_domain_reuse import validate
        validate(db,plan)
        result=deepcopy(parent.result)
        result.setdefault('alternative_history',[]).append({'site_id':site_id,'at':datetime.now(timezone.utc).isoformat(),'row':deepcopy(row),
            'plans':[deepcopy(p) for g in result['groups'] for p in g.get('plans',[]) if p['site_id']==site_id]})
        for group in result['groups']:
            group['plans']=[p for p in group.get('plans',[]) if p['site_id']!=site_id]
            group['site_ids']=[id for id in group['site_ids'] if id!=site_id]
        result['groups'].append({'filter':child.result['filter'],'site_ids':[site_id],'plans':[plan],'batch_id':child.id,'status':'previewed'})
        row=result['items'][site_id]
        row.update(run_id=None,status='ready',reason=None,phase='prepared',alternative={'id':child.id,'status':'started'},**describe(db,plan))
        from app.pilot_versions import append_version
        append_version(parent,result,plan,child.id)
        result['parallel_texts']=True
        parent.result=result;parent.payload={**parent.payload,'streaming_start':True,'manual_start':True}
        parent.status='queued';parent.finished_at=None;parent.dispatched_at=None
        child.payload={**child.payload,'started_at':datetime.now(timezone.utc).isoformat()}
        db.commit();return parent


def run_id(parent, plan):
    return str(uuid5(UUID(plan.get('pilot_alternative_id') or parent.id),plan['site_id']))


def authorized_run(db,parent,run):
    child_id=run.plan.get('pilot_alternative_id')
    if not child_id:return False
    child=db.get(models.BackgroundJob,child_id)
    return bool(child and child.kind==KIND and child.payload.get('parent_id')==parent.id
        and child.payload.get('site_id')==run.site_id and child.payload.get('started_at')
        and child.payload.get('actor')==run.initiator and run.id==run_id(parent,run.plan))
