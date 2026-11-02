import copy
from contextlib import nullcontext
from uuid import uuid4
from urllib.parse import unquote
import httpx,pytest
from app import network_sitemap as sitemap,project_network as network
from test_project_network import env


def test_only_main_and_published_pages():
    main,urls=sitemap.expected({'settings':{'canon':'new.test'},'data':{'pages':[
        {'slug':'/'},{'slug':'/bonus/'},{'slug':'/app/'},{'slug':'/draft/','status':'draft'},
        {'slug':'/removed/','isDeleted':True},{'slug':'/app/'}]}})
    assert urls==['https://new.test/','https://new.test/app/','https://new.test/bonus/']
    assert sitemap.locations(sitemap.document(urls))==urls
    with pytest.raises(ValueError):sitemap.expected({'settings':{'canon':'new.test'},'data':{'pages':[{'slug':'https://old.test/'}]}})


@pytest.mark.parametrize('lost',[False,True])
def test_durable_backup_verified_write_once(env,monkeypatch,lost):
    db,site,remote=env
    remote.data['data']={'pages':[{'slug':'/'},{'slug':'/bonus/'}]};remote.data['sitemap']='old template'
    writes=[]
    def request(method,path,payload):
        writes.append((path,payload));remote.data['sitemap']=unquote(payload['contents'])
        if lost:raise httpx.ReadTimeout('response lost')
        return 200,{}
    remote.request=request
    monkeypatch.setattr(network,'Remote',lambda *args:nullcontext(remote))
    monkeypatch.setattr(sitemap,'public_check',lambda main,urls:None)
    rid=uuid4();op=sitemap.queue(db,site,rid,'test',manual=True);db.commit()
    assert sitemap.queue(db,site,rid,'test',manual=True).id==op.id
    sitemap.process(db,op.id);sitemap.process(db,op.id)
    assert op.status=='sitemap_done' and op.request_payload['before']=='old template'
    assert len(writes)==1 and sitemap.locations(remote.data['sitemap'])==['https://main.test/','https://main.test/bonus/']


def test_uncertain_write_only_rechecks(env,monkeypatch):
    db,site,remote=env;remote.data.update(data={'pages':[{'slug':'/'}]},sitemap='old')
    writes=[]
    def request(*args):writes.append(args);raise httpx.ReadTimeout('lost')
    remote.request=request;monkeypatch.setattr(network,'Remote',lambda *args:nullcontext(remote))
    op=sitemap.queue(db,site,uuid4(),'test');db.commit()
    sitemap.process(db,op.id);sitemap.process(db,op.id)
    assert op.status=='sitemap_verify' and len(writes)==1 and remote.data['sitemap']=='old'
