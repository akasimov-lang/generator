"""Immutable competitor uploads, shared by brand/GEO; generic examples span all GEO."""
from datetime import datetime, timezone
from contextlib import contextmanager
from html import escape
from html.parser import HTMLParser
import hashlib
import re
from urllib.parse import urlsplit
from sqlalchemy import select, text
from sqlalchemy.orm import defer
from app import models
from app.template_knowledge import brand_key, LIBRARY
from app.template_sources import excerpt, MAX_HTML
from app.site_brands import BRANDS
import json


def is_general(brand):
    return brand_key(brand) in {'общиеключи', 'онлайнказино', 'onlinecasino', 'onlinecasinogeneral'}


def scope(brand, geo):
    name = 'Общие ключи' if is_general(brand) else brand.strip()
    if not name: raise ValueError('Выберите бренд.')
    if not is_general(name):
        key = brand_key(name)
        name = next((canonical for canonical, aliases in BRANDS.items()
                     if key in {brand_key(value) for value in [canonical, *aliases]}
                     or not brand_key(canonical).endswith('casino') and key == brand_key(canonical) + 'casino'), name)
    country = '*' if is_general(brand) else (geo or '').strip().upper()
    if country != '*' and not re.fullmatch('[A-Z]{2}', country): raise ValueError('Выберите GEO.')
    return name, 'general' if is_general(name) else brand_key(name), country


def scope_keys(name):
    _, key, _ = scope(name, 'PL')
    return {key, *(brand_key(alias) for alias in BRANDS.get(name, [])), *([key + 'casino'] if name in BRANDS and not key.endswith('casino') else [])}


@contextmanager
def knowledge_lock(db, key, country):
    # Task-boundary snapshots must stay locked until the caller's commit.
    if db.bind.dialect.name == 'postgresql':
        lock = int(hashlib.sha256(f'template-knowledge:{key}:{country}'.encode()).hexdigest()[:16],16)-2**63
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':lock})
    yield


def metadata(row):
    return {'id': row.id, 'brand': scope(row.brand,row.geo)[0], 'geo': row.geo, 'url': row.url,
            'title': row.title, 'filename': row.filename, 'sha256': row.sha256,
            'added_at': row.created_at.isoformat(), 'structure': row.structure or {}}


def competitor_identity(html, url=''):
    """Read source identity, never execute its HTML or make a network request."""
    class Identity(HTMLParser):
        def __init__(self):
            super().__init__(); self.title=[]; self.inside=False; self.canonical=''
        def handle_starttag(self, tag, attrs):
            attrs=dict(attrs)
            if tag=='title':self.inside=True
            if tag=='link' and 'canonical' in attrs.get('rel','').lower().split():self.canonical=attrs.get('href','')
            if tag=='meta' and attrs.get('property','').lower()=='og:url' and not self.canonical:self.canonical=attrs.get('content','')
        def handle_endtag(self, tag):
            if tag=='title':self.inside=False
        def handle_data(self, value):
            if self.inside:self.title.append(value)
    parser=Identity();parser.feed((html or '')[:64000])
    identity_url=''
    for candidate in [url,parser.canonical]:
        try:
            parsed=urlsplit(candidate or '')
            if parsed.scheme in {'http','https'} and parsed.hostname and not parsed.username and not parsed.password:
                identity_url=candidate;break
        except ValueError:pass
    return {'title':' '.join(' '.join(parser.title).split())[:1000], 'url':identity_url,
            'domain':urlsplit(identity_url).hostname or ''}


def entries(db, brand=None, geo=None, *, html=False):
    query = select(models.TemplateKnowledgeExample).order_by(models.TemplateKnowledgeExample.created_at)
    selected = scope(brand, geo) if brand else None
    if selected: query = query.where(models.TemplateKnowledgeExample.brand_key.in_(scope_keys(selected[0])), models.TemplateKnowledgeExample.geo == selected[2])
    if not html: query = query.options(defer(models.TemplateKnowledgeExample.html))
    result = []
    for row in db.scalars(query):
        item = {**metadata(row), **({'html': row.html} if html else {})}
        if not any(r['sha256']==item['sha256'] and scope(r['brand'],r['geo'])[1:]==scope(item['brand'],item['geo'])[1:] for r in result):result.append(item)
    static = json.loads((LIBRARY / 'index.json').read_text(encoding='utf-8'))
    for item in static:
        if selected and scope(item['brand'], item['geo'])[1:] != selected[1:]: continue
        if any(r['sha256'] == item['sha256'] and scope(r['brand'],r['geo'])[1:] == scope(item['brand'],item['geo'])[1:] for r in result): continue
        result.append({**item, 'structure': {}, **({'html': (LIBRARY / item['file']).read_text(encoding='utf-8')} if html else {})})
    return result


def listing(db, brand=None, geo=None):
    all_items = entries(db)
    groups = {}
    for item in all_items:
        name, key, country = scope(item['brand'], item['geo'])
        group = groups.setdefault((key,country), {'brand':name,'geo':country,'count':0})
        group['count'] += 1
    chosen = entries(db,brand,geo) if brand else []
    return {'count':len(chosen), 'sources':chosen, 'scopes':sorted(groups.values(),key=lambda g:(g['brand'],g['geo']))}


