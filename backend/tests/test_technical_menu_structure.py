import asyncio
import copy
import json

import pytest
from sqlalchemy import select

from app import models, services, technical_pages
from app.schemas import MenuStructurePreviewRequest, GeneratedMenuStructureApply
from test_generation_modes import db, make_site


@pytest.mark.parametrize('kind,language,count', [('monobrand','pl-PL',8),('general','cs-CZ',10)])
@pytest.mark.parametrize('levels',[1,2,3])
def test_technical_structure_uses_site_type_locale_and_allows_standard_labels(db,monkeypatch,kind,language,count,levels):
    site=make_site(db)
    site.site_type=kind;site.brand='Lemon Casino';site.homepage_title='Lemon Casino';site.cache_geo='PL' if language.startswith('pl') else 'CZ';site.cache_language=language
    original={'header':[{'id':1,'title':'Home','slug':'/'}],'footer':[]}
    site.default_menu=copy.deepcopy(original)
    other=models.Site(name='peer.test',base_url='https://peer.test',publication_endpoint='/',cache_geo=site.cache_geo,default_menu={'footer':[{'title':'Kontakty','slug':'/kontakty/'}]})
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://provider.test',api_key='test',is_active=True)
    db.add_all([provider,other]);db.commit()
    prompts=[]
    async def generate(p,prompt):
        prompts.append(prompt)
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'brand':'Lemon Casino','labels':{page['key']:('Polityka '+page['key'] if language.startswith('pl') else 'Zásady '+page['key']) for page in technical_pages.menu_catalog(site)}})}]}}]}
    monkeypatch.setattr(services,'call_gemini',generate)
    roots=count if levels==1 else 2
    result=asyncio.run(services.generate_menu_structure_preview(db,provider,site,MenuStructurePreviewRequest(menu_type='footer',mode='technical_pages',levels=levels,top_level_count=roots)))
    assert result['levels']==levels and result['top_level_count']==roots
    assert len(result['items'])==roots
    all_items=services._flatten_project_menu_items(result['items'])
    assert len(all_items)==count
    keys={item['technical_page_key'] for item in all_items}
    assert ('editorial' in keys)==(kind=='general')
    assert ('advertising' in keys)==(kind=='general')
    assert all(item['content_kind']=='technical_page' for item in all_items)
    assert len(prompts)==1 and language in prompts[0] and kind in prompts[0]
    assert site.default_menu==original
    assert not db.scalars(select(models.Section)).all()
    payload=GeneratedMenuStructureApply.model_validate(result)
    sent=[]
    async def sync(db,site,**kwargs):
        sent.append(copy.deepcopy(site.default_menu))
        return {'success':True,'status_codes':[201],'last_status_code':201,'results':[]}
    monkeypatch.setattr(services,'sync_project_menus',sync)
    applied=asyncio.run(services.apply_generated_menu_structure(db,site,payload.menu_type,payload.levels,payload.top_level_count,payload.mode,[i.model_dump() for i in payload.items]))
    assert applied['success'] and applied['created_count']==count
    assert sent[0]['header']==original['header']
    assert len(sent[0]['footer'])==roots
    assert len({item['slug'] for item in services._flatten_project_menu_items(sent[0]['footer'])})==count


def test_technical_structure_rejects_unknown_and_duplicate_keys():
    for items in [[{'title':'Promo','technical_page_key':'bonus'}],
                  [{'title':'Privacy','technical_page_key':'privacy'},{'title':'Other privacy','technical_page_key':'privacy'}]]:
        with pytest.raises(ValueError):
            services.normalize_generated_menu_structure(items,1,'technical_pages')


