from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import models, article_image_delivery as delivery


def raw():
    output=BytesIO();Image.new('RGB',(1200,300),'blue').save(output,'WEBP');return output.getvalue()

@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite://');models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        site=models.Site(name='project.test',base_url='https://main.test',publication_endpoint='https://webdev.test')
        db.add(site);db.commit()
        calls=[]
        def request(*args):
            calls.append(args);return 200,{'error':'none','webpPath':'/uploads/articles/webp/article.webp'}
        remote=SimpleNamespace(request=request)
        monkeypatch.setattr(delivery,'source_bytes',lambda db,url:raw())
        monkeypatch.setattr(delivery,'public_image',lambda url:raw())
        yield db,site,remote,calls

def payload():
    return {'pages':[{'slug':'/topic/deep/','title':'Keep','content':{'blocks':[
        {'type':'paragraph','data':{'text':'Keep https://panel.test/file.webp'}},
        {'type':'image','data':{'file':{'url':'https://panel.test/file.webp','width':1200},'alt':'Keep alt'}}]}}]}

def test_upload_precedes_relative_reference_and_retry_reuses_confirmed_file(setup):
    db,site,remote,calls=setup;source=payload();before=deepcopy(source)
    output=delivery.localize_payload(db,site,source,remote,{'settings':{'canon':'main.test'}})
    assert source==before
    assert output['pages'][0]['content']['blocks'][1]['data']=={'file':{'url':'/uploads/articles/webp/article.webp','width':1200},'alt':'Keep alt'}
    assert output['pages'][0]['content']['blocks'][0]==before['pages'][0]['content']['blocks'][0]
    assert calls[0][0:2]==('POST','/projects/image')
    assert calls[0][2]['folder']=='project.test' and calls[0][2]['customPath']=='articles'
    delivery.localize_payload(db,site,source,remote,{'settings':{'canon':'main.test'}})
    assert len(calls)==1

def test_uncertain_upload_is_not_replayed(setup):
    db,site,remote,calls=setup
    def fail(*args):calls.append(args);raise TimeoutError('upload response missing')
    remote.request=fail
    with pytest.raises(TimeoutError):delivery.localize_payload(db,site,payload(),remote,{'settings':{'canon':'main.test'}})
    with pytest.raises(ValueError,match='Повторная запись'):delivery.localize_payload(db,site,payload(),remote,{'settings':{'canon':'main.test'}})
    assert len(calls)==1

def test_upload_with_failed_public_check_can_be_verified_without_second_post(setup,monkeypatch):
    db,site,remote,calls=setup
    monkeypatch.setattr(delivery,'public_image',lambda url: (_ for _ in ()).throw(ValueError('404')))
    with pytest.raises(ValueError,match='404'):delivery.localize_payload(db,site,payload(),remote,{'settings':{'canon':'main.test'}})
    monkeypatch.setattr(delivery,'public_image',lambda url:raw())
    assert delivery.localize_payload(db,site,payload(),remote,{'settings':{'canon':'main.test'}})['generation_meta']['image_delivery']['status']=='confirmed'
    assert len(calls)==1

def test_same_domain_upload_path_becomes_relative_without_copy(setup):
    db,site,remote,calls=setup;p=payload();p['pages'][0]['content']['blocks'][1]['data']['file']['url']='https://main.test/uploads/keep.webp'
    output=delivery.localize_payload(db,site,p,remote,{'settings':{'canon':'main.test'}})
    assert output['pages'][0]['content']['blocks'][1]['data']['file']['url']=='/uploads/keep.webp'
    assert not calls

def test_html_lazy_and_responsive_sources_are_replaced_without_touching_links():
    source={'blocks':[{'type':'raw','data':{'html':'<a href="https://x/a">Keep</a><img src="https://x/a" data-src="https://x/b" srcset="https://x/a 1x, https://x/b 2x">'}}]}
    assert delivery.image_urls(source)==['https://x/a','https://x/b','https://x/a','https://x/b']
    result=delivery.replace_urls(source,{'https://x/a':'/uploads/a','https://x/b':'/uploads/b'})
    assert result['blocks'][0]['data']['html']=='<a href="https://x/a">Keep</a><img src="/uploads/a" data-src="/uploads/b" srcset="/uploads/a 1x, /uploads/b 2x">'

def test_relative_paths_checked_on_nested_page(setup,monkeypatch):
    db,site,remote,calls=setup;p=payload();p['pages'][0]['content']['blocks'][1]['data']['file']['url']='../../uploads/keep.webp';seen=[]
    monkeypatch.setattr(delivery,'public_image',lambda url:seen.append(url) or raw())
    result=delivery.localize_payload(db,site,p,remote,{'settings':{'canon':'main.test'}})
    assert seen==['https://main.test/uploads/keep.webp']
    assert result['pages'][0]['content']['blocks'][1]['data']['file']['url']=='/uploads/keep.webp'
    assert not calls

def test_missing_main_does_not_upload(setup):
    db,site,remote,calls=setup
    with pytest.raises(ValueError,match='Main'):delivery.localize_payload(db,site,payload(),remote,{'settings':{}})
    assert not calls


def test_same_relative_filename_resolves_independently_for_each_page(setup,monkeypatch):
    db,site,remote,calls=setup;p=payload();p['pages'][0]['content']['blocks'][1]['data']['file']['url']='image.webp'
    second=deepcopy(p['pages'][0]);second['slug']='/other/';p['pages'].append(second);seen=[]
    monkeypatch.setattr(delivery,'public_image',lambda url:seen.append(url) or raw())
    result=delivery.localize_payload(db,site,p,remote,{'settings':{'canon':'main.test'}})
    assert seen==['https://main.test/topic/deep/image.webp','https://main.test/other/image.webp']
    assert [x['content']['blocks'][1]['data']['file']['url'] for x in result['pages']]==['/topic/deep/image.webp','/other/image.webp']
    assert not calls
