"""Resumable launch of a table selection, grouped by brand/GEO and saved in the DB."""
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid5
import httpx
from sqlalchemy import select
from app import models, auto_reglue as auto, project_network as network
from app.mass_action_scope import MassActionFilter, brand_key, constrain, matches
from app.domain_transfer_policy import geo_key
from app.project_cache import ProjectCacheError
from app.reglue_history import changed_this_week, utc, weekly_reason

KIND = 'mass_reglue_list'
PREVIEW_KIND = 'auto_pilot_preview'
PLANNER_VERSION = 6
TERMINAL = {'completed', 'failed', 'partial', 'cancelled'}


def manual_pilot_allowed(db, site_id, run=None):
    if run and run.plan.get('maintenance_repeat_id'):
        from app.maintenance_repeat import manual_allowed
        return manual_allowed(db, site_id, run)
    job_id=(run.plan.get('list_launch_id') if run else db.info.get('manual_pilot_job_id'))
    job=db.get(models.BackgroundJob,job_id) if job_id else None
    if not job or job.kind!=KIND or job.status!='queued' or not job.payload.get('manual_start') or not job.payload.get('auto_pilot') or not job.payload.get('launched_at'):
        return False
    if run:
        from app.pilot_row_replan import authorized_run
        if run.initiator!=job.payload['actor'] or run.plan.get('scheduled') or (run.id!=str(uuid5(UUID(job.id),site_id)) and not authorized_run(db,job,run)):
            return False
    return any(p['site_id']==site_id for g in job.result['groups'] for p in g.get('plans',[]))


def skip_reason(db, site, now=None):
    if not site or not site.is_active or site.hidden_from_projects: return 'Проект недоступен или неактивен.'
    if site.project_status != 'mass_actions': return 'Статус проекта отличается от «Массовые действия».'
    if site.reglue_participation is False: return 'Участвует в переклее: Нет.'
    if reason := weekly_reason(site, now): return reason
    if auto.config(db, site.id).scope == 'personal': return 'У проекта персональные настройки автопереклея.'
    if auto.active_run(db, site.id): return 'Уже есть незавершённый переклей или перенос.'
    return None


def enqueue(db, request_id, site_ids, actor, allowed=None, *, preview_only=False):
    kind = PREVIEW_KIND if preview_only else KIND
    ids = sorted(set(site_ids))
    if allowed is not None and not set(ids).issubset(allowed): raise ValueError('Некоторые проекты недоступны.')
    with network.network_lock(db, 'mass-reglue-list-start'):
        old = db.get(models.BackgroundJob, str(request_id))
        if old:
            if old.kind not in ({PREVIEW_KIND, KIND} if preview_only else {KIND}) or old.payload['site_ids'] != ids or old.payload['actor'] != actor:
                raise ValueError('Идентификатор запуска уже используется для другого списка.')
            return old
        job = initial_job(db, request_id, ids, actor, allowed, preview_only=preview_only)
        db.add(job); db.commit()
        return job


def initial_job(db, request_id, site_ids, actor, allowed=None, *, preview_only=False):
    """Build local planning state without inserting a second background job."""
    ids = sorted(set(site_ids))
    kind = PREVIEW_KIND if preview_only else KIND
    cfg = auto.config(db)
    if not cfg.enabled and not preview_only: raise ValueError('Включите «Разрешить запуск автопереклеев» и сохраните настройки.')
    if cfg.execution_mode == 'transfer_only': raise ValueError('Выберите режим переклея: текущий режим только переносит домены.')
    for job in db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind == KIND, models.BackgroundJob.status == 'queued')):
        if not preview_only and set(ids).intersection(job.payload['site_ids']):
            raise network.NetworkConflict('Часть списка уже включена в массовый запуск. Дождитесь его завершения.')
    sites = {s.id: s for s in db.scalars(select(models.Site).where(models.Site.id.in_(ids)))}
    if set(sites) != set(ids): raise ValueError('Некоторые проекты больше недоступны. Обновите список.')
    groups, items = {}, {}
    from app.pilot_donors import grants
    donor_only = grants(db, str(request_id))
    for id in ids:
        site = sites[id]
        reason = skip_reason(db, site)
        if id in donor_only:
            reason = 'Сетка используется только как донор. Текущий Main сохраняется.'
        try:
            general = site.site_type == 'general' or brand_key(site.brand) in {'', brand_key('Общие ключи')}
            filters = MassActionFilter(brand='Общие ключи' if general else site.brand, geo=geo_key(site.cache_geo))
        except ValueError:
            reason = reason or 'Для проекта не указаны корректные бренд и GEO.'
        items[id] = {'site_id': id, 'project': site.name, 'geo': geo_key(site.cache_geo), 'status': 'skipped' if reason else 'pending', 'reason': reason, 'run_id': None}
        if not reason:
            key = (brand_key(filters.brand), filters.geo)
            groups.setdefault(key, {'filter': filters.model_dump(), 'site_ids': []})['site_ids'].append(id)
    chunks = []
    for key in sorted(groups):
        group = groups[key]
        for offset in range(0, len(group['site_ids']), cfg.max_projects):
            chunks.append({'filter': group['filter'], 'site_ids': group['site_ids'][offset:offset+cfg.max_projects], 'status': 'pending'})
    job = models.BackgroundJob(id=str(request_id), kind=kind, status='queued' if chunks else 'completed',
        payload={'site_ids': ids, 'actor': actor, 'allowed': sorted(allowed) if allowed is not None else None,
                 'config_hash': auto.digest(cfg.model_dump()), 'execution_mode': cfg.execution_mode, 'auto_pilot': preview_only, 'planner_version': PLANNER_VERSION},
        result={'items': items, 'groups': chunks, 'sent': {}})
    return job


