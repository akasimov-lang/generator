"""Replace a failed subdomain allocation for its own recipient only."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select
from app import models, auto_reglue as auto, cross_reglue as cross, cross_reglue_batch as batch
from app import project_network as network, reglue_reserves as stock


def replace_failed(db, run_id):
    run = db.get(models.AutoReglueRun, run_id)
    if not run or run.status not in {'failed', 'partial'} or not run.plan.get('create_subdomain'):
        return False
    job_id, batch_id = run.plan.get('list_launch_id'), run.plan.get('batch_id')
    if not job_id or not batch_id or run.plan.get('subdomain_fallback'):
        return False
    with network.network_lock(db, 'auto-run:' + run_id), network.network_lock(db, 'mass-reglue-list:' + job_id), network.network_lock(db, batch.key(batch_id)), network.network_lock(db, 'reglue-reserve-pool'):
        db.refresh(run)
        if run.status not in {'failed', 'partial'} or run.phase != 'cross_create_subdomains':
            return False
        old = deepcopy(run.plan)
        site = db.get(models.Site, run.site_id)
        job = db.get(models.BackgroundJob, job_id)
        if not job or job.kind != 'mass_reglue_list' or job.payload.get('actor') != run.initiator:
            return False
        if auto.digest(auto.config(db).model_dump()) != old['config_hash']:
            return False
        operation = db.get(models.NetworkOperation, cross.receipt_id(run, 'create_subdomains'))
        if not operation or not operation.request_payload.get('job_id'):
            return False
        with network.Remote(db, site) as remote:
            result = remote.job_state(operation.request_payload['job_id'])
        if result and result.get('state') == 'not_found':
            saved = operation.request_payload.get('provisioning_result') or {}
            result = saved.get('job') if saved.get('job_id') == operation.request_payload['job_id'] and saved.get('action') == operation.action else None
        details = (result or {}).get('result') or {}
        domains = details.get('domains') or (result or {}).get('domains') or []
        # A timeout or missing task is not proof of failure. Never reallocate while
        # the original create may still be in flight or target a different domain.
        if not result or result.get('state') not in {'completed', 'failed'} or not details.get('errorCount'):
            return False
        if len(domains) != 1 or domains[0].get('domain') != old['new_main'] or domains[0].get('status') != 'error':
            return False
        state = network.read_network(db, site)
        if state['canon'] != old['old_main'] or state.get('reserve') == old['new_main']:
            return False
        if any(db.get(models.NetworkOperation, cross.receipt_id(run, action)) for action in ('create_fake_main', 'reserve', 'reglue', 'alternates')):
            return False
        from app.mass_action_scope import constrain, stamp_plan
        from app.mass_reglue_launch import require_run
        require_run(db, run)
        constrain(db, old['mass_filter'], job.payload.get('allowed'), [site])
        from app.mass_main_targets import target_kind, require_target
        fixed = [p for g in job.result['groups'] for p in g.get('plans', []) if p['site_id'] != site.id]
        # Include every currently reserved allocation, not just this task's table.
        used = {cross.domain_key(p['new_main']) for p in fixed}
        used.update(cross.domain_key(r.plan['new_main']) for r in db.scalars(select(models.AutoReglueRun).where(models.AutoReglueRun.id != run.id, models.AutoReglueRun.status.in_(auto.ACTIVE))) if r.plan.get('new_main'))
        cfg = auto.config(db)
        previous_info = dict(db.info)
        try:
            db.info.update(auto_pilot_preview=True, canonical_allocation_plans=fixed)
            replacement = None
            for kind in ('newreg', 'drop'):
                for domain in state['domains']:
                    if cross.domain_key(domain) in used or target_kind(site, state, domain) != kind:
                        continue
                    try:
                        require_target(db, site, state, {'new_main': domain, 'main_target_kind': kind})
                        cross.unique_membership(db, domain, {site.id})
                    except ValueError:
                        continue
                    replacement = cross.make_plan(cfg, site, state, site, state, domain, mode='own_unused', db=db, plans=fixed)
                    replacement.update(local_target=True, main_target_kind=kind, required_domain_type=kind, domain_type=kind, requires_newreg=False)
                    break
                if replacement:
                    break
            if replacement is None:
                entry = stock.candidate(db, site, state, ['drop'], used)
                if entry is None:
                    return False
                replacement = stock.make_plan(db, cfg, site, state, entry, fixed)
            replacement = stamp_plan(db, replacement, state, site)
            for field in ('rewrite_title_h1', 'title_h1_current', 'title_h1_preview', 'redirect_old_main', 'pilot_variation_version'):
                if field in old:
                    replacement[field] = old[field]
            replacement['without_alternates'] = False
            from app.pilot_schemes import assign
            assign(db, [replacement], fixed=fixed)
        finally:
            db.info.clear(); db.info.update(previous_info)
        receipt = {'at': datetime.now(timezone.utc).isoformat(), 'old_plan': old, 'operation_id': operation.id,
                   'job_id': operation.request_payload['job_id'], 'job': result,
                   'reason': 'Поддомен не создан. Схема заменена только у этого проекта; доля поддоменов не перераспределяется.'}
        replacement.update(batch_id=batch_id, subdomain_fallback=receipt)
        replacement.pop('preview_token', None); replacement['preview_token'] = auto.digest(replacement)
        manifest = batch.manifest(db, batch_id)
        new_plans = [replacement if p['site_id'] == site.id else p for p in manifest.value['plans']]
        batch.validate(new_plans)
        # All remote reads are complete. Persist plan, manifest and display together.
        operation.request_payload = {**operation.request_payload, 'provisioning_result': {'job_id': receipt['job_id'], 'action': operation.action, 'job': result, 'observed_at': receipt['at']}}
        operation.status = 'failed'
        manifest.value = {**manifest.value, 'plans': new_plans}
        run.plan = {**replacement, 'list_launch_id': job_id}
        if replacement.get('reserve_pool_id'):
            stock.claim(db, run)
        run.status = 'queued'; run.phase = 'prepared'; run.message = receipt['reason']
        db.refresh(job)
        display = deepcopy(job.result)
        for group in display['groups']:
            group['plans'] = [replacement if p['site_id'] == site.id else p for p in group.get('plans', [])]
            if site.id in group['site_ids']:
                group['status'] = 'waiting'
        display['items'][site.id].update(status='queued', reason=run.message)
        from app.pilot_variations import update_summary
        update_summary(display)
        display['variation_summary']['warning'] = 'После неудачного создания поддомена схема заменена только у этого проекта. Доля поддоменов может быть ниже заданной; остальные назначения сохранены.'
        job.result = display; job.status = 'queued'; job.finished_at = None; job.dispatched_at = None
        db.commit()
        return True
