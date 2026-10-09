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
    assert len(concepts) == 10
    for c in concepts:
        assert set(c) == set(AXES)
        assert compare(c, old)['passed']
    assert len({c['hero'] for c in concepts}) == 10
    from app.template_design import CORE_AXES
    for i, candidate in enumerate(concepts):
        for other in concepts[:i]:
            assert sum(candidate[a] != other[a] for a in CORE_AXES) >= 4


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
    async def fail(*args, **kwargs): raise ValueError('No unique design')
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
        result = {'design': document()['design'], 'css': templates.design_css(document()['design']), 'rationale': 'Generated composition'} if 'web art director' in prompt else content().model_dump()
        return {'candidates': [{'content': {'parts': [{'text': json.dumps(result)}]}}], 'usageMetadata': {'totalTokenCount': 10}}
    async def capture(html):
        templates.validate_html(html)
        return {key: base64.b64encode(b'jpeg').decode() for key in ['desktop_hero','desktop_middle','mobile_hero','mobile_middle']}
    monkeypatch.setattr(services, 'call_gemini', fake)
    monkeypatch.setattr(templates, 'screenshots', capture)
    result = asyncio.run(templates.generate(db,r))
    assert result['status']=='ready' and r.status=='ready'
    assert r.document['design_status']=='built' and r.document['design_origin']=='gemini_generated'
    assert r.document['generated_css'] in r.html
    assert 'concepts' not in r.document
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
    from app import services, template_sources
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
    async def fetch(url, profile):
        if 'unavailable' in url: raise ValueError('unavailable')
        return {'google_html':'<html><body>'+('Verified source material. '*20)+'</body></html>', 'capture': {'status':'google_ready','source':'google_rich_results'}}
    monkeypatch.setattr(template_sources,'capture_google',fetch)
    async def gemini(p,prompt):
        assert '"status": "needs_google_html", "excerpt": ""' in prompt
        return {'candidates':[{'content':{'parts':[{'text':'Competitor analysis: '+('Verified information. '*10)}]}}]}
    monkeypatch.setattr(services,'call_gemini',gemini)
    report=asyncio.run(templates.research_competitors(db,r,request,provider))
    assert len(report['sources'])==2 and report['sources'][1]['excerpt']==''
    assert r.document['research']['analysis']


def test_research_inputs_parse_and_validate():
    request = templates.TemplateRequest(brand='Brand', geo='PL', ai_provider_id='g',
        keywords='brand review, brand bonus\nbrand review',
        competitors='example.com, https://example.org/review/\nexample.com https://example.net')
    assert request.search_queries() == ['brand review', 'brand bonus']
    assert request.competitor_urls() == ['https://example.com', 'https://example.org/review', 'https://example.net']
    for patch in ({'keywords': ','.join(str(i) for i in range(6))}, {'competitors': 'ftp://example.com'},
                  {'competitors': 'https://user:password@example.com'}):
        with pytest.raises(ValueError):
            templates.TemplateRequest(brand='Brand', geo='PL', ai_provider_id='g', **patch)


def test_manual_competitors_without_search_provider(db, monkeypatch):
    from app import services, template_sources
    async def fetch(url, profile):
        return {'google_html':'<html><body>'+('Source content. '*20)+'</body></html>', 'capture': {'status':'google_ready','source':'google_rich_results'}}
    async def gemini(*args, **kwargs):
        return {'text': 'Analysis ' * 30}
    monkeypatch.setattr(template_sources, 'capture_google', fetch)
    monkeypatch.setattr(services, 'get_dataforseo_provider', lambda db: pytest.fail('Search must not run'))
    monkeypatch.setattr(services, 'call_gemini', gemini)
    monkeypatch.setattr(services, 'extract_gemini_text', lambda response: response['text'])
    monkeypatch.setattr(services, 'apply_provider_usage', lambda *args: None)
    request = templates.TemplateRequest(brand='Brand', geo='PL', ai_provider_id='g',
        collect_competitors=False, competitors='example.com example.org')
    user = models.User(username='research-user', password_hash=''); db.add(user); db.flush()
    r = models.SiteTemplate(created_by_user_id=user.id, brand='Brand', geo='PL', language='en', request_data=request.model_dump())
    db.add(r); db.commit()
    report = asyncio.run(templates.research_competitors(db, r, request, None))
    assert [s['url'] for s in report['sources']] == ['https://example.com', 'https://example.org']