def test_selected_count_limits_flat_technical_preview_before_ai_request(db,monkeypatch):
    site=make_site(db);site.brand='Lemon Casino';site.homepage_title='Lemon Casino';site.cache_geo='PL';site.cache_language='pl-PL'
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://provider.test',api_key='test',is_active=True)
    db.add(provider);db.commit();prompts=[]
    async def generate(p,prompt):
        prompts.append(prompt)
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'brand':None,'labels':{'privacy':'Privacy','cookies':'Cookies','terms':'Terms'}})}]}}]}
    monkeypatch.setattr(services,'call_gemini',generate)
    result=asyncio.run(services.generate_menu_structure_preview(db,provider,site,MenuStructurePreviewRequest(mode='technical_pages',levels=1,top_level_count=3)))
    assert len(result['items'])==3 and result['top_level_count']==3
    assert 'responsible_gaming' not in prompts[0]
    with pytest.raises(ValueError,match='корневых'):
        asyncio.run(services.generate_menu_structure_preview(db,provider,site,MenuStructurePreviewRequest(mode='technical_pages',levels=3,top_level_count=8)))
    assert len(prompts)==1


def test_manual_technical_subset_title_url_and_nesting_reach_native_menu(db,monkeypatch):
    site=make_site(db);site.site_type='monobrand';site.default_menu={'header':[{'id':1,'title':'Original','slug':'/original/'}],'footer':[]}
    db.commit();sent=[]
    async def sync(db,site,**kwargs):
        sent.append(copy.deepcopy(site.default_menu))
        return {'success':True,'status_codes':[201],'last_status_code':201,'results':[]}
    monkeypatch.setattr(services,'sync_project_menus',sync)
    # A single surviving root after deleting other preview rows is valid.
    payload=GeneratedMenuStructureApply(mode='technical_pages',menu_type='footer',levels=2,top_level_count=1,items=[{'title':'Manual privacy label','slug':'/custom-privacy/','technical_page_key':'privacy','children':[{'title':'Manual cookies','slug':'/custom-privacy/my-cookies/','technical_page_key':'cookies'}]}])
    result=asyncio.run(services.apply_generated_menu_structure(db,site,payload.menu_type,payload.levels,payload.top_level_count,payload.mode,[i.model_dump() for i in payload.items]))
    assert result['created_count']==2
    assert sent[0]['header']==[{'id':1,'title':'Original','slug':'/original/'}]
    root=sent[0]['footer'][0]
    assert root['title']=='Manual privacy label' and root['slug']=='/custom-privacy/'
    assert root['children'][0]['slug']=='/custom-privacy/my-cookies/'
    rows=db.scalars(select(models.Section)).all()
    assert next(s for s in rows if s.path=='/custom-privacy/my-cookies/').parent_id==next(s for s in rows if s.path=='/custom-privacy/').id


@pytest.mark.parametrize('slug',['https://outside.test/x/','//outside.test/','/privacy/?x=1','/privacy/#a','/../','/'])
def test_invalid_manual_urls_are_rejected_before_remote_or_local_changes(db,monkeypatch,slug):
    site=make_site(db);before=copy.deepcopy(site.default_menu)
    async def sync(*args,**kwargs):pytest.fail('No native request allowed for invalid preview')
    monkeypatch.setattr(services,'sync_project_menus',sync)
    with pytest.raises(ValueError,match='URL'):
        asyncio.run(services.apply_generated_menu_structure(db,site,'footer',1,1,'technical_pages',[{'title':'Privacy','slug':slug,'technical_page_key':'privacy'}]))
    assert site.default_menu==before and not db.scalars(select(models.Section)).all()


def test_duplicate_urls_and_nested_duplicate_technical_keys_do_not_apply(db,monkeypatch):
    site=make_site(db)
    async def sync(*args,**kwargs):pytest.fail('Invalid menu must not be sent')
    monkeypatch.setattr(services,'sync_project_menus',sync)
    for items in [
        [{'title':'Privacy','slug':'/same/','technical_page_key':'privacy'},{'title':'Cookies','slug':'/same/','technical_page_key':'cookies'}],
    ]:
        with pytest.raises(ValueError,match='повторяется'):
            asyncio.run(services.apply_generated_menu_structure(db,site,'footer',1,2,'technical_pages',items))
    with pytest.raises(ValueError,match='разные технические'):
        services.normalize_generated_menu_structure([{'title':'Privacy','technical_page_key':'privacy','children':[{'title':'Other privacy','technical_page_key':'privacy'}]}],2,'technical_pages')
