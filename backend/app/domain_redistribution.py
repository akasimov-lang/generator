"""Two-domain redistribution with receipts, history and an explicit inverse operation."""
from contextlib import ExitStack
from datetime import datetime, timezone
from uuid import UUID, uuid5
from sqlalchemy import select
from app import models, project_network as network, auto_reglue as auto, cross_reglue as cross
from app.mass_action_reports import refresh_run
from app.domain_transfer_policy import require_transfer_allowed, policy_key, record_transfer_cooldown


def receipt(run, action):
    if action=='delete_batch' and run.plan.get('extraction_batch'):return run.plan['extraction_batch']
    return str(uuid5(UUID(run.id), 'redistribute:' + action))


def deletion_actions(run):
    # Old runs keep their original receipts; never resend a submitted deletion.
    if run.plan.get('deletion_mode') == 'batch':
        return ['delete_batch']
    return ['delete:' + item['domain'] for item in run.plan['domains']]


def snapshot(state):
    return {**cross.source_guard(state), 'domains': list(state['domains'])}


def eligible(db, site, state, domain, *, rollback=False):
    cross.transferable(site, state, domain)
    require_transfer_allowed(db, site, domain, ignore_cooldown=rollback)
    cross.unique_membership(db, domain, {site.id})


def choose_domains(db, source, state):
    available = {'drop': [], 'newreg': []}
    for domain in state['domains']:
        try:
            eligible(db, source, state, domain)
        except ValueError:
            continue
        kind = (source.domain_types or {}).get(domain)
        if kind in available:
            available[kind].append({'domain': domain, 'domain_type': kind})
    selected = [available[kind].pop(0) for kind in ('drop', 'newreg') if available[kind]]
    for kind in ('drop', 'newreg'):
        selected.extend(available[kind][:2-len(selected)])
    return selected[:2]


def make_plan(db, source, target, source_state, target_state, domains, *, rollback_of=None):
    cross.require_import_target(target_state)
    plan = {'execution_mode': 'transfer_only', 'deletion_mode': 'batch', 'scope': 'mass', 'site_id': target.id, 'project': target.name,
        'source_site_id': source.id, 'source_project': source.name, 'brand': target.brand,
        'geo': cross.geo_key(target.cache_geo), 'domains': domains, 'old_main': target_state['canon'],
        'old_fake_main_path': target_state.get('fake_main_current') or None, 'new_fake_main_path': target_state.get('fake_main_current') or None,
        'source_count':len(source_state['domains']), 'target_count':len(target_state['domains']),
        'source_revision':source_state['revision'], 'revision':target_state['revision'],
        'source_before':snapshot(source_state), 'target_before':snapshot(target_state),
        'config_hash':auto.digest(auto.config(db).model_dump())}
    if rollback_of:
        plan['rollback_of'] = rollback_of
    plan['preview_token'] = auto.digest(plan)
    return plan


def preview(db, target, state):
    cross.require_import_target(state)
    cfg = auto.config(db)
    auto.require_eligible(target, cfg, auto.config(db, target.id))
    if auto.config(db, target.id).scope == 'personal' or auto.active_run(db, target.id):
        raise ValueError('Принимающая сетка имеет персональные настройки или незавершённый запуск.')
    pending = set(db.scalars(select(models.NetworkOperation.site_id).where(models.NetworkOperation.status.in_(['pending','unknown']))))
    if target.id in pending:
        raise ValueError('У принимающей сетки есть неподтверждённая операция.')
    query = select(models.Site).where(models.Site.is_active.is_(True), models.Site.project_status=='mass_actions', models.Site.id != target.id)
    allowed = db.info.get('cross_allowed_site_ids')
    if allowed is not None:
        query=query.where(models.Site.id.in_(allowed))
    candidates=[]
    for source in db.scalars(query):
        try: cross.require_pair(source,target)
        except ValueError: continue
        if source.id in pending or auto.config(db,source.id).scope=='personal' or auto.active_run(db,source.id):
            continue
        source_state=network.read_network(db,source)
        if len(source_state['domains']) > len(state['domains']):
            candidates.append((source,source_state))
    candidates.sort(key=lambda item:(-len(item[1]['domains']),item[0].name,item[0].id))
    for source,source_state in candidates:
        domains=choose_domains(db,source,source_state)
        if domains:
            return make_plan(db,source,target,source_state,state,domains)
    raise ValueError('Нет доступных доменов в более крупной сетке того же бренда и GEO. Домены, участвующие в редиректах, исключены из переноса.')


