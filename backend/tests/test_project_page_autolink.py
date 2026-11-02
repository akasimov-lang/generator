from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app import models,project_page_autolink as links,background_jobs
from test_project_pages import setup


def prepare(setup,text='Try Brand here. Brand again.'):
    client,db,site,state=setup
    site.site_type='monobrand';db.commit()
    page=state['project']['data']['pages'][0]
    page['content']={'blocks':[{'id':'brand','type':'paragraph','data':{'text':text}},{'type':'image','data':{'file':{'url':'/keep.png'}}}]}
    missing=deepcopy(page);missing.update(id='9',slug='/missing/',title='Missing brand')
    missing['content']['blocks'][0]['data']['text']='A useful paragraph about payments.'
    state['project']['data']['pages'].append(missing)
    return db,site,state


def run(db,site):
    request=links.Start(request_id=uuid4())
    result=links.start(site.id,request,{'username':'anton'},db)
    background_jobs.run_job(db,result['id'])
    return request,links.report(site.id,{'username':'anton'},db)


def test_explicit_batch_backs_up_before_write_preserves_pages_and_reports_manual_paragraph(setup):
    db,site,state=prepare(setup)
    home=deepcopy(state['project']['data']['pages'][1])
    request,result=run(db,site)
    assert result['status']=='completed'
    success,missing=result['entries']
    assert success['status']=='confirmed' and '<a href="/">Brand</a>' in success['paragraph']
    assert success['block_index']==0 and success['block_id']=='brand'
    assert missing['status']=='failed' and missing['paragraph']=='A useful paragraph about payments.'
    assert state['project']['data']['pages'][1]==home
    assert state['project']['data']['pages'][0]['content']['blocks'][1]['data']['file']['url']=='/keep.png'
    assert state['events'].index('backup')<state['events'].index('update')
    assert len(state['requests'])==1
    assert links.start(site.id,request,{'username':'anton'},db)['id']==result['id']
    _,again=run(db,site)
    assert again['entries'][0]['status']=='already_linked' and len(state['requests'])==1


def test_uses_second_unlinked_mention_and_never_third(setup):
    db,site,state=prepare(setup,'<a href="/bonus/">Brand</a> and Brand.')
    _,result=run(db,site)
    assert result['entries'][0]['paragraph']=='<a href="/bonus/">Brand</a> and <a href="/">Brand</a>.'
    state['project']['data']['pages'][0]['content']['blocks'][0]['data']['text']='<a href="/a/">Brand</a> <a href="/b/">Brand</a> Brand'
    _,result=run(db,site)
    assert result['entries'][0]['status']=='failed' and len(state['requests'])==1


def test_existing_nofollow_home_link_is_fixed_without_duplicate(setup):
    db,site,state=prepare(setup,'<a href="/" rel="nofollow sponsored noopener">Brand</a> here.')
    _,result=run(db,site)
    assert result['entries'][0]['paragraph']=='<a href="/" rel="noopener">Brand</a> here.'
    assert len(state['requests'])==1


def test_backup_failure_prevents_publication(setup):
    db,site,state=prepare(setup)
    state['backup_apply']=False
    _,result=run(db,site)
    assert result['entries'][0]['status']=='failed'
    assert 'бекап' in result['entries'][0]['message'].lower()
    assert not state['requests']


def test_uncertain_save_is_only_checked_and_new_click_cannot_repeat_write(setup):
    db,site,state=prepare(setup)
    state['apply']=False
    request,result=run(db,site)
    assert result['entries'][0]['status']=='unknown'
    for _ in range(2):
        same=links.start(site.id,links.Start(request_id=uuid4()),{'username':'anton'},db)
        assert same['id']==str(request.request_id)
        links.report(site.id,{'username':'anton'},db)
    assert len(state['requests'])==1


def test_no_brand_is_reported_for_manual_edit_and_access_is_checked(setup):
    db,site,state=prepare(setup)
    with pytest.raises(HTTPException) as denied:
        links.start(site.id,links.Start(request_id=uuid4()),{'username':'other','allowed_site_ids':[]},db)
    assert denied.value.status_code==404
    site.brand='Общие ключи';db.commit()
    _,result=run(db,site)
    assert all(entry['status']=='failed' and entry['paragraph'] for entry in result['entries'])
    assert not state['requests']


def test_manual_page_editor_save_refreshes_report_paragraph_and_success(setup):
    from app import project_pages as pages
    db,site,state=prepare(setup)
    _,report=run(db,site)
    missing=report['entries'][1]
    original=state['project']['data']['pages'][2]
    content=deepcopy(original['content'])
    content['blocks'][0]['data']['text']='A useful <a href="/">homepage</a> link.'
    result=pages.save_page(site.id,missing['key'],pages.PageEdit(request_id=uuid4(),revision=pages.digest(original),title=original['title'],description=original['description'],content=content),{'username':'anton'},db)
    assert result['status']=='confirmed'
    fresh=links.report(site.id,{'username':'anton'},db)
    assert fresh['entries'][1]['status']=='confirmed'
    assert fresh['entries'][1]['paragraph']==content['blocks'][0]['data']['text']
