"""Bounded public same-domain discovery from the uploaded home page and sitemap."""
import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree
import httpx
from app import models
from app.factual_research import require_public_url

LIMIT = 30
MAX_BYTES = 2_000_000


def internal_url(base, value):
    if not isinstance(value,str):return None
    try:
        parsed = urlsplit(urljoin(base, value))
        expected = urlsplit(base)
        port = parsed.port
    except ValueError:return None
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password: return None
    if parsed.hostname.lower().removeprefix('www.') != expected.hostname.lower().removeprefix('www.'): return None
    if port not in {None,80,443} or parsed.query: return None
    if parsed.path.lower().endswith(('.jpg','.png','.gif','.webp','.svg','.pdf','.zip','.css','.js','.woff','.ico')): return None
    return urlunsplit((parsed.scheme,parsed.netloc,parsed.path or '/','',''))


class Page(HTMLParser):
    def __init__(self, base):
        super().__init__(); self.base=base; self.links={}; self.headings=[]; self.title=[]; self.current=None; self.text=[]; self.href=None; self.hidden=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in {'script','style','noscript','template'}: self.hidden+=1
        if self.hidden:return
        if tag in {'h1','h2','title'}: self.current=tag;self.text=[]
        if tag=='a': self.href=internal_url(self.base,attrs.get('href',''));self.text=[]
    def handle_data(self,data):
        if not self.hidden and (self.current or self.href):self.text.append(data)
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript','template'}:self.hidden=max(0,self.hidden-1)
        value=' '.join(' '.join(self.text).split())[:300]
        if tag=='a' and self.href:
            self.links.setdefault(self.href,value);self.href=None;self.text=[]
        if tag==self.current:
            if tag=='title':self.title.append(value)
            elif value:self.headings.append({'level':tag,'text':value})
            self.current=None;self.text=[]
    def summary(self):
        return {'url':self.base,'path':urlsplit(self.base).path or '/', 'title':' '.join(self.title), 'headings':self.headings[:30]}


def parse(html,url):
    page=Page(url);page.feed(html);return page


def describe_home(html,url):
    page=parse(html,url)
    urls=[url,*[u for u in page.links if u!=url]][:LIMIT]
    return {'status':'queued','limit':LIMIT,'pages':[page.summary(),*[{'url':u,'path':urlsplit(u).path or '/', 'title':page.links.get(u,''),'status':'discovered'} for u in urls[1:]]], 'errors':[]}


async def fetch(client,url,base):
    for _ in range(4):
        if internal_url(base,url) is None:raise ValueError('Переход на другой домен запрещён.')
        await require_public_url(url)
        async with client.stream('GET',url,follow_redirects=False) as response:
            if response.is_redirect:
                url=urljoin(url,response.headers.get('location',''));continue
            response.raise_for_status()
            content=bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content)>MAX_BYTES:raise ValueError('Страница превышает 2 МБ.')
            return content.decode(response.encoding or 'utf-8',errors='replace')
    raise ValueError('Слишком много перенаправлений.')


async def collect(html,url):
    home=parse(html,url);found=dict(home.links);found.pop(url,None);errors=[]
    async with httpx.AsyncClient(timeout=12,headers={'User-Agent':'PagePilot competitor structure reader'}) as client:
        sitemap=urljoin(url,'/sitemap.xml')
        try:
            xml=await fetch(client,sitemap,url)
            if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():raise ValueError('Неподдерживаемый sitemap XML.')
            root=ElementTree.fromstring(xml)
            locations=[n.text for n in root.iter() if n.tag.rsplit('}',1)[-1]=='loc' and n.text]
            if root.tag.rsplit('}',1)[-1]=='sitemapindex':
                for child in locations[:2]:
                    if not internal_url(url,child):continue
                    text=await fetch(client,child,url)
                    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():continue
                    sub=ElementTree.fromstring(text)
                    for node in sub.iter():
                        if node.tag.rsplit('}',1)[-1]=='loc' and node.text:
                            if target:=internal_url(url,node.text):found.setdefault(target,'')
            else:
                for loc in locations:
                    if target:=internal_url(url,loc):found.setdefault(target,'')
        except (httpx.HTTPError,ValueError,ElementTree.ParseError):pass  # Home-page links remain sufficient.
        targets=[u for u in found if u!=url][:LIMIT-1]
        semaphore=asyncio.Semaphore(3)
        async def read(target):
            async with semaphore:
                try:
                    page=parse(await fetch(client,target,url),target)
                    return {**page.summary(),'status':'parsed'}
                except Exception as error:
                    errors.append({'url':target,'message':str(error)[:250]})
                    return {'url':target,'path':urlsplit(target).path,'title':found[target], 'status':'unavailable'}
        pages=[{**home.summary(),'status':'parsed'},*await asyncio.gather(*(read(t) for t in targets))]
    return {'status':'completed','limit':LIMIT,'pages':pages,'errors':errors,'checked_at':datetime.now(timezone.utc).isoformat()}


def execute(db,job):
    row=db.get(models.TemplateKnowledgeExample,job.payload['example_id'])
    if not row:raise ValueError('Пример конкурента не найден.')
    row.structure={**row.structure,'status':'running'};db.commit()
    try:row.structure=asyncio.run(collect(row.html,row.url));db.commit()
    except Exception as error:
        row.structure={**row.structure,'status':'failed','error':str(error)[:400]};db.commit();raise
    return {'example_id':row.id,'pages':len(row.structure['pages'])}
