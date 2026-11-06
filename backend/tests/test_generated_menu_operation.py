import asyncio
import copy
import pytest
from sqlalchemy import select
from app import models, services
from app.schemas import GeneratedMenuStructureApply
from test_generation_modes import db, make_site


def setup_menu(db):
    site = make_site(db)
    site.default_menu = {'header':[{'id':11,'title':'Old','slug':'/old/'}], 'footer':[{'id':22,'title':'Footer','slug':'/footer/'}]}
    section = models.Section(site_id=site.id, external_id='11', name='Old', path='/old/', menu_type='header', sync_status='synced')
    db.add(section); db.commit()
    return site, section


def test_replace_selected_menu_preserves_pages_and_other_menu(db, monkeypatch):
    site, old = setup_menu(db)
    before = copy.deepcopy(site.default_menu)
    async def sync(db, site, **kwargs):
        payload = services.build_project_menu_payload(db, site, 'header')
        assert 'Old' not in str(payload)
        return {'success':True,'results':[]}
    monkeypatch.setattr(services, 'sync_project_menus', sync)
    result = asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,1,'thematic',[{'title':'New','slug':'/new/'}],operation='replace'))
    assert result['success']
    assert [x['slug'] for x in site.default_menu['header']] == ['/new/']
    assert site.default_menu['footer'] == before['footer']
    assert db.get(models.Section,old.id) is old
    assert old.sync_status == 'external_deleted'
    log = db.scalar(select(models.PublicationLog))
    assert log.request_payload['menu_before'] == before['header']


def test_failed_replacement_restores_old_menu_and_sections(db, monkeypatch):
    site, old = setup_menu(db)
    before = copy.deepcopy(site.default_menu)
    async def sync(*args, **kwargs):
        return {'success':False,'last_status_code':502,'results':[]}
    monkeypatch.setattr(services, 'sync_project_menus', sync)
    result = asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,1,'thematic',[{'title':'New','slug':'/new/'}],operation='replace'))
    assert result['rolled_back']
    assert site.default_menu == before
    assert old.sync_status == 'synced'
    assert len(db.scalars(select(models.Section).where(models.Section.site_id==site.id)).all()) == 1


def test_default_operation_appends_and_replace_rejects_pending_edits(db, monkeypatch):
    site, old = setup_menu(db)
    payload = GeneratedMenuStructureApply(levels=1,top_level_count=1,items=[{'title':'New','slug':'/new/'}])
    assert payload.operation == 'append'
    async def sync(*args, **kwargs):
        return {'success':True,'results':[]}
    monkeypatch.setattr(services, 'sync_project_menus', sync)
    asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,1,'thematic',[i.model_dump() for i in payload.items]))
    assert [x['slug'] for x in site.default_menu['header']] == ['/old/','/new/']
    old.sync_status = 'pending'; db.commit()
    with pytest.raises(ValueError,match='Дождитесь'):
        asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,1,'thematic',[{'title':'Another','slug':'/another/'}],operation='replace'))


def test_append_children_to_selected_existing_parent_preserves_siblings(db, monkeypatch):
    site, old = setup_menu(db)
    site.default_menu = {'header':[{'id':11,'title':'Old','slug':'/old/','children':[{'id':12,'title':'Existing child','slug':'/old/existing/'}]},{'id':13,'title':'Untouched','slug':'/other/'}], 'footer':[]}
    db.commit()
    async def sync(db,site,**kwargs):
        native = services.build_project_menu_payload(db,site,'header')
        assert 'New child' in str(native)
        return {'success':True,'results':[]}
    monkeypatch.setattr(services,'sync_project_menus',sync)
    result=asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,2,'thematic',[
        {'title':'New child','slug':'/old/new/','parent_slug':'/old/'},
        {'title':'New root','slug':'/root/'}]))
    assert result['created_count']==2
    assert [x['slug'] for x in site.default_menu['header']]==['/old/','/other/','/root/']
    assert [x['slug'] for x in site.default_menu['header'][0]['children']]==['/old/existing/','/old/new/']
    child=db.scalar(select(models.Section).where(models.Section.path=='/old/new/'))
    assert child.parent_id==old.id


def test_missing_nested_parent_stops_before_creating_sections(db, monkeypatch):
    site,old=setup_menu(db)
    before=copy.deepcopy(site.default_menu)
    with pytest.raises(ValueError,match='родительский'):
        asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,1,'thematic',[{'title':'Child','slug':'/missing/child/','parent_slug':'/missing/'}]))
    assert site.default_menu==before
    assert len(db.scalars(select(models.Section).where(models.Section.site_id==site.id)).all())==1


def test_nested_preview_uses_parent_topic_and_requested_count_without_mutating_menu(db, monkeypatch):
    from app.schemas import MenuStructurePreviewRequest
    import json
    site,old=setup_menu(db);site.cache_geo='DK';site.cache_language='da-DK'
    before=copy.deepcopy(site.default_menu)
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://ai.test',api_key='test',is_active=True)
    db.add(provider);db.commit();prompts=[]
    async def generate(provider,prompt):
        prompts.append(prompt)
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'items':[{'title':'Spilleformer','slug':'/spilleformer/'},{'title':'Betalingsvalg','slug':'/betalingsvalg/'}]})}]}}]}
    monkeypatch.setattr(services,'call_gemini',generate)
    result=asyncio.run(services.generate_menu_structure_preview(db,provider,site,MenuStructurePreviewRequest(parent_paths=['/old/'],nested_count=2,include_top_level=False,levels=1)))
    assert len(result['items'])==2
    assert all(item['parent_slug']=='/old/' and item['slug'].startswith('/old/') for item in result['items'])
    assert 'Parent menu section: Old' in prompts[0]
    assert site.default_menu==before


def test_append_rejects_existing_title_even_with_new_url(db):
    site,old=setup_menu(db)
    with pytest.raises(ValueError,match='названия уже есть'):
        asyncio.run(services.apply_generated_menu_structure(db,site,'header',1,1,'thematic',[{'title':'OLD','slug':'/different/'}]))
    assert len(db.scalars(select(models.Section).where(models.Section.site_id==site.id)).all())==1


def test_exact_nested_count_retries_wrong_ai_shape(db,monkeypatch):
    from app.schemas import MenuStructurePreviewRequest
    import json
    site,old=setup_menu(db);site.cache_geo='DK';site.cache_language='da-DK'
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://ai.test',api_key='test',is_active=True)
    db.add(provider);db.commit();calls=[]
    async def generate(provider,prompt):
        calls.append(prompt)
        items=[{'title':'Spilvalg','children':[{'title':'Kortspil'}]+([{'title':'Bordspil'}] if len(calls)>1 else [])}]
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'items':items})}]}}]}
    monkeypatch.setattr(services,'call_gemini',generate)
    result=asyncio.run(services.generate_menu_structure_preview(db,provider,site,MenuStructurePreviewRequest(levels=2,top_level_count=1,children_per_parent=2)))
    assert len(calls)==2
    assert len(result['items'][0]['children'])==2


def test_oversized_nested_menu_rejected_before_provider_request(db):
    from app.schemas import MenuStructurePreviewRequest
    site,old=setup_menu(db)
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://ai.test',api_key='test',is_active=True)
    with pytest.raises(ValueError,match='80'):
        asyncio.run(services.generate_menu_structure_preview(db,provider,site,MenuStructurePreviewRequest(levels=3,top_level_count=5,children_per_parent=10)))
