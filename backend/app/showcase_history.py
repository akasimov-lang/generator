"""Project showcase history from confirmed native-card receipts and report evidence."""
from sqlalchemy import select
from uuid import NAMESPACE_URL, uuid5
import hashlib,json
from app import models
from app.showcase_inventory import brand_delta, unique_brands


def record_names(records):
    names = []
    for record in records if isinstance(records, list) else []:
        if isinstance(record, dict):
            names.append(record.get('brand') or record.get('name'))
        elif isinstance(record, list):
            names.extend(field.get('value') for field in record if isinstance(field, dict) and field.get('key') in {'brand','name'})
    return unique_brands(names)


def receipt_changes(before, after):
    old, new = before.get('casinos'), after.get('casinos')
    if old is None or new is None:
        return []
    if isinstance(old, list) and isinstance(new, list):
        return [('Витрина', brand_delta(record_names(old), record_names(new)))]
    if not isinstance(old, dict) or not isinstance(new, dict):
        return []
    return [('Карточки витрины · '+group, brand_delta(record_names(old.get(group,[])), record_names(new.get(group,[]))))
            for group in sorted(set(old)|set(new)) if group != 'basic' and old.get(group)!=new.get(group)]


def summary_text(delta):
    count=lambda key:'не подтверждено' if delta.get(key) is None else str(delta[key])
    return f"Брендов было: {count('before')} · добавлено: {count('added')} · удалено: {count('removed')} · стало: {count('after')}"


def events(db, site_id):
    result=[]
    for op in db.scalars(select(models.ProjectPageEdit).where(models.ProjectPageEdit.site_id==site_id,
            models.ProjectPageEdit.page_key.in_(['showcase:casinos','showcase:audit','showcase:work'])).order_by(models.ProjectPageEdit.created_at.desc()).limit(50)):
        if op.page_key != 'showcase:casinos':
            saved=op.after_page or {}
            delta=saved.get('delta')
            result.append({'id':op.id,'kind':'showcase','title':saved.get('title','Витрина'),
                'status':saved.get('result_status',op.status),'created_at':op.updated_at or op.created_at,
                'actor':op.requested_by,'message':saved.get('message') or summary_text(delta or {}),
                'confirmed':op.status=='confirmed','showcase_delta':delta,'changes':[],
                'report_id':saved.get('report_id'),
                'url':f"/auto-reglue/pilot/report?maintenance={saved['report_id']}" if saved.get('report_id') else None})
            continue
        for index,(title,delta) in enumerate(receipt_changes(op.before_page or {},op.after_page or {})):
            confirmed=op.status=='confirmed'
            result.append({'id':op.id+':'+str(index),'kind':'showcase','title':title,'status':op.status,
                'created_at':op.created_at,'actor':op.requested_by,'message':summary_text(delta) if confirmed else (op.error or 'Изменение витрины ожидает подтверждения Webdev.'),
                'confirmed':confirmed,'showcase_delta':delta if confirmed else None,'changes':[], 'url':None})
    return result


def remember_report(db, job, entry):
    inventory=entry.get('inventory')
    change=entry.get('showcase_change')
    migration=entry.get('migration')
    if migration and not change and not migration.get('started_at'):return
    if not inventory and not change and not migration:return
    if migration and not change:
        delta={'before':migration.get('before_count'),'after':None,'added':None,'removed':None,'added_brands':[],'removed_brands':[]}
        title='Замена нестандартной витрины';message=summary_text(delta)+' · '+(migration.get('message') or 'Выполняется публикация стандартной витрины.')
    elif change:
        delta=change;title='Изменение витрины';message=summary_text(delta)+((' · '+change['description']) if change.get('description') else '')
    elif inventory:
        home=(inventory.get('home') or {}).get('public') or {}
        source=inventory.get('home') or {}
        brands=home.get('brands') if home.get('presence')=='present' else [] if home.get('presence')=='none' and source.get('presence')=='none' else None
        delta=brand_delta(brands,brands)
        delta.update(added=0,removed=0)
        title='Проверка витрины и внутренних страниц'
        message=summary_text(delta)+' · Изменения сайта не выполнялись.'
    saved={'title':title,'message':message,'delta':delta,'report_id':job.id,'result_status':entry['status']}
    key=str(uuid5(NAMESPACE_URL,'pagepilot:showcase-report:'+job.id+':'+entry['site_id']))
    digest=hashlib.sha256(json.dumps(saved,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    status='confirmed' if change or not migration else 'pending' if entry['status']=='running' else 'unknown'
    op=db.get(models.ProjectPageEdit,key)
    if op is None:
        op=models.ProjectPageEdit(id=key,site_id=entry['site_id'],page_key='showcase:work' if change or migration else 'showcase:audit',requested_by=job.payload['actor'],before_page={'brand_count':delta.get('before')},status=status,fingerprint=digest,after_page=saved)
        db.add(op)
    elif op.fingerprint!=digest:
        op.fingerprint=digest;op.after_page=saved;op.status=status
