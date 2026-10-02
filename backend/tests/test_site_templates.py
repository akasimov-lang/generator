import asyncio
import base64
import copy
import io
import json
from types import SimpleNamespace
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models, site_templates as templates, background_jobs
from app.db import Base, get_db
from app.security import require_auth
from app.site_templates_api import router, downloadable_html
from app.template_design import AXES, choose_concepts, compare, normalize


def content():
    return templates.PageContent(title='Brand — overview', description='An independent brand guide.',
        heading='A clear guide to Brand', intro='Explore the available information and check the current conditions before you make a decision.',
        menu_label='Menu', cta_label='Explore the guide', faq_title='Questions and answers',
        footer_text='An independent information page. Check current terms with the service provider.',
        sections=[{'id': key, 'title': title,
            'paragraphs': ['Read the current terms on the provider website before creating an account. Availability and conditions depend on your location.',
                'Compare the published information with your requirements. Keep a copy of the conditions relevant to your decision.'],
            'bullets': ['Check regional availability', 'Review the current terms', 'Find verified support contacts'],
            'table': [['What to check', 'Where to look'], ['Account requirements', 'Registration terms'], ['Restrictions', 'Regional terms']] if i == 0 else []}
            for i, (key, title) in enumerate([('overview', 'Understanding the service'), ('conditions', 'Conditions and availability'), ('support', 'Finding reliable information')])],
        faq=[{'question': q, 'answer': 'Consult the current terms and independently verified information before proceeding.'}
            for q in ['Where can I find current terms?', 'How do I check availability?', 'Where can I get support?']])


def document():
    c = content()
    return {'content': c.model_dump(), 'menu': templates.default_menu(c),
        'design': choose_concepts([], 'test')[0], 'scope': 'brand_geo', 'comparisons': [], 'design_status': 'built'}


def row():
    return SimpleNamespace(id='template', brand='Brand', geo='DE', language='en', status='ready',
        request_data={'uniqueness_scope': 'brand_geo'}, document=document(), html=None)


@pytest.fixture
def db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_unique_protocol_compares_all_fifteen_axes_and_hard_rules():
    old = {key: values[0] for key, values in AXES.items()}
    distinct = {key: values[-1] for key, values in AXES.items()}
    assert compare(distinct, old)['passed']
    for keys in [('hero', 'navigation'), ('shell', 'typography', 'shape_language'), ('palette', 'density', 'header', 'footer_pattern')]:
        candidate = {**distinct, **{key: old[key] for key in keys}}
        assert not compare(candidate, old)['passed']
    assert compare({**distinct, 'palette': old['palette'], 'density': old['density']}, old)['passed']
    concepts = choose_concepts([{'id': 'old', 'design': old}], 'new')
    assert len(concepts) == 3
    for c in concepts:
        assert set(c) == set(AXES)
        assert compare(c, old)['passed']
    for key in ('hero', 'navigation', 'shell', 'typography', 'palette', 'visual_style'):
        assert len({c[key] for c in concepts}) == 3


def test_scope_is_brand_geo_or_every_template(db):
    user = models.User(username='test', password_hash='')
    db.add(user); db.flush()
    rows = [models.SiteTemplate(created_by_user_id=user.id, brand=brand, geo=geo, language='en',
        status='ready', document=document(), request_data={'uniqueness_scope': 'brand_geo'})
        for brand, geo in [('  BRAND  ', 'de'), ('Other', 'DE'), ('Brand', 'PL'), ('Brand', 'DE')]]
    db.add_all(rows); db.commit()
    assert [r.id for r in templates.history_rows(db, rows[3])] == [rows[0].id]
    rows[3].request_data = {'uniqueness_scope': 'global'}
    assert len(templates.history_rows(db, rows[3])) == 3
    assert normalize(' Ｂｒａｎｄ ') == 'brand'


def test_static_structure_escaping_and_menu_conversion():
    r = row()
    r.brand = '</style><script>alert(1)</script>'
    d = r.document
    d['content']['intro'] = '<img src=x onerror=alert(1)>'
    d['menu'][0].update(mode='real', url='/real-page/')
    html = templates.render(r, d)
    assert '<script' not in html and '<img src=x' not in html
    assert 'href="/real-page/"' in html and 'href="#conditions"' in html
    assert html.count('class="section"') == 5
    assert '<main' not in html and 'onclick=' not in html
    assert '<div class="logo"' in html and '.logo img' in html
    assert html.count('data-menu-id="overview"') == 3
    assert '<details class="mobile-nav">' in html and '<article class="faq-item">' in html


