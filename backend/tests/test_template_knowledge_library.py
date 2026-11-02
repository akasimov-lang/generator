import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import select
from app import models, background_jobs, competitor_site_structure as crawl
from app.db import get_db
from app.security import require_auth
from app.site_templates_api import router
from app.template_knowledge_library import save, listing
from app.template_knowledge import attach_sources, source_excerpt
from test_site_templates import db, content
from test_template_knowledge import setup_template

HTML='<html><head><title>Example Lemon Casino</title></head><body><h1>Example brand</h1><p>'+('Original competitor material and useful information. '*15)+'</p><a href="/bonus/">Bonus</a><a href="https://outside.test/page/">Outside</a></body></html>'


def client(db,user):
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[require_auth]=lambda:{'id':user.id,'is_admin':True}
    return TestClient(app)


def test_upload_scoped_count_dedup_and_automatic_template_snapshot(db):
    user,provider,_=setup_template(db)
    api=client(db,user)
    payload={'brand':'Lemon Casino','geo':'PL','html':HTML,'filename':'competitor.html'}
    saved=api.post('/site-templates/knowledge',json=payload)
    assert saved.status_code==201,saved.text
    assert saved.json()['count']==2  # Existing imported Lemon PL plus this example.
    assert api.post('/site-templates/knowledge',json=payload).json()['source']['duplicate']
    assert api.get('/site-templates/knowledge?brand=Lemon-Casino&geo=pl').json()['count']==2
    assert api.get('/site-templates/knowledge?brand=Lemon-Casino&geo=CZ').json()['count']==0
    assert 'html' not in api.get('/site-templates/knowledge?brand=Lemon-Casino&geo=pl').json()['sources'][0]
    created=api.post('/site-templates',json={'brand':'Lemon Casino','geo':'PL','language':'pl','ai_provider_id':provider.id,'collect_competitors':False})
    assert created.status_code==202,created.text
    sources=api.get('/site-templates/'+created.json()['id']+'/sources').json()
    assert len(sources)==2 and any(s['html']==HTML for s in sources)
    assert len(db.scalars(select(models.TemplateKnowledgeExample)).all())==1


def test_generic_all_geo_source_structure_and_background_dispatch(db):
    user,provider,_=setup_template(db);api=client(db,user)
    payload={'brand':'Общие ключи','geo':'PL','html':HTML,'url':'https://example.test/','filename':'home.html'}
    result=api.post('/site-templates/knowledge',json=payload)
    assert result.status_code==201,result.text
    row=db.scalar(select(models.TemplateKnowledgeExample))
    assert row.geo=='*' and row.structure['status']=='queued'
    assert len(row.structure['pages'])==2
    for geo in ['PL','CZ','DE']:
        assert api.get('/site-templates/knowledge',params={'brand':'Онлайн казино','geo':geo}).json()['count']==1
    assert api.get('/site-templates/knowledge',params={'brand':'Other','geo':'PL'}).json()['count']==0
    queued=[];background_jobs.dispatch_pending(db,lambda id,queue:queued.append(queue))
    assert queued==['maintenance']
    template=models.SiteTemplate(created_by_user_id=user.id,brand='Онлайн казино',geo='DE',language='de',request_data={})
    db.add(template);db.flush();attach_sources(db,template);db.commit()
    source=db.scalar(select(models.TemplateSource).where(models.TemplateSource.template_id==template.id))
    assert source.google_html==HTML and len(source_excerpt(source)['site_structure']['pages'])==2
    row.structure={**row.structure,'status':'completed','pages':[{'url':row.url,'title':'Home'},{'url':row.url+'bonus/','title':'Welcome bonus'}]};db.commit()
    attach_sources(db,template);db.commit()
    assert source.capture['site_structure']['status']=='completed'
    assert len(db.scalars(select(models.TemplateSource).where(models.TemplateSource.template_id==template.id)).all())==1


@pytest.mark.parametrize('change',[{'html':''},{'html':'x'},{'brand':''},{'geo':''},{'html':'x'*2_000_001}])
def test_invalid_upload_never_saved(db,change):
    user,_,_=setup_template(db);api=client(db,user)
    result=api.post('/site-templates/knowledge',json={'brand':'Lemon Casino','geo':'PL','html':HTML,**change})
    assert result.status_code==422
    assert not db.scalar(select(models.TemplateKnowledgeExample.id))


def test_generic_requires_main_url_and_plain_text_supported(db):
    user,_,_=setup_template(db);api=client(db,user)
    result=api.post('/site-templates/knowledge',json={'brand':'Общие ключи','html':HTML})
    assert result.status_code==422
    assert api.post('/site-templates/knowledge',json={'brand':'Other','geo':'CZ','html':'Useful content. '*30,'filename':'source.txt'}).status_code==201


def test_parser_uses_home_and_sitemap_without_cross_domain_or_query_traps(monkeypatch):
    calls=[]
    async def public(url):
        assert 'outside.test' not in url and '127.0.0.1' not in url
    monkeypatch.setattr(crawl,'require_public_url',public)
    def response(request):
        calls.append(str(request.url))
        if request.url.path=='/sitemap.xml':return httpx.Response(200,text='<urlset><url><loc>https://example.test/terms/</loc></url><url><loc>http://127.0.0.1/private</loc></url></urlset>')
        return httpx.Response(200,text=f'<html><title>{request.url.path}</title><h1>Inner page</h1><h2>Conditions</h2></html>')
    original=httpx.AsyncClient
    monkeypatch.setattr(crawl.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(response),**kw))
    structure=asyncio.run(crawl.collect(HTML+'<a href="/?q=1">trap</a><a href="http://example.test:invalid/">invalid</a>','https://example.test/'))
    assert structure['status']=='completed'
    assert {p['path'] for p in structure['pages']}=={'/','/bonus/','/terms/'}
    assert structure['pages'][1]['headings']==[{'level':'h1','text':'Inner page'},{'level':'h2','text':'Conditions'}]
    assert not any('outside.test' in url or '?q' in url for url in calls)


def test_generic_knowledge_and_structure_reach_gemini_in_another_geo(db,monkeypatch):
    from app import services,site_templates as templates
    user,provider,_=setup_template(db)
    save(db,'Общие ключи','PL',HTML,'https://example.test/','home.html',user.id)
    request=templates.TemplateRequest(brand='Онлайн казино',geo='CZ',language='cs',ai_provider_id=provider.id,collect_competitors=False)
    template=models.SiteTemplate(created_by_user_id=user.id,brand=request.brand,geo=request.geo,language=request.language,request_data=request.model_dump())
    db.add(template);db.commit();prompts=[]
    async def gemini(provider,prompt,**kwargs):
        prompts.append(prompt)
        assert 'Original competitor material' in prompt
        if len(prompts)==1:
            assert 'site_structure' in prompt and '/bonus/' in prompt
            return {'candidates':[{'content':{'parts':[{'text':'Useful analysis. '*30}]}}]}
        import json
        return {'candidates':[{'content':{'parts':[{'text':json.dumps(content().model_dump())}]}}]}
    monkeypatch.setattr(services,'call_gemini',gemini)
    assert asyncio.run(templates.generate(db,template,content_only=True))['status']=='content_ready'
    assert len(prompts)==2
