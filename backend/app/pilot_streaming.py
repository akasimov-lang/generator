"""Run approved network plans and reviewed text publication independently."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid5
import httpx
from app import models, auto_reglue as auto, mass_reglue_launch as launch
from app.project_network import NetworkConflict
from app.project_cache import ProjectCacheError


def components(plans):
    """A shared donor/recipient must be reserved together before any network write."""
    groups=[]
    for plan in plans:
        sites={plan['site_id'],plan.get('source_site_id',plan['site_id'])}
        joined=[g for g in groups if sites & g[0]]
        members=[plan]
        for group in joined:
            sites |= group[0];members.extend(group[1]);groups.remove(group)
        groups.append((sites,members))
    return [members for _,members in groups]


def text_ready(db,job,plan):
    from app.auto_pilot import heading_mode_ready, paragraphs_ready
    return heading_mode_ready(db,plan,job.payload.get('title_rewrite_mode','minimal')) and paragraphs_ready(db,plan)


def execute(db,job,send):
    from app.pilot_text_jobs import sync
    from app.pilot_content_publication import enabled, attach, states
    independent_content = enabled(job)
    from app.pilot_weekly import exclude
    from app.mass_action_scope import constrain
    from app.pilot_versions import append_version
    result=deepcopy(job.result)
    db.info['manual_pilot_job_id']=job.id
    db.info['auto_pilot_preview']=False
    db.info['prefer_own_domains']=True
    job.started_at=job.started_at or datetime.now(timezone.utc)
    def save():
        job.result=deepcopy(result);db.commit()
    exclude(db,result,job=job)
    sync(db,job,result)
    groups={p['site_id']:g for g in result['groups'] for p in g.get('plans',[])}
    plans=[p for g in result['groups'] for p in g.get('plans',[])]
    for group_plans in components(plans):
        pending=[p for p in group_plans if not result['items'][p['site_id']].get('run_id')
                 and result['items'][p['site_id']]['status'] not in launch.TERMINAL|{'skipped'}]
        if not pending:continue
        failed=next((p for p in group_plans if (not independent_content and (p.get('title_h1_error') or p.get('paragraphs_error')))
                     or result['items'][p['site_id']]['status'] in {'failed','skipped','cancelled'}),None)
        if failed:
            for p in pending:
                reason=failed.get('title_h1_error') or failed.get('paragraphs_error') or 'Связанный проект исключён или завершился ошибкой.'
                result['items'][p['site_id']].update(status='failed',reason=reason,phase='content_failed')
            save();continue
        waiting=[] if independent_content else [p for p in pending if not text_ready(db,job,p)]
        if waiting:
            for p in pending:
                fields=[label for field,label in (('title_h1','Title/заголовков'),('paragraphs','абзацев'))
                        if p.get('rewrite_'+field) and not p.get(field+'_preview')]
                result['items'][p['site_id']].update(status='generating' if fields else 'waiting',
                    phase='content_generation' if fields else 'content_dependency',
                    reason=('Генерация '+ ' и '.join(fields)+'. Публикация после готовности.' if fields else 'Ждём тексты связанного проекта для общего резервирования доменов.'))
            save();continue
        try:
            # Reserve every part of the connected component before dispatching any of it.
            batches=defaultdict(list)
            for p in pending:batches[groups[p['site_id']].get('batch_id') or p['site_id']].append(p)
            for batch in batches.values():
                group=groups[batch[0]['site_id']]
                constrain(db,group['filter'],set(job.payload['allowed']) if job.payload['allowed'] is not None else None)
                db.info.pop('mass_participant_ids',None)
                for p in batch:
                    site=db.get(models.Site,p['site_id']);db.refresh(site)
                    if reason:=launch.skip_reason(db,site):raise NetworkConflict(reason)
                entries=[{'site_id':p['site_id'],'request_id':str(uuid5(UUID(job.id),p['site_id'])),
                          'preview_token':p['preview_token']} for p in batch]
                if group.get('batch_id'):
                    from app.cross_reglue_batch import reserve
                    fresh=reserve(db,group['batch_id'],entries,job.payload['actor'])
                else:
                    fresh=[auto.prepare_run(db,db.get(models.Site,e['site_id']),UUID(e['request_id']),e['preview_token'],
                        job.payload['actor'],'mass',saved_plan=p) for e,p in zip(entries,batch)]
                for run,_ in fresh:
                    run.plan={**run.plan,'list_launch_id':job.id}
                    if independent_content: attach(db, run)
                    result['items'][run.site_id].update(run_id=run.id,status=run.status,reason=None,phase='prepared')
                    append_version(job,result,next(p for p in batch if p['site_id']==run.site_id),job.payload.get('generation_id',job.id))
                save()
        except (ValueError,NetworkConflict,ProjectCacheError,httpx.HTTPError) as error:
            db.rollback()
            for p in pending:
                run=db.get(models.AutoReglueRun,str(uuid5(UUID(job.id),p['site_id'])))
                if run and run.status in ('planned','queued'):
                    run.status='failed';run.message=str(error)[:1500]
                result['items'][p['site_id']].update(status='failed',reason=str(error)[:1500],
                    **({'run_id':run.id} if run else {}))
            save()
    for row in result['items'].values():
        if row.get('completed_elsewhere'):continue
        run=db.get(models.AutoReglueRun,row.get('run_id')) if row.get('run_id') else None
        if not run:continue
        if independent_content: attach(db, run)
        row.update(status=run.status,reason=run.message)
        if run.status=='queued':
            last=launch.utc(result['sent'].get(run.id))
            if not last or last<datetime.now(timezone.utc)-timedelta(minutes=1):
                try:
                    send(run.id);result['sent'][run.id]=datetime.now(timezone.utc).isoformat()
                except Exception:job.error='Очередь временно недоступна. Отправка будет повторена.'
    for group in result['groups']:
        group['status']='done' if all(result['items'][id]['status'] in launch.TERMINAL|{'skipped'} for id in group['site_ids']) else 'waiting'
    content_pending = independent_content and (any(s.status == 'queued' for s in states(db, job.id)) or not result.get('variations_finalized'))
    if not content_pending and all(row['status'] in launch.TERMINAL|{'skipped'} for row in result['items'].values()):
        job.status='completed';job.finished_at=datetime.now(timezone.utc);job.error=None
    save()
    return {'status':job.status}
