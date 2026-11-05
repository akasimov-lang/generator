from test_project_pages import setup
from copy import deepcopy
import pytest
from app.showcase_standardization import prepare,PositionedTree

CARD='<article class="casino-card"><h3>A Casino</h3><img alt="A Casino" src="/uploads/a.png"><div class="bonus-value">100% + 20 FS</div><a href="/go/a?x=1&amp;y=2">Get bonus</a></article>'


def project(blocks,templates=()):
    return {'settings':{'canon':'site.test'},'data':{'casinos':{'standard':[[{'key':'brand','value':'Unused'}]],'basic':[]},'pages':[{'id':'1','slug':'/','title':'Original','content':{'blocks':blocks}}]},'shortcodes':list(templates),'layout':''}


def test_html_block_standardization_preserves_surrounding_article_and_source_data():
    original=project([{'id':'html','type':'code','data':{'code':'<section><h2>Keep intro</h2>'+CARD+'<p>Keep footer</p></section>'}}]);before=deepcopy(original)
    plan=prepare(original,CARD,['A Casino'])
    assert original==before
    blocks=plan['pages'][0][1]['content']['blocks']
    assert blocks[0]['data']['code']=='<section><h2>Keep intro</h2>'
    assert blocks[1]['type']=='shortcode'
    assert blocks[-1]['data']['code']=='<p>Keep footer</p></section>'
    assert plan['casinos_after']['standard']==original['data']['casinos']['standard']
    fields={f['key']:f.get('value') for f in plan['casinos_after']['pagepilot_standard_1'][0]}
    assert fields['bonus']=='100% + 20 FS'
    assert '/go/a?x=1&amp;y=2' in fields['actions_html']
    assert plan['brands_after']==['A Casino']


def test_shortcode_standardization_changes_only_card_ranges():
    markup='<style>.casino-card{color:red}</style><div>'+CARD+'<p>Unrelated paragraph</p></div>'
    original=project([{'id':'sc','type':'shortcode','data':{'shortcode':'casinos'}}],[{'name':'casinos.hbs','data':markup}])
    plan=prepare(original,CARD,['A Casino'])
    assert not plan['pages']
    assert plan['templates'][0][1]['data']=='<style>.casino-card{color:red}</style><div>{{> casinos-standard-1}}<p>Unrelated paragraph</p></div>'


def test_table_standardization_retains_all_terms_without_inventing_call_to_action():
    block={'id':'table','type':'table','data':{'content':[['Casino','Bonus','Licence'],['A Casino','50 FS','Original licence']]}}
    plan=prepare(project([block]),'', ['A Casino'])
    fields={f['key']:f.get('value') for f in plan['casinos_after']['pagepilot_standard_1'][0]}
    assert fields['bonus']=='50 FS' and 'Original licence' in fields['conditions']
    assert fields['actions_html']==''


def test_standardization_refuses_partial_brand_extraction():
    with pytest.raises(ValueError,match='Состав брендов'):
        prepare(project([{'id':'html','type':'code','data':{'code':CARD}}]),CARD,['A Casino','Missing'])


def test_publish_stops_before_any_write_if_saved_revision_is_stale():
    from types import SimpleNamespace
    from app.showcase_standardization import publish
    original=project([{'id':'table','type':'table','data':{'content':[['Casino','Bonus'],['A Casino','50 FS']]}}])
    plan=prepare(original,'',['A Casino'])
    remote=SimpleNamespace(project=lambda:{**original,'layout':'Changed'})
    with pytest.raises(ValueError,match='Проект изменился'):
        publish(None,SimpleNamespace(id='site'),remote,plan,'00000000-0000-0000-0000-000000000001')


class MemoryRemote:
    def __init__(self,document,fail=False):
        self.document=deepcopy(document);self.calls=[];self.fail=fail
    def project(self):return deepcopy(self.document)
    def request(self,method,path,payload):
        from urllib.parse import unquote
        self.calls.append(path)
        if self.fail:raise TimeoutError('Unconfirmed request')
        if path=='/projects/casinos':self.document['data']['casinos']=deepcopy(payload['casinos'])
        elif path=='/projects/shortcode':
            name=payload['filename']+'.hbs';self.document['shortcodes']=[s for s in self.document['shortcodes'] if s['name']!=name]+[{'name':name,'data':unquote(payload['contents'])}]
        elif path=='/projects/update':
            self.document['data']['pages']=[deepcopy(payload['page']) if str(p['id'])==str(payload['id']) else p for p in self.document['data']['pages']]
        return 200,{}


def test_publish_records_confirmed_steps_and_preserves_original_brand_terms(setup):
    from uuid import uuid4
    from app.showcase_standardization import publish
    from app import models
    _,db,site,_=setup
    original=project([{'id':'table','type':'table','data':{'content':[['Casino','Bonus'],['A Casino','50 FS']]}}])
    plan=prepare(original,'',['A Casino']);remote=MemoryRemote(original)
    result=publish(db,site,remote,plan,str(uuid4()))
    assert len(result['receipt_ids'])==3
    assert all(db.get(models.ProjectPageEdit,key).status=='confirmed' for key in result['receipt_ids'])
    assert len(remote.calls)==3
    assert result['project']['data']['casinos']['standard']==original['data']['casinos']['standard']


def test_unconfirmed_publication_is_recorded_and_never_retried(setup):
    from uuid import uuid4
    from app.showcase_standardization import publish
    from app import models
    from sqlalchemy import select
    _,db,site,_=setup
    original=project([{'id':'table','type':'table','data':{'content':[['Casino','Bonus'],['A Casino','50 FS']]}}])
    plan=prepare(original,'',['A Casino']);remote=MemoryRemote(original,fail=True);rid=str(uuid4())
    with pytest.raises(ValueError):publish(db,site,remote,plan,rid)
    with pytest.raises(ValueError,match='повтор запрещён'):publish(db,site,remote,plan,rid)
    assert remote.calls==['/projects/casinos']
    op=db.scalar(select(models.ProjectPageEdit).where(models.ProjectPageEdit.site_id==site.id))
    assert op.status=='unknown' and op.before_page and op.after_page
