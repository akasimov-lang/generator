import copy,json
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from app import models, background_jobs, services
from app.page_content_trimming import trim
from app.auto_reglue_api import router
from test_project_pages import setup


def test_structural_trims_keep_h1_and_paragraph_without_block_ids():
    content={'version':'2','blocks':[{'type':'header','data':{'text':'Heading','level':1}},
        *[{'type':'paragraph','data':{'text':f'Paragraph {i}'}} for i in range(5)]]}
    before=copy.deepcopy(content)
    assert len(trim(content,'trim_99')['blocks'])==2
    half=trim(content,'trim_50')
    assert len(half['blocks'])==4
    assert sum(b['type']=='paragraph' for b in half['blocks'])==3
    assert content==before
    only_para={'blocks':[{'type':'paragraph','data':{'text':'Body'}}]}
    assert trim(only_para,'trim_99','Page title')['blocks'][0]['data']=={'text':'Page title','level':1}
    with pytest.raises(ValueError):trim({'blocks':[]},'trim_99','Title')


@pytest.mark.parametrize('action',['trim_50','trim_99','meta_headings','paragraphs'])
def test_mass_actions_are_idempotent_drafts_and_never_publish(setup,monkeypatch,action):
    client,db,site,state=setup
    client.app.include_router(router)
    site.project_status='mass_actions';site.cache_geo='PL'
    provider=models.AiProvider(name='Gemini',provider_type='gemini',endpoint_url='https://ai.test',api_key='test')
    db.add(provider);db.commit()
    home=state['project']['data']['pages'][1]
    home['content']['blocks'].insert(0,{'id':'h1','type':'header','data':{'text':'Overview 2026','level':1}})
    before=copy.deepcopy(home)
    calls=[]
    async def generate(_provider,prompt,**kwargs):
        assert not action.startswith('trim_')
        assert len(state['backup_requests']) == 1
        assert state['backups'][0]['data'] == {**before, '_shortcodes': state['project']['shortcodes']}
        data=json.loads(prompt.split('\n',1)[1]);calls.append(data)
        return {'candidates':[{'content':{'parts':[{'text':json.dumps({'items':[{'id':item['id'],'text':'Revised '+item['text']} for item in data['items']]})}]}}]}
    monkeypatch.setattr(services,'call_gemini',generate)
    body={'filter':{'brand':'Brand','geo':'PL'},'request_id':str(uuid4()),'site_ids':[site.id],'action':action,'provider_id':None if action.startswith('trim_') else provider.id}
    response=client.post('/auto-reglue/content-drafts',json=body)
    assert response.status_code==200,response.text
    result=response.json()['results'][0]
    assert result['status']=='queued'
    assert client.post('/auto-reglue/content-drafts',json=body).json()==response.json()
    assert db.scalar(select(func.count()).select_from(models.ProjectPageDraft))==1
    job=db.scalar(select(models.BackgroundJob).where(models.BackgroundJob.kind=='project_page_ai'))
    assert background_jobs.run_job(db,job.id)['status']=='completed'
    status=client.get('/auto-reglue/content-drafts/'+body['request_id']).json()['results'][0]
    assert status['status']=='ready'
    draft=db.get(models.ProjectPageDraft,result['draft_id'])
    if action=='trim_99':assert len(draft.result_content['blocks'])==2
    if action=='meta_headings':
        assert draft.result_metadata=={'title':'Revised Home','description':'Revised About brand'}
        assert draft.result_content['blocks'][0]['data']['text']=='Revised Overview 2026'
        assert draft.result_content['blocks'][1:]==before['content']['blocks'][1:]
    if action.startswith('trim_'):assert not calls and draft.provider_id is None
    assert not state['requests']
    assert home==before
    assert len(state['backup_requests']) == 1
    assert job.result['backup']['name'] == state['backups'][0]['name']