def validate_rollback(db, run):
    original=db.get(models.AutoReglueRun,run.plan.get('rollback_of'))
    if (not original or original.status!='completed' or original.plan.get('execution_mode')!='transfer_only'
        or original.plan.get('rollback_of') or original.plan.get('rolled_back_at')
        or run.site_id!=original.plan['source_site_id'] or run.plan['source_site_id']!=original.site_id
        or run.plan['domains']!=original.plan['domains']
        or run.id!=str(uuid5(UUID(original.id),'rollback'))):
        raise ValueError('Откат должен возвращать только домены подтверждённого исходного переноса.')
    return original


def prepare_rollback(db, original, username):
    if original.plan.get('execution_mode')!='transfer_only' or original.status!='completed' or original.plan.get('rollback_of'):
        raise ValueError('Откат доступен для завершённого перераспределения доменов.')
    run_id=str(uuid5(UUID(original.id),'rollback'))
    existing=db.get(models.AutoReglueRun,run_id)
    if existing:
        return existing,False
    source=db.get(models.Site,original.site_id)
    target=db.get(models.Site,original.plan['source_site_id'])
    cross.require_pair(source,target)
    if any(auto.active_run(db,s.id) for s in (source,target)):
        raise network.NetworkConflict('Одна из сеток уже участвует в другом запуске.')
    source_state=network.read_network(db,source)
    target_state=network.read_network(db,target)
    for item in original.plan['domains']:
        eligible(db,source,source_state,item['domain'],rollback=True)
        if item['domain'] in target_state['domains']:
            raise ValueError('Домен уже присутствует в исходной сетке.')
    plan=make_plan(db,source,target,source_state,target_state,original.plan['domains'],rollback_of=original.id)
    with cross.participant_locks(db,target.id,plan):
        if any(auto.active_run(db,s.id) for s in (source,target)):
            raise network.NetworkConflict('Одна из сеток уже участвует в другом запуске.')
        existing=db.get(models.AutoReglueRun,run_id)
        if existing:return existing,False
        run=models.AutoReglueRun(id=run_id,site_id=target.id,initiator=username,status='queued',phase='prepared',plan=plan)
        db.add(run)
        original.plan={**original.plan,'rollback_run_id':run_id}
        db.commit()
    return run,True


def validate_write(db,run,site,payload):
    cross.require_pair(db.get(models.Site,run.plan['source_site_id']),db.get(models.Site,run.site_id))
    names=[item['domain'] for item in run.plan['domains']]
    if not 1<=len(names)<=2 or len(set(names))!=len(names):
        raise ValueError('За одно нажатие можно перенести не более двух разных доменов.')
    if run.plan.get('manual_action') == 'move_plus2':
        from app.move_plus2 import validate_intent
        validate_intent(db, run)
    if run.plan.get('rollback_of'):validate_rollback(db,run)
    if payload.action == 'create_domains' and str(payload.request_id) != receipt(run,'create'):
        from app.transfer_report_check import valid_retry
        if valid_retry(db,run,site,payload):return
    if payload.action=='delete_domain':
        if run.plan.get('deletion_mode') == 'batch':
            if run.plan.get('extraction_batch'):
                from app.move_batch import extraction
                peers,all_names=extraction(db,run)
                valid=(site.id==run.plan['source_site_id'] and payload.domains==all_names
                    and not payload.domain and str(payload.request_id)==receipt(run,'delete_batch'))
                state=network.read_network(db,site)
                for name in all_names:eligible(db,site,state,name)
            else:
                valid=(site.id==run.plan['source_site_id'] and payload.domains==names
                    and not payload.domain and str(payload.request_id)==receipt(run,'delete_batch'))
        else:
            valid=(site.id==run.plan['source_site_id'] and payload.domain in names
                and (not payload.domains or payload.domains==[payload.domain])
                and str(payload.request_id)==receipt(run,'delete:'+payload.domain))
    elif payload.action=='create_domains':
        source=db.get(models.Site,run.plan['source_site_id'])
        valid=site.id==run.site_id and payload.domains==names and str(payload.request_id)==receipt(run,'create')
        for action in deletion_actions(run):
            deletion=db.get(models.NetworkOperation,receipt(run,action))
            if run.plan.get('extraction_batch'):
                from app.transfer_report_check import deletion_ready
                ready=deletion_ready(db,run,source,names)
            else:ready=bool(deletion and cross.completed_job(db,source,deletion))
            if not deletion or deletion.site_id!=source.id or not ready:valid=False
    else:valid=False
    if not valid:
        raise ValueError('Перераспределение допускает только согласованные извлечение и добавление двух доменов после подтверждения Webdev.')