def view(db, job):
    result = job.result or {}
    items = []
    for item in result.get('items', {}).values():
        row = dict(item)
        run = db.get(models.AutoReglueRun, row.get('run_id')) if row.get('run_id') else None
        if run: row.update(status=run.status, reason=run.message)
        from app.pilot_content_publication import merge_row
        merge_row(db, job, row)
        items.append(row)
    from app.pilot_observed_reglues import project
    project(db, job, items)
    return {'id': job.id, 'status': job.status, 'created_at': job.created_at, 'error': job.error,
            'items': items, 'counts': {status: sum(i['status'] == status for i in items)
            for status in {'pending', 'queued', 'running', 'generating', 'waiting', 'completed', 'skipped', 'failed', 'partial', 'cancelled'}}}


def require_run(db, run):
    """Recheck the durable list and weekly exclusion before every new remote write."""
    if not run or not run.plan.get('list_launch_id'): return
    job = db.get(models.BackgroundJob, run.plan['list_launch_id'])
    if not job or job.kind != KIND or run.site_id not in job.payload['site_ids']:
        raise ValueError('Нет сохранённого разрешения на переклей проекта из списка.')
    allowed = job.payload.get('allowed')
    if allowed is not None and not {run.site_id, run.plan.get('source_site_id', run.site_id)}.issubset(allowed):
        raise ValueError('Проект вне разрешённой области запуска.')
    site = db.get(models.Site, run.site_id)
    db.refresh(site)
    if changed_this_week(site):
        # Finishing alternates after this run's own confirmed Main change is allowed.
        own = [op for op in db.scalars(select(models.NetworkOperation).where(
            models.NetworkOperation.site_id == site.id, models.NetworkOperation.action == 'reglue',
            models.NetworkOperation.status == 'confirmed')) if op.request_payload.get('auto_run_id') == run.id]
        if not any(utc(op.request_payload.get('confirmed_at')) == utc(site.last_reglue_at) for op in own):
            raise ValueError(weekly_reason(site))


class PreviewCancelled(Exception):
    pass


def cancel_key(job_id):
    return 'pilot-cancel:'+str(job_id)


class PreviewReplan(Exception):
    pass


def check_preview_cancelled(db, job):
    if job.kind==PREVIEW_KIND and db.scalar(select(models.AutoReglueConfig.key).where(models.AutoReglueConfig.key==cancel_key(job.id))):
        raise PreviewCancelled()
    if job.kind == PREVIEW_KIND:
        from app.pilot_replanning import pending
        if pending(db, job.id): raise PreviewReplan()