@pytest.mark.parametrize('url', ['javascript:alert(1)', '//evil.test', '/%2fevil.test', '/\\evil.test', 'data:text/html,test', 'https://user:pass@evil.test', '/%0aevil', 'http://example.test'])
def test_reject_unsafe_real_links(url):
    with pytest.raises(ValueError):
        templates.MenuItem(id='x', label='X', section_id='overview', mode='real', url=url)


@pytest.mark.parametrize('mutation', [
    lambda h: h.replace('<body>', '<body><main>').replace('</body>', '</main></body>'),
    lambda h: h.replace('class="section"', 'class="section extra"', 1),
    lambda h: h.replace('</head>', '<script type="application/ld+json">{}</script></head>'),
    lambda h: h.replace('role="img"', 'onclick="alert(1)"'),
    lambda h: h.replace('aria-label="Brand"></div>', 'aria-label="Brand"> </div>'),
])
def test_structural_gate_rejects_invalid_html(mutation):
    r = row()
    with pytest.raises(ValueError):
        templates.validate_html(mutation(templates.render(r, r.document)))


def test_download_html_uses_asset_and_bundle_is_self_contained():
    r = row(); r.html = templates.render(r, r.document)
    assert 'src="assets/hero.svg"' in downloadable_html(r)
    archive = zipfile.ZipFile(io.BytesIO(templates.build_archive(r)))
    assert {'index.html', 'template.json', 'validation.json'} <= set(archive.namelist())
    assert b'<svg viewBox' in archive.read('index.html')
    r.status = 'failed'
    with pytest.raises(ValueError): templates.build_archive(r)


def test_api_auth_queue_edit_and_download(db):
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    assert client.get('/site-templates').status_code == 401
    user = models.User(username='owner', password_hash='')
    provider = models.AiProvider(name='Gemini', provider_type='gemini', endpoint_url='https://api.test', api_key='secret')
    db.add_all([user, provider]); db.commit()
    app.dependency_overrides[require_auth] = lambda: {'id': user.id, 'is_admin': True}
    response = client.post('/site-templates', json={'brand': 'Brand', 'geo': 'DE', 'language': 'en',
        'ai_provider_id': provider.id, 'collect_competitors': False})
    assert response.status_code == 202, response.text
    tid = response.json()['id']
    job = db.scalar(select(models.BackgroundJob))
    assert job.kind == 'site_template'
    assert client.get(f'/site-templates/{tid}/download/html').status_code == 409
    r = db.get(models.SiteTemplate, tid)
    r.document = document(); r.status = 'ready'; r.html = templates.render(r, r.document); db.commit()
    response = client.get(f'/site-templates/{tid}/download/images')
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(response.json()['base64'])))
    assert archive.namelist() == ['assets/hero.svg']
    assert b'currentColor' not in archive.read('assets/hero.svg')
    edit = {'revision': 1, 'content': r.document['content'], 'menu': r.document['menu']}
    assert client.put(f'/site-templates/{tid}', json={**edit, 'revision': 999}).status_code == 409
    assert client.put(f'/site-templates/{tid}', json=edit).status_code == 202
    assert r.revision == 2 and r.status == 'queued'
    assert client.put(f'/site-templates/{tid}', json=edit).status_code == 409


def test_worker_failure_is_visible_and_recoverable(db, monkeypatch):
    user = models.User(username='worker', password_hash=''); db.add(user); db.flush()
    r = models.SiteTemplate(created_by_user_id=user.id, brand='Brand', geo='DE', language='en', request_data={})
    db.add(r); db.flush()
    job = models.BackgroundJob(kind='site_template', payload={'template_id': r.id})
    db.add(job); db.commit()
    async def fail(*args): raise ValueError('No unique design')
    monkeypatch.setattr(templates, 'generate', fail)
    assert background_jobs.run_job(db, job.id)['status'] == 'failed'
    assert r.status == 'failed' and r.error == 'No unique design'
    assert background_jobs.run_job(db, job.id)['status'] == 'skipped'


