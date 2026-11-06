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