def test_multiple_queries_merge_manual_sources(db, monkeypatch):
    from app import services, template_sources
    queries = []
    async def serp(provider, query, geo, language):
        queries.append(query)
        return [{'url': 'https://example.com/', 'position': 1}, {'url': f'https://{query}.org', 'position': 2}]
    async def fetch(url, profile):
        return {'google_html':'<html><body>'+('Source content. '*20)+'</body></html>', 'capture': {'status':'google_ready','source':'google_rich_results'}}
    async def gemini(*args, **kwargs):
        return {'text': 'Analysis ' * 30}
    monkeypatch.setattr(services, 'get_dataforseo_provider', lambda db: None)
    monkeypatch.setattr(services, 'call_dataforseo_google_serp', serp)
    monkeypatch.setattr(services, 'extract_organic_serp_items', lambda response: response)
    monkeypatch.setattr(template_sources, 'capture_google', fetch)
    monkeypatch.setattr(services, 'call_gemini', gemini)
    monkeypatch.setattr(services, 'extract_gemini_text', lambda response: response['text'])
    monkeypatch.setattr(services, 'apply_provider_usage', lambda *args: None)
    request = templates.TemplateRequest(brand='Brand', geo='PL', ai_provider_id='g', keywords='one,two', competitors='example.com')
    user = models.User(username='research-user', password_hash=''); db.add(user); db.flush()
    r = models.SiteTemplate(created_by_user_id=user.id, brand='Brand', geo='PL', language='en', request_data=request.model_dump())
    db.add(r); db.commit()
    report = asyncio.run(templates.research_competitors(db, r, request, None))
    assert queries == ['one', 'two']
    assert len(report['sources']) == 3
    assert report['sources'][0]['origin'] == 'manual'


@pytest.mark.parametrize('kind', list(__import__('app.template_compositions', fromlist=['CONCEPTS']).CONCEPTS))
def test_new_compositions_render_valid_html(kind):
    r = row()
    r.document['design']['hero'] = kind
    html = templates.render(r, r.document)
    templates.validate_html(html)
    assert 'topic-card' in html and html.count('<h1>') == 1
    assert '<script' not in html


def test_phone_gallery_assets_and_backwards_compatibility():
    from app.template_phones import FRAMES, frame_svg, data_uri
    from app.site_templates_api import assets
    assert len(FRAMES) == 15
    assert len({frame_svg(f[0]) for f in FRAMES}) == 15
    r = row()
    screen = data_uri('image/jpeg', b'fixture-screen')
    logo = data_uri('image/png', b'fixture-logo')
    r.document['brand_media'] = {'screens': [screen]*3, 'frames': [FRAMES[0][0]]*3, 'logo': logo}
    r.document['content']['mobile_gallery_heading'] = 'Brand mobile website'
    r.html = templates.render(r,r.document)
    assert 'id="mobile-screens"' in r.html
    templates.validate_html(r.html)
    exported = downloadable_html(r)
    assert 'src="assets/phone-1.svg"' in exported
    assert 'url(assets/brand-logo.png)' in exported
    assert assets(r)['assets/brand-logo.png'] == b'fixture-logo'
    assert screen in assets(r)['assets/phone-1.svg']
    assert 'mobile-screens' not in templates.render(row(), row().document).split('</style>')[1]


def test_brand_url_validation():
    req = templates.TemplateRequest(brand='Brand',geo='PL',ai_provider_id='g',brand_url='example.com')
    assert req.brand_url == 'https://example.com'
    for url in ['example.com example.org','file:///etc/passwd','https://user:pass@example.com']:
        with pytest.raises(ValueError):
            templates.TemplateRequest(brand='Brand',geo='PL',ai_provider_id='g',brand_url=url)


