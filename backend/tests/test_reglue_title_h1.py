from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import select
from app import models,reglue_title_h1 as rewrite
from test_project_pages import setup


def test_minimal_rewrite_keeps_key_numbers_and_markup():
    assert rewrite.minimal('Casino Brand bonus online','Casino Brand online bonus','Brand')=='Casino Brand online bonus'
    for invalid in ('Brand Casino online bonus','Casino Brand bonus 500','Casino Brand very different new words now'):
        with pytest.raises(ValueError):rewrite.minimal('Casino Brand bonus online',invalid,'Brand')


@pytest.mark.parametrize('external_change', [False, True])
def test_manual_refresh_reloads_exact_saved_edit_after_502(setup, monkeypatch, external_change):
    import httpx
    from uuid import uuid5, UUID
    client, db, site, state = setup
    run = models.AutoReglueRun(id=str(uuid4()), site_id=site.id, initiator='test', status='partial', phase='title_h1',
        plan={'rewrite_title_h1': True, 'title_h1_preview': {'title_after': 'Saved title'}})
    db.add(run); db.commit()
    original = deepcopy(state['project']['data']['pages'][1])
    desired = deepcopy(original['content'])
    desired['blocks'].append({'type': 'header', 'data': {'level': 1, 'text': 'Saved H1 text'}})
    state['failure'] = httpx.HTTPStatusError('502', request=httpx.Request('POST', 'https://test.test'), response=httpx.Response(502))
    payload = rewrite.pages.PageEdit(request_id=uuid5(UUID(run.id), 'title-h1-save'), revision=rewrite.pages.digest(original),
        title='Saved title', description=original['description'], content=desired)
    result = rewrite.pages.save_page(site.id, rewrite.pages.page_key(original), payload, {'username': 'test'}, db)
    assert result['status'] == 'unknown' and len(state['requests']) == 1
    state['failure'] = None
    monkeypatch.setattr('app.services.call_gemini', lambda *_: pytest.fail('Must use saved text'))
    if external_change:
        state['project']['data']['pages'][1]['title'] = 'External edit'
        with pytest.raises(ValueError, match='вне плана'): rewrite.retry_saved(db, run)
        assert len(state['requests']) == 1
    else:
        assert rewrite.retry_saved(db, run)
        assert len(state['requests']) == 2
        after = state['project']['data']['pages'][1]
        assert after['title'] == 'Saved title' and after['content'] == desired
        assert after['updatedTime'] and after['banners'] == original['banners']
        assert rewrite.retry_saved(db, run) and len(state['requests']) == 2


def test_response_accepts_literal_whitespace_but_rejects_control_characters():
    assert rewrite.parse_response('```json\n{"title":"Casino Brand online bonus","h1":"Casino Brand\nonline games"}\n```')['h1']=='Casino Brand\nonline games'
    for raw in ('{"title":"bad\x00title","h1":"heading"}', '{"title":null,"h1":"heading"}', '[]'):
        with pytest.raises(ValueError):rewrite.parse_response(raw)


def test_long_h1_is_fully_shortened_preserving_markup_and_neighbor_content(setup,monkeypatch):
    client,db,site,state=setup
    home=state['project']['data']['pages'][1];home['title']='Casino Brand bonus online'
    home['content']['blocks'].append({'type':'raw','data':{'code':'<h1>Casino Brand.<br><span>games online today now</span></h1>'}})
    db.add(models.AiProvider(name='Gemini',provider_type='gemini',api_key='mock',endpoint_url='https://mock.test',model='mock'));db.commit()
    async def generated(provider,prompt):
        assert '"h1": "Casino Brand. games online today now"' in prompt
        assert '3–5 words' in prompt
        return {'candidates':[{'content':{'parts':[{'text':'{"title":"Casino Brand online bonus","h1":"Casino Brand online games"}'}]}}]}
    monkeypatch.setattr('app.services.call_gemini',generated)
    p=rewrite.prepare_preview(db,site,uuid4())
    draft=db.get(models.ProjectPageDraft,p['draft_id'])
    assert draft.result_content['blocks'][-1]['data']['code']=='<h1>Casino Brand online games<br><span></span></h1>'
    assert draft.result_content['blocks'][:-1]==home['content']['blocks'][:-1]
    assert not state['requests']


def test_shortening_allows_full_rewrite_and_enforces_length_brand_key_and_facts():
    original='Casino Brand: the <span>very best games &amp; offers online 2026</span>'
    result=rewrite.short_heading(original,'Casino Brand official review','Brand')
    assert rewrite.heading_text(result)=='Casino Brand official review'
    assert '<span>' in result and '&amp;' not in result
    assert rewrite.heading_words('Casino Brand<br>online games today now')==['casino','brand','online','games','today','now']
    for invalid in ('Casino Brand', 'Casino Brand the best online games', 'Brand Casino online games',
                    'Casino Brand bonus 999', '<b>Casino Brand online</b>'):
        with pytest.raises(ValueError):rewrite.short_heading(original,invalid,'Brand')
    with pytest.raises(ValueError,match='бренд'):
        rewrite.short_heading('Online casino Brand excellent games today','Online casino games','Brand')


def test_legacy_preview_only_requires_update_for_selected_long_h1():
    p={'rewrite_title_h1':True,'title_h1_preview':{'h1_before':'Casino Brand the best games online today','h1_after':'Casino Brand the best online games today'}}
    assert rewrite.preview_needs_shortening(p)
    p['rewrite_title_h1']=False
    assert not rewrite.preview_needs_shortening(p)
    p['rewrite_title_h1']=True;p['title_h1_preview']['h1_after']='Casino Brand online games'
    assert not rewrite.preview_needs_shortening(p)