def test_generation_uses_gemini_and_persists_audited_result(db, monkeypatch):
    from app import services
    user = models.User(username='generate', password_hash='')
    provider = models.AiProvider(name='Gemini', provider_type='gemini', endpoint_url='https://api.test', api_key='key')
    db.add_all([user, provider]); db.flush()
    request = templates.TemplateRequest(brand='Brand', geo='DE', language='en', ai_provider_id=provider.id, collect_competitors=False)
    r = models.SiteTemplate(created_by_user_id=user.id, brand='Brand', geo='DE', language='en', request_data=request.model_dump())
    db.add(r); db.commit()
    calls=[]
    async def fake(provider, prompt, **kwargs):
        calls.append(prompt)
        result = {'selected': 1, 'rationale': 'Readable composition'} if 'web art director' in prompt else content().model_dump()
        return {'candidates': [{'content': {'parts': [{'text': json.dumps(result)}]}}], 'usageMetadata': {'totalTokenCount': 10}}
    async def capture(html):
        templates.validate_html(html)
        return {key: base64.b64encode(b'jpeg').decode() for key in ['desktop_hero','desktop_middle','mobile_hero','mobile_middle']}
    monkeypatch.setattr(services, 'call_gemini', fake)
    monkeypatch.setattr(templates, 'screenshots', capture)
    result = asyncio.run(templates.generate(db,r))
    assert result['status']=='ready' and r.status=='ready'
    assert r.document['design_status']=='built' and len(r.document['concepts'])==3
    assert r.document['scope']=='brand_geo' and all(m['mode']=='fake' for m in r.document['menu'])
    assert len(calls)==2 and provider.total_tokens_used==20
    assert len(r.document['screenshots'])==4


def test_visual_gate_uses_images_and_rejects_recolored_clones(monkeypatch):
    from app import services
    provider=SimpleNamespace(prompt_tokens_used=0,completion_tokens_used=0,total_tokens_used=0)
    old=row(); old.document['screenshots']={key:'image' for key in ['desktop_hero','desktop_middle','mobile_hero','mobile_middle']}
    async def fake(provider,prompt,**kwargs):
        assert len(kwargs['images'])==8
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'score':39,'same_first_screen':True,
            'same_header_hero_next':False,'same_mobile_sequence':False,'explanation':'Recolored first screen'})}]}}]}
    monkeypatch.setattr(services,'call_gemini',fake)
    result=asyncio.run(templates.audit_visual(provider,old.document['screenshots'],[old]))
    assert not result[0]['passed']


def test_research_does_not_invent_inaccessible_source_content(db,monkeypatch):
    from app import services, factual_research
    user=models.User(username='research',password_hash='')
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://api.test',api_key='key')
    db.add_all([user,provider]);db.flush()
    request=templates.TemplateRequest(brand='Brand',geo='DE',ai_provider_id=provider.id)
    r=models.SiteTemplate(created_by_user_id=user.id,brand='Brand',geo='DE',language='en',request_data=request.model_dump())
    db.add(r);db.commit()
    monkeypatch.setattr(services,'get_dataforseo_provider',lambda db:provider)
    async def serp(*args): return {}
    monkeypatch.setattr(services,'call_dataforseo_google_serp',serp)
    monkeypatch.setattr(services,'extract_organic_serp_items',lambda x:[{'url':'https://read.test','position':1},{'url':'https://unavailable.test','position':2}])
    async def fetch(url):
        if 'unavailable' in url: raise ValueError('unavailable')
        return {'url':url,'status':'fetched','excerpt':'Verified source material'}
    monkeypatch.setattr(factual_research,'fetch_source',fetch)
    async def gemini(p,prompt):
        assert '"status": "unavailable", "excerpt": ""' in prompt
        return {'candidates':[{'content':{'parts':[{'text':'Competitor analysis: '+('Verified information. '*10)}]}}]}
    monkeypatch.setattr(services,'call_gemini',gemini)
    report=asyncio.run(templates.research_competitors(db,r,request,provider))
    assert len(report['sources'])==2 and report['sources'][1]['excerpt']==''
    assert r.document['research']['analysis']