def test_phone_capture_rejects_private_sources():
    from app.template_phones import capture_brand
    with pytest.raises(ValueError, match='Non-public'):
        asyncio.run(capture_brand('http://127.0.0.1', 'Brand'))


@pytest.mark.parametrize('unsafe', ['@import "https://example.com";', 'x{background:url(https://example.com)}', '</style><script>alert(1)</script>', 'a{background:u\\72l(x)}'])
def test_generated_css_rejects_external_and_active_content(unsafe):
    from app.template_generated_design import validate_generated_css
    with pytest.raises(ValueError):
        validate_generated_css(templates.design_css(document()['design']) + unsafe)


def test_asset_library_matching_evidence_and_export():
    from app.template_asset_library import build_snapshot, catalog
    from app.site_templates_api import assets
    lib = catalog()
    assert len(lib['brands']) >= 20 and len(lib['providers']) >= 15
    facts = 'Pin-Up supports Visa payments and offers Pragmatic Play games.'
    c = content()
    c.payment_systems = [templates.AssetMention(id='visa', source_url='facts', evidence=facts),
                         templates.AssetMention(id='mastercard', source_url='facts', evidence=facts)]
    c.game_providers = [templates.AssetMention(id='pragmaticplay', source_url='facts', evidence=facts)]
    snap = build_snapshot('pin up',c,None,facts)
    assert snap['logo'] and snap['favicon']
    assert [x['id'] for x in snap['payments']] == ['visa']
    assert [x['id'] for x in snap['providers']] == ['pragmaticplay']
    r=row();r.document['library_assets']=snap;r.document['content']=c.model_dump();r.html=templates.render(r,r.document)
    exported=downloadable_html(r)
    assert 'rel="icon"' in exported and 'assets/library-favicon-' in exported
    assert 'assets/payments-visa-logo.png' in exported
    assert 'assets/providers-pragmaticplay-logo.png' in exported
    assert assets(r)['assets/payments-visa-logo.png'].startswith(b'\x89PNG')
    assert not build_snapshot('Unknown Brand',c,None,'')['payments']
    competitor='Another Casino accepts Visa payments.'
    c.payment_systems=[templates.AssetMention(id='visa',source_url='https://example.com',evidence=competitor)]
    research={'sources':[{'url':'https://example.com','status':'fetched','excerpt':competitor}]}
    assert not build_snapshot('Pin-Up',c,research,'')['payments']


def test_sources_autosave_conflicts_and_stages(db):
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    user = models.User(username='sources', password_hash='')
    db.add(user); db.flush()
    r = models.SiteTemplate(created_by_user_id=user.id, brand='Brand', geo='DE', language='en',
        request_data={'ai_provider_id':'g'}, status='awaiting_sources')
    other = models.SiteTemplate(created_by_user_id=user.id, brand='Other', geo='DE', language='en', request_data={}, status='awaiting_sources')
    db.add_all([r, other]); db.commit()
    app.dependency_overrides[require_auth] = lambda: {'id':user.id, 'is_admin':True}
    path = f'/site-templates/{r.id}'
    response = client.post(path+'/sources', json={'html':'unfinished draft'})
    assert response.status_code == 201
    source = response.json(); assert source['capture']['status']=='invalid_html'
    assert client.get(path+'/sources').json()[0]['html']=='unfinished draft'
    html = '<html><body><p>'+('Verified information on the competitor. '*20)+'</p></body></html>'
    response = client.put(path+'/sources/'+source['id'], json={'html':html,'revision':source['revision']})
    assert response.status_code==200 and response.json()['capture']['status']=='google_ready'
    assert client.put(path+'/sources/'+source['id'], json={'html':'overwrite','revision':source['revision']}).status_code==409
    assert client.put(f'/site-templates/{other.id}/sources/'+source['id'], json={'html':html,'revision':2}).status_code==404
    assert client.post(path+'/generate-design').status_code==409
    assert client.post(path+'/generate-content').status_code==202
    assert client.put(path+'/sources/'+source['id'],json={'html':html,'revision':2}).status_code==409
    job = db.scalar(select(models.BackgroundJob)); assert job.payload['stage']=='content'
    r.document=document(); r.status='content_ready'; db.commit()
    assert client.post(path+'/generate-design').status_code==202
    jobs=db.scalars(select(models.BackgroundJob)).all(); assert jobs[-1].payload['stage']=='design'