def test_forced_refresh_uses_fresh_snapshot_and_discards_previous_draft(setup,monkeypatch):
    client,db,site,state=setup
    home=state['project']['data']['pages'][1];home['title']='Casino Brand updated offers'
    home['content']['blocks'].append({'type':'header','data':{'level':1,'text':'Casino Brand latest online games today'}})
    db.add(models.AiProvider(name='Gemini',provider_type='gemini',api_key='mock',endpoint_url='https://mock.test',model='mock'));db.commit()
    async def generated(provider,prompt):
        assert 'Casino Brand updated offers' in prompt
        return {'candidates':[{'content':{'parts':[{'text':'{"title":"Casino Brand offers updated","h1":"Casino Brand online games"}'}]}}]}
    monkeypatch.setattr('app.services.call_gemini',generated)
    monkeypatch.setattr(rewrite.pages,'Remote',lambda *a:pytest.fail('Use the already fetched snapshot'))
    p={'site_id':site.id,'rewrite_title_h1':True,'title_h1_preview':{'draft_id':str(uuid4()),'h1_before':'Casino Brand games','h1_after':'Casino Brand online','title_after':'Stale title'}}
    old=p['title_h1_preview']['draft_id']
    rewrite.prepare_for_plan(db,p,uuid4(),project=state['project'],force=True)
    assert 'title_h1_error' not in p,p
    assert p['title_h1_preview']['draft_id']!=old
    assert p['title_h1_preview']['title_before']==home['title']
    assert p['title_h1_preview']['title_after']=='Casino Brand offers updated'
    assert p['title_h1_preview']['h1_after']=='Casino Brand online games'
    # A removed H1 must never leave an old ready draft visible or runnable.
    home['content']['blocks'].pop()
    rewrite.prepare_for_plan(db,p,uuid4(),project=state['project'],force=True)
    assert 'title_h1_preview' not in p and p.get('title_h1_error')
    assert not state['requests']


def test_title_h1_only_backup_and_modified_date_once(setup,monkeypatch):
    client,db,site,state=setup
    home=state['project']['data']['pages'][1];home['title']='Casino Brand bonus online'
    home['content']['blocks'] += [{'type':'header','data':{'level':1,'text':'Casino Brand games online'}},{'type':'header','data':{'level':2,'text':'Keep H2'}}]
    original=deepcopy(home)
    provider=models.AiProvider(name='Gemini',provider_type='gemini',api_key='mock',endpoint_url='https://mock.test',model='mock');db.add(provider)
    run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='test',status='running',phase='alternates',plan={'rewrite_title_h1':True});db.add(run);db.commit()
    async def generated(provider,prompt):
        return {'candidates':[{'content':{'parts':[{'text':'{"title":"Casino Brand online bonus","h1":"Casino Brand online games"}'}]}}]}
    monkeypatch.setattr('app.services.call_gemini',generated)
    assert rewrite.finish(db,run)
    after=state['project']['data']['pages'][1]
    assert after['title']=='Casino Brand online bonus'
    assert after['content']['blocks'][-2]['data']['text']=='Casino Brand online games'
    assert after['content']['blocks'][:-2]==original['content']['blocks'][:-2]
    assert after['description']==original['description'] and after['content']['blocks'][-1]==original['content']['blocks'][-1]
    assert after['updatedTime']==run.plan['title_h1_updated_at']
    assert state['backup_requests'] and len(state['requests'])==1
    assert rewrite.finish(db,run) and len(state['requests'])==1


@pytest.mark.parametrize('reject_first',[False,True])
def test_preview_only_generates_then_execution_saves_exact_review_once(setup,monkeypatch,reject_first):
    client,db,site,state=setup
    home=state['project']['data']['pages'][1];home['title']='Casino Brand bonus online'
    home['content']['blocks'] += [{'type':'header','data':{'level':1,'text':'Casino Brand games online'}}]
    db.add(models.AiProvider(name='Gemini',provider_type='gemini',api_key='mock',endpoint_url='https://mock.test',model='mock'));db.commit()
    calls=[]
    async def generated(provider,prompt):
        calls.append(prompt)
        if reject_first and len(calls)==1:
            return {'candidates':[{'content':{'parts':[{'text':'{"title":"Brand Casino online bonus","h1":"Casino Brand online games"}'}]}}]}
        return {'candidates':[{'content':{'parts':[{'text':'{"title":"Casino Brand online bonus","h1":"Casino Brand online games"}'}]}}]}
    monkeypatch.setattr('app.services.call_gemini',generated)
    job_id=uuid4();preview=rewrite.prepare_preview(db,site,job_id)
    assert preview==rewrite.prepare_preview(db,site,job_id)
    assert len(calls)==1+int(reject_first) and not state['requests'] and not state['backup_requests']
    assert home['title']==preview['title_before']
    run=models.AutoReglueRun(id=str(uuid4()),site_id=site.id,initiator='test',status='running',phase='alternates',plan={'rewrite_title_h1':True,'title_h1_preview':preview});db.add(run);db.commit()
    assert rewrite.finish(db,run)
    assert state['project']['data']['pages'][1]['title']==preview['title_after']
    assert len(calls)==1+int(reject_first) and len(state['requests'])==1