def save(db, brand, geo, content, url, filename, actor_id, *, commit=True, allow_missing_general_url=False):
    name, key, country = scope(brand,geo)
    if not content.strip() or len(content.encode('utf-8')) > MAX_HTML: raise ValueError('Пример пуст или превышает 2 МБ.')
    html = content if re.search(r'<(?:html|body|head)\b',content,re.I) else '<html><body><p>'+escape(content).replace('\n','</p><p>')+'</p></body></html>'
    evidence = excerpt(html)
    url = url.strip()
    if not url:url=competitor_identity(html)['url']
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in {'https','http'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Укажите HTTP(S) адрес главной страницы без логина и пароля.')
    if key == 'general' and ((not url and not allow_missing_general_url) or url and (urlsplit(url).path not in {'','/'} or urlsplit(url).query)):
        raise ValueError('Для общих ключей укажите URL главной страницы домена, например https://example.com/.')
    digest = hashlib.sha256(html.encode('utf-8')).hexdigest()
    with knowledge_lock(db,key,country):
        existing = entries(db,name,country)
        duplicate = next((item for item in existing if item['sha256'] == digest),None)
        if duplicate: return {**duplicate,'duplicate':True}
        if len(existing) >= 30: raise ValueError('Для одной связки можно сохранить до 30 примеров.')
        from app.competitor_site_structure import describe_home
        structure = describe_home(html,url) if key == 'general' and url else ({'status':'needs_url','pages':[]} if key=='general' else {})
        row = models.TemplateKnowledgeExample(brand=name,brand_key=key,geo=country,url=url,title=evidence['title'] or filename,
            filename=filename[:255],html=html,sha256=digest,created_by_user_id=actor_id,structure=structure)
        db.add(row);db.flush()
        if key == 'general' and url:
            db.add(models.BackgroundJob(kind='template_knowledge',payload={'example_id':row.id}))
        if commit:db.commit()
        return {**metadata(row),'duplicate':False}


def remember_source(db, template, source):
    """Snapshot a valid user upload at a task boundary, never on every autosave."""
    capture = source.capture or {}
    if capture.get('source') != 'manual_html' or capture.get('status') != 'google_ready':
        return {'status':'skipped'}
    html = source.google_html or ''
    try:
        name, key, country = scope(template.brand, template.geo)
        if len(html.encode('utf-8')) > MAX_HTML:raise ValueError('Too large')
        evidence = excerpt(html)
    except ValueError:return {'status':'skipped'}
    digest = hashlib.sha256(html.encode('utf-8')).hexdigest()
    if capture.get('knowledge_id') and capture.get('sha256') == digest:return {'status':'skipped'}
    with knowledge_lock(db,key,country):
        existing = entries(db,name,country)
        duplicate = next((entry for entry in existing if entry['sha256']==digest),None)
        if duplicate:return {'status':'duplicate','id':duplicate['id']}
        if len(existing)>=30:return {'status':'full'}
        from app.competitor_site_structure import describe_home
        url = source.url or ''
        try:
            parsed = urlsplit(url)
            if url and (parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password):url=''
        except ValueError:
            url='';parsed=urlsplit('')
        # Historical uploads without a homepage URL remain useful as HTML evidence.
        can_parse = key=='general' and parsed.scheme in {'http','https'} and parsed.hostname and parsed.path in {'','/'} and not parsed.query and not parsed.username and not parsed.password
        row = models.TemplateKnowledgeExample(brand=name,brand_key=key,geo=country,url=url,
            title=evidence['title'] or 'Пример из предыдущей задачи',
            filename=f'Задача {template.id[:8]} · {source.id[:8]}.html',html=html,sha256=digest,
            created_by_user_id=template.created_by_user_id,created_at=source.created_at or datetime.now(timezone.utc),
            structure=describe_home(html,url) if can_parse else {})
        db.add(row);db.flush()
        if can_parse:db.add(models.BackgroundJob(kind='template_knowledge',payload={'example_id':row.id}))
        return {'status':'imported','id':row.id}


def remember_template_sources(db, template):
    sources=db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id==template.id)
        .order_by(models.TemplateSource.created_at)).all()
    return [remember_source(db,template,source) for source in sources]


def import_previous_sources(db):
    """Explicit, idempotent historical import; caller commits and records the audit."""
    counts={'imported':0,'duplicate':0,'skipped':0,'full':0}
    rows=db.execute(select(models.SiteTemplate,models.TemplateSource)
        .join(models.TemplateSource,models.TemplateSource.template_id==models.SiteTemplate.id)
        .where(models.TemplateSource.google_html.is_not(None),models.TemplateSource.google_html!='')
        .order_by(models.TemplateSource.created_at)).all()
    results=[]
    for template,source in rows:
        result=remember_source(db,template,source);counts[result['status']]+=1
        results.append({'template_id':template.id,'source_id':source.id,**result})
    db.flush()
    return {'counts':counts,'sources':results}
