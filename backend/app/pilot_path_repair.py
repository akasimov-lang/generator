"""Replace a contested fake path in the authorized plan, without a new variant."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from app import models, auto_reglue as auto
from app.fake_main import normalize_fake_path, retarget_fake_head
from app.fake_path_allocation import group, group_lock, occupied, next_path


def repair(db, job, result, plans):
    from app.cross_reglue_batch import key
    from app.auto_pilot import describe
    from app.pilot_text_jobs import fingerprint
    all_plans=[p for g in result['groups'] for p in g.get('plans',[])]
    sites={p['site_id']:db.get(models.Site,p['site_id']) for p in plans}
    changed=[]
    with ExitStack() as locks:
        scopes={group(s):s for s in sites.values()}
        for scope in sorted(scopes):locks.enter_context(group_lock(db,scopes[scope]))
        for plan in plans:
            old=plan.get('fake_main_path')
            site=sites[plan['site_id']]
            if not old or normalize_fake_path(old).casefold() not in occupied(db,site,all_plans):continue
            row=result['items'][site.id]
            if row.get('run_id'):continue # Existing native receipts must be reconciled first.
            from app.project_network import read_network
            state=read_network(db,site)
            new=next_path(db,site,state,auto.config(db),all_plans)
            plan['text_fingerprint_before_path_repair']=fingerprint(plan)
            head={**plan,'canon':plan.get('new_main'),'domains':list(dict.fromkeys([
                *state.get('domains',[]),plan.get('new_main'),plan.get('parent_domain'),plan.get('parent_alternate_domain')]))}
            plan.update(retarget_fake_head(head,old,new))
            for field in ('alternates_after',):
                if isinstance(plan.get(field),dict):
                    data=plan[field]
                    patch=retarget_fake_head({**head,'alternateMarkup':data.get('markup','')},old,new)
                    if patch:plan[field]={**data,'markup':patch['alternateMarkup']}
            for field in ('fake_main_path','create_fake_main_path','new_fake_main_path','x_default_parent_path'):
                if plan.get(field)==old:plan[field]=new
            plan['create_fake_main_path']=new
            def url(value):
                parsed=urlsplit(value)
                return urlunsplit(parsed._replace(path=new)) if parsed.path.rstrip('/')==old.rstrip('/') else value
            plan['required_page_urls']=[url(v) for v in plan.get('required_page_urls',[])]
            plan['path_adjustments']=[*plan.get('path_adjustments',[]),{
                'before':old,'after':new,'at':datetime.now(timezone.utc).isoformat(),
                'reason':'Путь занят в другой сетке бренда и GEO. Выбран уникальный внутряк.'}]
            from app.pilot_schemes import validate_single_alternate, validate_parent_x_default
            validate_single_alternate(plan);validate_parent_x_default(plan)
            plan.pop('preview_token',None);plan['preview_token']=auto.digest(plan)
            row.update(**describe(db,plan),reason=None)
            history=result.get('row_versions',{}).get(site.id,{})
            for version in history.get('versions',[]):
                if version['number']==history.get('selected'):version['plan']=deepcopy(plan)
            for g in result['groups']:
                if not any(p['site_id']==site.id for p in g.get('plans',[])):continue
                ledger=db.get(models.AutoReglueConfig,key(g['batch_id'])) if g.get('batch_id') else None
                if ledger:
                    if site.id in ledger.value.get('run_ids',{}):raise ValueError('Запуск уже зарезервирован; требуется подтверждение его операций.')
                    ledger.value={**ledger.value,'plans':[deepcopy(plan) if p['site_id']==site.id else p for p in ledger.value['plans']]}
            child=db.get(models.BackgroundJob,plan.get('pilot_alternative_id')) if plan.get('pilot_alternative_id') else None
            if child:child.result={**child.result,'plan':deepcopy(plan)}
            changed.append(site.id)
        if changed:
            job.result=deepcopy(result)
            db.commit()
    return changed