def step(db,run,site,action,state,**values):
    operation_id=receipt(run, 'create' if action=='create_domains' else
        'delete_batch' if run.plan.get('deletion_mode') == 'batch' else 'delete:'+values['domain'])
    operation=db.get(models.NetworkOperation,operation_id)
    if operation is None:
        run.status='running';run.phase='transfer_create' if action=='create_domains' else 'transfer_delete';db.commit()
        network.change_network(db,site,network.NetworkChange(request_id=operation_id,action=action,revision=state['revision'],**values),run.initiator,auto_run_id=run.id)
        operation=db.get(models.NetworkOperation,operation_id)
    if action=='create_domains':
        if operation.status=='confirmed':return True
        actual=network.read_network(db,site)
        if all(d in actual['domains'] for d in values['domains']):return True
    try:completed=cross.completed_job(db,site,operation)
    except ValueError:
        if not (action=='delete_domain' and run.plan.get('extraction_batch')):raise
        from app.transfer_report_check import deletion_ready
        if not deletion_ready(db,run,site):raise
        completed=True
    if not completed:
        run.status='waiting';run.message='Ждём подтверждения Webdev. Повторная отправка не выполняется.';db.commit()
        return False
    return True


def execute(db,run):
    plan=run.plan
    source,target=db.get(models.Site,plan['source_site_id']),db.get(models.Site,run.site_id)
    names=[item['domain'] for item in plan['domains']]
    try:
        with ExitStack() as locks:
            from app.move_batch import extraction
            _,extracted_names=extraction(db,run) if plan.get('extraction_batch') else ([run],names)
            for domain in sorted(extracted_names):locks.enter_context(network.network_lock(db,policy_key(domain)))
            cross.require_pair(source,target)
            rollback=bool(plan.get('rollback_of'))
            original=validate_rollback(db,run) if rollback else None
            if not rollback:
                cfg=auto.config(db)
                if plan.get('manual_action') == 'move_plus2':
                    from app.move_plus2 import validate_intent
                    validate_intent(db, run)
                elif not cfg.enabled or cfg.execution_mode!='transfer_only':raise ValueError('Режим перераспределения выключен.')
                if any(auto.config(db,s.id).scope=='personal' for s in (source,target)):
                    raise ValueError('У сетки включены персональные настройки.')
            source_state,target_state=network.read_network(db,source),network.read_network(db,target)
            existing=[db.get(models.NetworkOperation,receipt(run,action)) for action in deletion_actions(run)]
            if not any(existing):
                cross.require_import_target(target_state)
                from app.domain_redirects import require_transfer_free
                require_transfer_free(source_state, extracted_names)
                revisions_match=source_state['revision']==plan['source_revision'] and target_state['revision']==plan['revision']
                if plan.get('prefetch'):
                    from app.move_batch import state_matches
                    revisions_match=state_matches(db,run,source_state,source.id,plan['source_before']) and state_matches(db,run,target_state,target.id,plan['target_before'])
                if not revisions_match:
                    raise ValueError('Сетки изменились после предпросмотра. Подготовьте перенос заново.')
                if not rollback and plan.get('manual_action') != 'move_plus2' and auto.digest(auto.config(db).model_dump())!=plan['config_hash']:
                    raise ValueError('Настройки изменились после предпросмотра.')
                if not rollback and len(source_state['domains'])<=len(target_state['domains']):
                    raise ValueError('Перенос разрешён только из большей сетки в меньшую.')
                for domain in names:eligible(db,source,source_state,domain,rollback=rollback)
            if cross.source_guard(source_state)!=cross.source_guard(plan['source_before']) or cross.source_guard(target_state)!=cross.source_guard(plan['target_before']):
                raise ValueError('Main или настройки сетки изменились вне переноса. Проверьте результат вручную.')
            if plan.get('deletion_mode') == 'batch':
                if not step(db,run,source,'delete_domain',source_state,domains=extracted_names):return
            else:
                for domain in names:
                    source_state=network.read_network(db,source)
                    if not db.get(models.NetworkOperation,receipt(run,'delete:'+domain)):
                        eligible(db,source,source_state,domain,rollback=rollback)
                    if not step(db,run,source,'delete_domain',source_state,domain=domain):return
            source_state=network.read_network(db,source)
            if any(domain in source_state['domains'] for domain in names):
                raise ValueError('Извлечение доменов не подтверждено.')
            if plan.get('prefetch'):
                from app.move_batch import ready_to_add
                if not run.plan.get('source_released'):
                    run.plan={**run.plan,'source_released':True};db.commit()
                if not ready_to_add(db,run):
                    raise network.NetworkConflict('Домены извлечены. Ожидаем очередь последовательного добавления.')
            addition=db.get(models.NetworkOperation,receipt(run,'create'))
            if all(domain in target_state['domains'] for domain in names):pass
            elif addition is None:
                for domain in names:
                    require_transfer_allowed(db,target,domain,ignore_cooldown=rollback)
                    cross.unique_membership(db,domain,set())
                if not step(db,run,target,'create_domains',target_state,domains=names):return
            elif addition.status!='confirmed' and not cross.completed_job(db,target,addition):
                run.status='waiting';run.message='Ждём завершения добавления доменов.';db.commit();return
            after_source,after_target=network.read_network(db,source),network.read_network(db,target)
            if any(domain not in after_target['domains'] for domain in names):
                raise ValueError('Домены не появились в принимающей сетке.')
            if (cross.source_guard(after_source)!=cross.source_guard(plan['source_before'])
                or cross.source_guard(after_target)!=cross.source_guard(plan['target_before'])):
                raise ValueError('Настройки сетки изменились. Проверьте результат вручную.')
            deadlines={}
            for item in plan['domains']:
                domain=item['domain']
                target.domain_types={**(target.domain_types or {}),domain:item['domain_type']}
                at=after_target.get('domain_added_at',{}).get(domain) or datetime.now(timezone.utc).isoformat()
                deadlines[domain]=record_transfer_cooldown(db,domain,at,None)
            at=datetime.now(timezone.utc).isoformat()
            run.plan={**run.plan,'source_after':snapshot(after_source),'target_after':snapshot(after_target),
                'applied_result':{'new_main':after_target['canon'],'fake_main_path':after_target.get('fake_main_current') or None,'confirmed_at':at},
                'completed_at':at,'transfer_deadlines':deadlines}
            from app.move_batch import clear_destination_errors
            clear_destination_errors(db,run,names)
            run.status='completed';run.phase='completed';run.message=f"{'Откат подтверждён' if rollback else 'Перераспределение подтверждено'}: {len(names)} доменов."
            if original:
                original.plan={**original.plan,'rolled_back_at':at}
                refresh_run(db,original)
            refresh_run(db,run)
            db.commit()
    except network.NetworkConflict as error:
        db.rollback();db.refresh(run);run.status='waiting';run.message=str(error)[:2000];refresh_run(db,run);db.commit()
    except Exception as error:
        db.rollback();db.refresh(run)
        run.status='partial' if any(db.get(models.NetworkOperation,receipt(run,action)) for action in deletion_actions(run)) else 'failed'
        run.message=str(error)[:2000];refresh_run(db,run);db.commit()
