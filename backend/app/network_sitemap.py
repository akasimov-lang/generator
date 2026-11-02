"""Durable sitemap updates: current Main and all published Webdev pages."""
from datetime import datetime, timezone
from uuid import UUID, uuid5
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree as ET
import httpx
from sqlalchemy import select
from app import models
from app.core.config import get_settings
from app.network_state import domain_name

NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
ET.register_namespace('', NS)
ACTIVE = ('sitemap_queued', 'sitemap_writing', 'sitemap_verify')


def expected(project):
    main = domain_name(project.get('settings', {}).get('canon'))
    pages = project.get('data', {}).get('pages')
    if not main or not isinstance(pages, list): raise ValueError('Webdev не вернул Main и опубликованные страницы.')
    urls = {'https://' + main + '/'}
    for page in pages:
        if not isinstance(page, dict): raise ValueError('Некорректные данные страницы Webdev.')
        # data.pages is the published collection; explicit draft/deleted flags are still excluded.
        if page.get('status') in ('draft','deleted','unpublished','archived') or page.get('isDeleted') or page.get('published') is False: continue
        slug = str(page.get('slug') or '/').strip()
        if slug in ('','/','//'): slug = '/'
        parsed = urlsplit(slug)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not slug.startswith('/'):
            raise ValueError('Некорректный адрес опубликованной страницы: ' + slug[:150])
        urls.add('https://' + main + quote(slug, safe="/%:@-._~!$&'()*+,;="))
    return main, sorted(urls)


def document(urls):
    root = ET.Element('{'+NS+'}urlset')
    for url in urls:
        row=ET.SubElement(root,'{'+NS+'}url'); ET.SubElement(row,'{'+NS+'}loc').text=url
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode')


def locations(xml):
    if not isinstance(xml,str) or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper(): raise ValueError('Некорректный sitemap XML.')
    try: root = ET.fromstring(xml)
    except ET.ParseError as error: raise ValueError('Sitemap содержит неверный XML.') from error
    if root.tag != '{'+NS+'}urlset': raise ValueError('Ожидался sitemap urlset.')
    return [e.text or '' for e in root.findall('{'+NS+'}url/{'+NS+'}loc')]


def receipt(op):
    if not op:return None
    return {'id':op.id,'status':op.status,'message':op.message,'count':len(op.request_payload.get('urls',[])),
            'main':op.request_payload.get('main'),'updated_at':op.updated_at}


def latest(db,site):
    return db.scalar(select(models.NetworkOperation).where(models.NetworkOperation.site_id==site.id,
        models.NetworkOperation.action=='sitemap').order_by(models.NetworkOperation.created_at.desc()).limit(1))


def queue(db,site,request_id,actor,*,manual=False):
    from app.project_network import network_lock
    with network_lock(db,'sitemap-queue:'+site.id):
        id=str(uuid5(UUID(site.id),'sitemap:'+str(request_id)))
        old=db.get(models.NetworkOperation,id)
        if old:return old
        if manual:
            active=latest(db,site)
            if active and active.status in ACTIVE:return active
        op=models.NetworkOperation(id=id,site_id=site.id,action='sitemap',status='sitemap_queued',
            initiator=actor,request_payload={},message='Обновление sitemap поставлено в очередь.')
        db.add(op);db.flush();return op


def public_check(main,urls):
    from app.factual_research import require_public_url
    import asyncio
    url='https://'+main+'/sitemap.xml';asyncio.run(require_public_url(url))
    with httpx.Client(timeout=20,follow_redirects=False) as client:
        with client.stream('GET',url,headers={'Cache-Control':'no-cache'}) as response:
            response.raise_for_status();parts=[];size=0
            for chunk in response.iter_bytes():
                size+=len(chunk)
                if size>4_000_000:raise ValueError('Sitemap превышает 4 МБ.')
                parts.append(chunk)
    actual=locations(b''.join(parts).decode('utf-8-sig'))
    if len(actual)!=len(urls) or set(actual)!=set(urls):raise ValueError('Публичный sitemap ещё не содержит точный список страниц текущего Main.')


def process(db,id):
    from app.project_network import Remote,network_lock
    with network_lock(db,'sitemap:'+id):
        op=db.get(models.NetworkOperation,id)
        if not op or op.status not in ACTIVE:return
        site=db.get(models.Site,op.site_id)
        with network_lock(db,site.id):
            try:
                with Remote(db,site) as remote:
                    project=remote.project();main,urls=expected(project)
                    if op.status=='sitemap_queued':
                        if not isinstance(project.get('sitemap'),str):raise ValueError('Webdev не вернул исходный sitemap для резервной копии.')
                        xml=document(urls)
                        # Persist the complete previous template before any write.
                        op.request_payload={'main':main,'urls':urls,'before':project['sitemap'],'after':xml}
                        if project['sitemap']!=xml:
                            op.status='sitemap_writing';op.message='Сохраняем sitemap в Webdev.';db.commit()
                            try:
                                code,_=remote.request('POST','/projects/update-sitemap',{'project':site.name,'filename':'sitemap',
                                    'contents':quote(xml,safe=";/?:@&=+$,-_.!~*'()#"),'username':get_settings().project_cache_username})
                                op.response_status=code;db.commit()
                            except (httpx.HTTPError,ValueError):
                                pass  # A read verifies ambiguous writes; no automatic resend.
                            project=remote.project()
                        op.status='sitemap_verify';db.commit()
                    if main!=op.request_payload['main'] or expected(project)[1]!=op.request_payload['urls']:
                        raise ValueError('Main или опубликованные страницы изменились во время обновления. Обновите sitemap заново.')
                    if project.get('sitemap')!=op.request_payload['after']:
                        raise ValueError('Webdev пока не подтвердил запись sitemap. Повторная отправка не выполняется.')
                    public_check(main,op.request_payload['urls'])
                    op.status='sitemap_done';op.message=f'Sitemap проверен: {len(urls)} страниц, только {main}.'
                    db.commit()
            except (httpx.HTTPError,ValueError) as error:
                # A queued read may be retried; a submitted write is only rechecked.
                from app.reglue_history import utc
                expired=(datetime.now(timezone.utc)-utc(op.created_at)).total_seconds()>600
                op.status='sitemap_failed' if expired or op.status=='sitemap_queued' else 'sitemap_verify'
                op.message=str(error)[:1000];db.commit()


def process_pending(db,limit=20):
    ids=list(db.scalars(select(models.NetworkOperation.id).where(models.NetworkOperation.action=='sitemap',
        models.NetworkOperation.status.in_(ACTIVE)).order_by(models.NetworkOperation.created_at).limit(limit)))
    for id in ids:
        try:process(db,id)
        except Exception:db.rollback()
    return len(ids)