@pytest.mark.parametrize('patch', [{'heading':'1. Overview'}, {'heading':'Sources'}, {'intro':'Here is your HTML'}, {'intro':'See https://source.test/'}, {'intro':'Claim [1]'}, {'intro':'<!-- Gemini -->'}])
def test_rejects_public_generation_artifacts(patch):
    with pytest.raises(ValueError): templates.PageContent.model_validate({**content().model_dump(),**patch})


def test_content_stage_does_not_call_designer(db,monkeypatch):
    from app import services
    user=models.User(username='two-stage',password_hash='')
    provider=models.AiProvider(name='g',provider_type='gemini',endpoint_url='https://api.test',api_key='test')
    db.add_all([user,provider]);db.flush()
    request=templates.TemplateRequest(brand='Brand',geo='DE',ai_provider_id=provider.id,collect_competitors=False)
    r=models.SiteTemplate(created_by_user_id=user.id,brand='Brand',geo='DE',language='en',request_data=request.model_dump())
    db.add(r);db.commit()
    calls=[]
    async def gemini(provider,prompt,**kwargs):
        calls.append(prompt)
        return {'candidates':[{'content':{'parts':[{'text':json.dumps(content().model_dump())}]}}]}
    monkeypatch.setattr(services,'call_gemini',gemini)
    assert asyncio.run(templates.generate(db,r,content_only=True))['status']=='content_ready'
    assert len(calls)==1 and not r.html and 'design' not in r.document


def test_research_stage_waits_for_manual_html_without_generating_content(db, monkeypatch):
    from app import services
    user = models.User(username='three-stage', password_hash='')
    provider = models.AiProvider(name='g',provider_type='gemini',endpoint_url='https://api.test',api_key='test')
    db.add_all([user,provider]); db.flush()
    request=templates.TemplateRequest(brand='Brand',geo='DE',ai_provider_id=provider.id,collect_competitors=False)
    row=models.SiteTemplate(created_by_user_id=user.id,brand='Brand',geo='DE',language='en',request_data=request.model_dump())
    db.add(row);db.commit()
    async def fail(*args,**kwargs): raise AssertionError('Research without sources must not generate content')
    monkeypatch.setattr(services,'call_gemini',fail)
    assert asyncio.run(templates.generate(db,row,research_only=True))['status']=='awaiting_sources'
    assert 'content' not in row.document
    row.document={'research':{'sources':[{'status':'fetched','excerpt':'verified'}],'analysis':'analysis'}}
    db.commit()
    assert asyncio.run(templates.generate(db,row,research_only=True))['status']=='sources_ready'
    assert 'content' not in row.document and not row.html


def test_new_template_starts_with_research_and_retry_preserves_stage(db):
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db
    user=models.User(username='new-three',password_hash='')
    provider=models.AiProvider(name='g',provider_type='gemini',endpoint_url='https://api.test',api_key='test')
    db.add_all([user,provider]);db.commit()
    app.dependency_overrides[require_auth]=lambda:{'id':user.id,'is_admin':True}
    client=TestClient(app)
    response=client.post('/site-templates',json={'brand':'Brand','geo':'DE','ai_provider_id':provider.id,'collect_competitors':False})
    assert response.status_code==202
    row=db.get(models.SiteTemplate,response.json()['id'])
    assert db.scalar(select(models.BackgroundJob)).payload['stage']=='research'
    row.status='failed';db.commit()
    assert client.post(f'/site-templates/{row.id}/retry').status_code==202
    assert all(job.payload['stage']=='research' for job in db.scalars(select(models.BackgroundJob)))
