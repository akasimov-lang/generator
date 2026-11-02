"""Explicit, backed-up homepage linking for published internal pages."""
from copy import deepcopy
import re
from uuid import UUID,uuid5
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app import models,project_pages as pages
from app.brand_home_links import project_link_brand,link_brand_paragraph,HomeAnchor
from app.page_content_tools import brand_pattern
from app.db import get_db
from app.security import AuthUser

router=APIRouter(prefix='/sites/{site_id}/autolink-pages',tags=['Project pages'])
class Start(BaseModel):
    request_id: UUID


def authorized(db,site_id,user):
    site=pages.site_for(db,site_id)
    allowed=user.get('allowed_site_ids')
    if allowed is not None and site_id not in allowed:raise HTTPException(404,'Проект недоступен.')
    return site


def serialize(job):
    return {'id':job.id,'status':job.status,'error':job.error,**(job.result or {'entries':[]})}


@router.post('',status_code=202)
def start(site_id:str,payload:Start,user:AuthUser,db:Session=Depends(get_db)):
    site=authorized(db,site_id,user)
    with pages.network_lock(db,'page-autolink:'+site_id):
        existing=db.get(models.BackgroundJob,str(payload.request_id))
        if existing:
            if existing.kind!='page_autolink' or existing.payload['site_id']!=site_id:raise HTTPException(409,'Идентификатор уже использован.')
            return serialize(existing)
        active=db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind=='page_autolink',models.BackgroundJob.status.in_(['queued','running','completed']))).all()
        if pending:=next((job for job in active if job.payload['site_id']==site_id and (job.status in {'queued','running'} or any(e.get('status') in {'unknown','pending'} for e in (job.result or {}).get('entries',[])))),None):return serialize(pending)
        job=models.BackgroundJob(id=str(payload.request_id),kind='page_autolink',payload={'site_id':site.id,'actor':user['username'],'brand':project_link_brand(site)},result={'entries':[]})
        db.add(job);db.commit()
        return serialize(job)


@router.get('')
def report(site_id:str,user:AuthUser,db:Session=Depends(get_db)):
    authorized(db,site_id,user)
    jobs=db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind=='page_autolink').order_by(models.BackgroundJob.created_at.desc())).all()
    job=next((j for j in jobs if j.payload['site_id']==site_id),None)
    if job:
        changed=False
        entries=deepcopy((job.result or {}).get('entries',[]))
        for entry in entries:
            if entry.get('status') not in {'pending','unknown'} or not entry.get('request_id'):continue
            try:
                result=pages.check_edit(site_id,entry['key'],UUID(entry['request_id']),user,db)
                entry.update(status=result['status'],message=result.get('error') or 'Ссылка сохранена.');changed=True
            except HTTPException:
                continue
        if changed:job.result={'entries':entries};db.commit()
    return serialize(job) if job else None


def paragraph_info(content,brand=None,*,any_link=False):
    paragraphs=[(index,b) for index,b in enumerate(content.get('blocks',[])) if isinstance(b,dict) and b.get('type')=='paragraph' and isinstance(b.get('data',{}).get('text'),str)]
    for index,block in paragraphs:
        if (brand or any_link) and HomeAnchor(block['data']['text'],re.compile(r'\S') if any_link else brand_pattern(brand)).found:
            return {'paragraph':block['data']['text'],'block_index':index,'block_id':block.get('id'),'has_home_link':True}
    if paragraphs:
        index,block=paragraphs[0]
        return {'paragraph':block['data']['text'],'block_index':index,'block_id':block.get('id')}
    return {'paragraph':'','block_index':None,'block_id':None}


def execute(db,job):
    site=pages.site_for(db,job.payload['site_id'])
    brand=job.payload.get('brand')
    entries=deepcopy((job.result or {}).get('entries',[]))
    def checkpoint():
        job.result={'entries':deepcopy(entries)};db.commit()
    with pages.remote_errors(),pages.Remote(db,site) as remote:
        project=remote.project()
    originals=[deepcopy(p) for p in pages.pages(project) if not pages.is_home(p)]
    for original in originals:
        key=pages.page_key(original)
        if any(entry['key']==key for entry in entries):continue
        content=original.get('content') or {}
        entry={**pages.page_summary(original),**paragraph_info(content),'status':'failed','message':''}
        try:
            if not brand:raise ValueError('Бренд проекта не указан. Добавьте ссылку вручную.')
            if project_link_brand(site)!=brand:raise ValueError('Бренд проекта изменился. Запустите обработку заново.')
            linked,changed=link_brand_paragraph(content,brand,max_mentions=2)
            entry.update(paragraph_info(linked,brand))
            if not changed:
                entry.update(status='already_linked',message='Ссылка на главную уже есть.')
            else:
                request_id=uuid5(UUID(job.id),'autolink:'+key)
                # Native backup and revision recheck happen inside save_page,
                # before its durable edit receipt and the external write.
                payload=pages.PageEdit(request_id=request_id,revision=pages.digest(original),**{**pages.editable(original),'content':linked})
                entry['request_id']=str(request_id)
                operation=db.get(models.ProjectPageEdit,str(request_id))
                result=(pages.check_edit(site.id,key,request_id,{'username':job.payload['actor']},db) if operation else
                        pages.save_page(site.id,key,payload,{'username':job.payload['actor']},db))
                entry.update(status=result['status'],message=result.get('error') or ('Ссылка сохранена.' if result['status']=='confirmed' else 'Проверяем результат сохранения.'))
                if result.get('page'):entry['revision']=result['page']['revision']
        except (ValueError,HTTPException) as error:
            db.rollback();entry['message']=str(error.detail if isinstance(error,HTTPException) else error)
        entries.append(entry);checkpoint()
    return {'entries':entries}


def saved_page(db,site,page):
    """The latest report follows manual paragraph edits made in the page editor."""
    jobs=db.scalars(select(models.BackgroundJob).where(models.BackgroundJob.kind=='page_autolink').order_by(models.BackgroundJob.created_at.desc())).all()
    job=next((row for row in jobs if row.payload['site_id']==site.id),None)
    if not job:return
    key=pages.page_key(page)
    entries=deepcopy((job.result or {}).get('entries',[]))
    entry=next((row for row in entries if row['key']==key),None)
    if not entry:return
    info=paragraph_info(page.get('content') or {},any_link=True)
    entry.update(info,status='confirmed' if info.get('has_home_link') else 'failed',
                 message='Изменения сохранены. Ссылка на главную есть.' if info.get('has_home_link') else 'В абзацах нет ссылки на главную. Добавьте вручную.')
    job.result={'entries':entries}
