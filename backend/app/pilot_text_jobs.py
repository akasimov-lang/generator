"""Independent, durable Title/H1 and paragraph jobs; no Webdev writes here."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid5
from sqlalchemy import update
from app import models, auto_reglue as auto
from app.project_network import network_lock, NetworkConflict

KIND = 'pilot_text'
FIELDS = ('title_h1', 'paragraphs')


def independent_start(job):
    return bool(job.status in ('queued','completed') and job.result.get('variations_allocated') and job.result.get('parallel_texts'))


def generation(job):
    return str(job.payload.get('generation_id', job.id))


def fingerprint(plan):
    return auto.digest({k:v for k,v in plan.items() if k not in {
        'preview_token', *(field + suffix for field in FIELDS for suffix in ('_preview','_error'))}})


def identity(job, plan, field):
    return str(uuid5(UUID(generation(job)), f"pilot-text:{plan['site_id']}:{field}:{fingerprint(plan)}"))


def current(db, child):
    from app.mass_reglue_launch import KIND as EXECUTION, PREVIEW_KIND, cancel_key
    from app.pilot_replanning import pending
    parent = db.get(models.BackgroundJob, child.payload['parent_id'])
    if parent: db.refresh(parent)
    if (not parent or parent.kind not in (PREVIEW_KIND, EXECUTION) or parent.status != 'queued'
            or generation(parent) != child.payload['generation_id'] or pending(db,parent.id)
            or db.get(models.AutoReglueConfig,cancel_key(parent.id))): return None
    plan = next((p for g in parent.result['groups'] for p in g.get('plans',[])
                 if p['site_id']==child.payload['site_id']),None)
    row = parent.result['items'].get(child.payload['site_id'],{})
    if not plan or row.get('run_id') or row.get('status') in ('skipped','failed','cancelled'):
        return None
    if fingerprint(plan) != child.payload['fingerprint']: return None
    allowed = parent.payload.get('allowed')
    if allowed is not None and plan['site_id'] not in allowed: return None
    return parent


def sync(db, job, result):
    """Caller owns the parent lock. Only collect reviewed output for this generation."""
    from app.auto_pilot import describe
    from app.cross_reglue_batch import key
    from app.mass_reglue_launch import check_preview_cancelled
    check_preview_cancelled(db,job)
    progress = {field:dict(done=0,total=0,running=0,failed=0) for field in FIELDS}
    for group in result['groups']:
        changed = False
        for plan in group.get('plans',[]):
            plan_changed = False
            for field in FIELDS:
                if not plan.get('rewrite_'+field): continue
                stats = progress[field]; stats['total'] += 1
                if not plan.get(field+'_preview') and not plan.get(field+'_error'):
                    id = identity(job,plan,field)
                    child = db.get(models.BackgroundJob,id)
                    if not child:
                        child = models.BackgroundJob(id=id,kind=KIND,status='queued',payload={
                            'parent_id':job.id,'generation_id':generation(job),'site_id':plan['site_id'],
                            'field':field,'fingerprint':fingerprint(plan),'plan':deepcopy(plan)})
                        db.add(child)
                    if child.status in ('completed','failed'):
                        output = child.result or {}
                        if child.status=='completed' and output.get('preview'):
                            plan[field+'_preview'] = deepcopy(output['preview'])
                        else: plan[field+'_error'] = child.error or output.get('error') or 'Генерация не вернула текст.'
                        changed = True
                        plan_changed = True
                    elif child.status=='queued' and child.started_at:
                        stats['running'] += 1
                stats['done'] += bool(plan.get(field+'_preview') or plan.get(field+'_error'))
                stats['failed'] += bool(plan.get(field+'_error'))
            if plan_changed and not result['items'][plan['site_id']].get('run_id'):
                plan.pop('preview_token',None); plan['preview_token']=auto.digest(plan)
                result['items'][plan['site_id']].update(**describe(db,plan))
        if changed and group.get('batch_id'):
            ledger=db.get(models.AutoReglueConfig,key(group['batch_id']))
            if ledger: ledger.value={**ledger.value,'plans':deepcopy(group['plans'])}
    for field,stats in progress.items():result[field+'_progress']=stats
    result['parallel_texts']=True
    result['variations_finalized']=all(p['done']==p['total'] for p in progress.values())
    job.result=deepcopy(result);db.commit()
    return result['variations_finalized']


def execute(db, job_id):
    """One child lock spans generation. The parent is never locked during AI I/O."""
    try:
        with network_lock(db,'pilot-text:'+str(job_id)):
            child=db.get(models.BackgroundJob,str(job_id))
            if not child or child.kind!=KIND or child.status!='queued':return {'status':'skipped'}
            if not current(db,child):
                child.status='cancelled';child.finished_at=datetime.now(timezone.utc);db.commit()
                return {'status':'cancelled'}
            child.started_at=child.started_at or datetime.now(timezone.utc)
            db.execute(update(models.BackgroundJob).where(models.BackgroundJob.id==child.payload['parent_id'],
                models.BackgroundJob.status=='queued').values(dispatched_at=None))
            db.commit()
            plan=deepcopy(child.payload['plan']);field=child.payload['field']
            if field=='title_h1':
                from app.reglue_title_h1 import prepare_for_plan
            elif field=='paragraphs':
                from app.reglue_paragraphs import prepare_for_plan
            else:raise ValueError('Неизвестный вид генерации.')
            try:
                prepare_for_plan(db,plan,child.payload.get('draft_request_id') or child.payload['generation_id'])
                from app.auto_pilot import heading_mode_ready, paragraphs_ready
                ready = (heading_mode_ready(db,plan,plan.get('title_rewrite_mode','minimal'))
                         if field=='title_h1' else paragraphs_ready(db,plan))
                if not ready and not plan.get(field+'_error'):
                    plan[field+'_error']='Текст не прошёл проверку выбранного режима. Обновите генерацию проекта.'
            except Exception:
                db.rollback()
                # Do not strand the parent or expose provider responses/credentials.
                plan[field+'_error']='Не удалось завершить генерацию текста. Обновите генерацию проекта.'
            if not current(db,child):child.status='cancelled';child.result={}
            else:
                child.result={'preview':plan.get(field+'_preview'),'error':plan.get(field+'_error')}
                child.error=plan.get(field+'_error')
                child.status='completed' if child.result.get('preview') and not child.error else 'failed'
            child.finished_at=datetime.now(timezone.utc)
            db.execute(update(models.BackgroundJob).where(models.BackgroundJob.id==child.payload['parent_id'],
                models.BackgroundJob.status=='queued').values(dispatched_at=None))
            db.commit()
            return {'status':child.status}
    except NetworkConflict:
        db.rollback();return {'status':'busy'}
