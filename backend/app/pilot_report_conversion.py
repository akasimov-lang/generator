"""Promote a planning-only report in place; retain its exact target domains and audit."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from app import models, maintenance_reports, mass_reglue_launch as launch, auto_reglue as auto
from app.project_network import network_lock, NetworkConflict


def convert(db, report_id, user, *, percentages, title_rewrite_mode='full_all'):
    from app.pilot_mixed import parameters
    with network_lock(db, 'mass-reglue-list-start'), network_lock(db, 'mass-reglue-list:' + str(report_id)):
        job = db.get(models.BackgroundJob, str(report_id))
        if job and job.kind == launch.PREVIEW_KIND and job.payload.get('maintenance_archive_key'):
            from app.auto_pilot import get
            return get(db, report_id, user)
        job = maintenance_reports.get(db, report_id, user)
        rows = (job.result or {}).get('entries', [])
        if not job.payload.get('planning_only') or any(r.get('run_id') or r.get('operations') or r.get('edit_ids') for r in rows):
            raise NetworkConflict('Можно преобразовать только план, выполнение которого ещё не начиналось.')
        ids = list(job.payload['site_ids'])
        pins = {r['site_id']:deepcopy(r['plan']) for r in rows if r.get('plan')}
        if set(pins) != set(ids):
            raise ValueError('Сначала выберите целевой домен для каждого проекта.')
        archive_key = 'maintenance-pilot-archive:' + job.id
        db.add(models.AutoReglueConfig(key=archive_key, value={'payload':deepcopy(job.payload), 'result':deepcopy(job.result), 'status':job.status, 'archived_at':datetime.now(timezone.utc).isoformat()}))
        fresh = launch.initial_job(db, job.id, ids, job.payload['actor'], user.get('allowed_site_ids'), preview_only=True)
        retained = {k:deepcopy(job.payload[k]) for k in ('original_site_ids','excluded_site_ids','excluded_projects') if k in job.payload}
        job.payload = {**fresh.payload, **retained, **parameters(db,percentages,title_rewrite_mode),
            'execution_mode':'cross_network', 'planning_filter':{'scope_mode':'include','brands':[],'geos':[]},
            'fixed_site_ids':ids, 'preserved_target_plans':pins, 'maintenance_archive_key':archive_key,
            'draft_name':f'План {len(ids)} проектов · выбранные домены сохранены',
            'allow_stock_drops':True, 'generation_id':str(uuid4())}
        job.kind=fresh.kind;job.result=fresh.result;job.status=fresh.status
        job.started_at=job.finished_at=job.dispatched_at=None;job.error=None
        db.commit()
        return job


def build_preserved(db, job, sites):
    """Refresh observations for the pinned targets; never substitute another domain."""
    from app import project_network as network, cross_reglue as cross
    from app.cross_reglue_batch import key
    from app.domain_transfer_policy import banned_domains, domain_key
    plans, skipped = [], []
    batch_id = str(uuid4())
    cfg = auto.config(db)
    for target in sites:
        old = job.payload['preserved_target_plans'].get(target.id)
        if not old:
            skipped.append({'site_id':target.id,'error':'Для проекта не сохранён целевой домен.'});continue
        try:
            source = db.get(models.Site, old.get('source_site_id',target.id))
            if source is None:raise ValueError('Исходная сетка больше недоступна.')
            allowed=job.payload.get('allowed')
            if allowed is not None and source.id not in allowed:raise ValueError('Исходная сетка недоступна пользователю.')
            state = network.read_network(db,target)
            source_state = state if source.id==target.id else network.read_network(db,source)
            domain=old['new_main']
            if domain_key(domain)==domain_key(state['canon']):raise ValueError('Выбранный домен уже является Main. Другой домен автоматически не выбирается.')
            if banned_domains(db,target,[domain])[domain]:raise ValueError('Выбранный домен отмечен БАН.')
            if not old.get('reserve_pool_id') and not old.get('create_subdomain') and domain not in source_state['domains']:
                raise ValueError('Выбранный домен больше не находится в исходной сетке.')
            if old.get('reserve_pool_id'):
                from app.reglue_reserves import validate_plan
                validate_plan(db,target,state,old)
            plan=deepcopy(old)
            for field in ('preview_token','title_h1_preview','title_h1_error','paragraphs_preview','paragraphs_error','internal_pages'):
                plan.pop(field,None)
            plan.update(old_main=state['canon'], old_fake_main_path=state.get('fake_main_current'),
                revision=state['revision'], source_revision=source_state['revision'],
                target_guard=cross.source_guard(state), source_guard=cross.source_guard(source_state),
                target_domains=state['domains'],source_domains=source_state['domains'],
                target_count=len(state['domains']),source_count=len(source_state['domains']),
                alternates_before={'markup':state['alternateMarkup'],'enabled':state['enableAlternates']},
                title_h1_current=state.get('page_metadata',{}), config_hash=auto.digest(cfg.model_dump()), batch_id=batch_id)
            plan['preview_token']=auto.digest(plan);plans.append(plan)
        except Exception as error:
            skipped.append({'site_id':target.id,'error':str(error)[:1500]})
    db.add(models.AutoReglueConfig(key=key(batch_id),value={'created_by':job.payload['actor'],'plans':plans,'skipped':skipped,'run_ids':{},'filter':None,'distribution':{}}))
    db.commit()
    return {'batch_id':batch_id,'plans':plans,'skipped':skipped}