def execute_step(db, job_id, send, *, parallel_texts=False):
    try:
        with network.network_lock(db, 'mass-reglue-list:' + job_id):
            job = db.get(models.BackgroundJob, job_id)
            if job and job.kind == PREVIEW_KIND:
                from app.pilot_replanning import apply_pending
                apply_pending(db, job)
            if not job or job.status != 'queued': return {'status': 'skipped'}
            preview_only = job.kind == PREVIEW_KIND
            db.info['pilot_job_id'] = job.id
            db.info['parallel_pilot_texts'] = parallel_texts
            if not preview_only and job.payload.get('streaming_start'):
                from app.pilot_streaming import execute
                return execute(db,job,send)
            db.info['manual_pilot_job_id']=job.id if not preview_only and job.payload.get('manual_start') else None
            db.info['pilot_allow_stock_drops'] = job.payload.get('allow_stock_drops',True)
            db.info['auto_pilot_preview'] = preview_only
            db.info['pilot_mixed'] = preview_only and job.payload.get('planning_mode') == 'mixed'
            db.info['prefer_own_domains'] = True
            job.started_at = job.started_at or datetime.now(timezone.utc)
            # Every step is persisted; duplicated deliveries and worker restarts resume it.
            result = dict(job.result)
            result['groups'] = [dict(g) for g in result['groups']]
            result['items'] = {k: dict(v) for k, v in result['items'].items()}
            result['sent'] = dict(result.get('sent', {}))
            def save():
                check_preview_cancelled(db,job)
                job.result = dict(result); db.commit()
            for group in result['groups']:
                check_preview_cancelled(db,job)
                if group['status'] in {'done', 'previewed'}: continue
                ids = group['site_ids']
                if group['status'] == 'pending':
                    if auto.digest(auto.config(db).model_dump()) != job.payload['config_hash']:
                        for id in ids: result['items'][id].update(status='skipped', reason='Настройки изменились после запуска списка.')
                        group['status'] = 'done'; save(); continue
                    ready = []
                    for id in ids:
                        site = db.get(models.Site, id)
                        reason = skip_reason(db, site)
                        if not reason and not matches(site, MassActionFilter.model_validate(group['filter'])):
                            reason = 'Бренд или GEO изменились после запуска списка.'
                        if reason: result['items'][id].update(status='skipped', reason=reason)
                        else: ready.append(site)
                    if not ready:
                        group['status'] = 'done'; save(); continue
                    try:
                        db.info['canonical_allocation_plans'] = [p for g in result['groups'] for p in g.get('plans', [])]
                        constrain(db, group['filter'], set(job.payload['allowed']) if job.payload['allowed'] is not None else None, ready)
                        db.info.pop('mass_participant_ids', None)
                        if job.payload['execution_mode'] == 'cross_network':
                            from app.cross_reglue_batch import build
                            db.info['reglue_preview_domains'] = {p['new_main'] for g in result['groups'] for p in g.get('plans', [])} if preview_only else set()
                            try:
                                if job.payload.get('preserved_target_plans'):
                                    from app.pilot_report_conversion import build_preserved
                                    preview = build_preserved(db, job, ready)
                                else:
                                    preview = build(db, ready, job.payload['actor'])
                            finally: db.info.pop('reglue_preview_domains', None)
                            group.update(batch_id=preview['batch_id'], plans=preview['plans'])
                            for skip in preview['skipped']:
                                result['items'][skip['site_id']].update(status='skipped', reason=skip['error'])
                                if skip.get('retry_state'):
                                    result['items'][skip['site_id']]['retry_state'] = skip['retry_state']
                        else:
                            group['plans'] = []
                            for site in ready:
                                try:
                                    plan = auto.preview(db, site, 'mass')
                                    group['plans'].append(plan)
                                    db.info['canonical_allocation_plans'].append(plan)
                                except network.NetworkBusy:
                                    raise
                                except (ValueError, network.NetworkConflict, ProjectCacheError, httpx.HTTPError) as error:
                                    result['items'][site.id].update(status='skipped', reason=str(error)[:1500])
                        group['status'] = 'prepared'; save()
                    except network.NetworkBusy:
                        db.rollback();job.dispatched_at=None;save()
                        return {'status':'queued'}
                    except (ValueError, network.NetworkConflict, ProjectCacheError, httpx.HTTPError) as error:
                        db.rollback()
                        for site in ready: result['items'][site.id].update(status='failed', reason=str(error)[:1500])
                        group['status'] = 'done'; save(); continue
                if group['status'] == 'prepared' and preview_only:
                    from app.auto_pilot import describe
                    for plan in group.get('plans', []):
                        result['items'][plan['site_id']].update(status='ready', **describe(db, plan))
                    group['status'] = 'previewed'; save(); continue
                if group['status'] == 'prepared':
                    from app.pilot_weekly import exclude
                    if exclude(db, result, job=job): save()
                    if group['status'] == 'done': continue
                    try:
                        plans = group.get('plans', [])
                        from app.pilot_path_repair import repair
                        repair(db,job,result,plans)
                        entries = [{'site_id': p['site_id'], 'preview_token': p['preview_token'],
                                    'request_id': str(uuid5(UUID(job.id), p['site_id']))} for p in plans]
                        constrain(db, group['filter'], set(job.payload['allowed']) if job.payload['allowed'] is not None else None)
                        db.info.pop('mass_participant_ids', None)
                        # Recheck after slow preview reads, before reserving any domains.
                        for item in entries:
                            if not db.get(models.AutoReglueRun, item['request_id']):
                                site = db.get(models.Site, item['site_id']); db.refresh(site)
                                if reason := skip_reason(db, site): raise ValueError(reason)
                        if group.get('batch_id'):
                            from app.cross_reglue_batch import reserve
                            reserved = reserve(db, group['batch_id'], entries, job.payload['actor'])
                        else:
                            reserved = [auto.prepare_run(db, db.get(models.Site, e['site_id']), UUID(e['request_id']), e['preview_token'], job.payload['actor'], 'mass', saved_plan=next(p for p in plans if p['site_id'] == e['site_id'])) for e in entries]
                        for run, _ in reserved:
                            run.plan = {**run.plan, 'list_launch_id': job.id}
                            result['items'][run.site_id].update(status=run.status, run_id=run.id)
                        group['status'] = 'waiting'; save()
                    except network.NetworkBusy:
                        db.rollback();job.dispatched_at=None;save()
                        return {'status':'queued'}
                    except (ValueError, network.NetworkConflict, ProjectCacheError, httpx.HTTPError) as error:
                        db.rollback()
                        # Recover any runs committed before an interrupted within-network loop.
                        for id in ids:
                            run = db.get(models.AutoReglueRun, str(uuid5(UUID(job.id), id)))
                            if run:
                                run.plan = {**run.plan, 'list_launch_id': job.id}
                                result['items'][id].update(run_id=run.id, status=run.status)
                            elif result['items'][id]['status'] == 'pending':
                                result['items'][id].update(status='failed', reason=str(error)[:1500])
                        group['status'] = 'waiting'; save()
                if group['status'] == 'waiting':
                    running = []
                    for id in ids:
                        if result['items'][id].get('completed_elsewhere'): continue
                        rid = result['items'][id].get('run_id')
                        run = db.get(models.AutoReglueRun, rid) if rid else None
                        if not run: continue
                        result['items'][id].update(status=run.status, reason=run.message)
                        if run.status not in TERMINAL: running.append(run)
                        if run.status == 'queued':
                            last = utc(result['sent'].get(run.id))
                            if not last or last < datetime.now(timezone.utc) - timedelta(minutes=1):
                                try:
                                    send(run.id)
                                    result['sent'][run.id] = datetime.now(timezone.utc).isoformat()
                                except Exception:
                                    job.error = 'Очередь временно недоступна. Отправка будет повторена.'
                    if not running: group['status'] = 'done'
                    save()
                    # Independent brand/GEO groups may execute concurrently.
                    # Celery bounds active work; participant/domain locks still apply.
                    continue
            if all(g['status'] in {'done', 'previewed'} for g in result['groups']):
                if preview_only:
                    from app.pilot_weekly import exclude
                    exclude(db, result, job=job)
                    from app.pilot_variations import finalize
                    finalize(db, job, result)
                    if not result.get('variations_finalized'):
                        save()
                        return {'status':job.status}
                    from app.pilot_versions import capture_all
                    capture_all(job, result)
                job.status = 'completed'; job.finished_at = datetime.now(timezone.utc); job.error = None
            else:
                job.dispatched_at = None
            save()
            return {'status': job.status}
    except PreviewReplan:
        db.rollback()
        with network.network_lock(db, 'mass-reglue-list:' + job_id):
            job = db.get(models.BackgroundJob, job_id); db.refresh(job)
            from app.pilot_replanning import apply_pending
            apply_pending(db, job)
        return {'status': job.status}
    except PreviewCancelled:
        db.rollback()
        job=db.get(models.BackgroundJob,job_id);db.refresh(job)
        job.status='cancelled';job.finished_at=datetime.now(timezone.utc);db.commit()
        return {'status':'cancelled'}
    except network.NetworkConflict:
        db.rollback()
        return {'status': 'busy'}
    except Exception as error:
        db.rollback()
        job=db.get(models.BackgroundJob,job_id)
        if not job or job.kind!=PREVIEW_KIND:raise
        db.refresh(job)
        # A failure in the superseded generation must not strand an accepted
        # replan command in a failed job that the dispatcher will never pick up.
        from app.pilot_replanning import pending, apply_pending
        if pending(db, job_id):
            with network.network_lock(db, 'mass-reglue-list:' + job_id):
                db.refresh(job)
                if apply_pending(db, job): return {'status': job.status}
        job.status='failed';job.error=str(error)[:1000];job.finished_at=datetime.now(timezone.utc);db.commit()
        return {'status':'failed'}

    finally:
        db.info.pop('pilot_job_id', None)
        db.info.pop('parallel_pilot_texts', None)
        db.info.pop('manual_pilot_job_id', None)
        db.info.pop('auto_pilot_preview', None)
        db.info.pop('pilot_allow_stock_drops', None)
        db.info.pop('pilot_mixed', None)
        db.info.pop('prefer_own_domains', None)
        db.info.pop('canonical_allocation_plans', None)
