from uuid import uuid4
from test_permissions import api


def test_queue_endpoint_accepts_task_without_webdev_and_get_is_read_only(api,monkeypatch):
    client,engine,grants=api
    monkeypatch.setattr('app.project_network.Remote',lambda *_:(_ for _ in ()).throw(AssertionError('No Webdev request while enqueuing')))
    request={'request_id':str(uuid4()),'action':'create','path':'resources'}
    reply=client.post('/api/sites/own/network/fake-main-queue',json=request)
    assert reply.status_code==202,reply.text
    assert reply.json()['items'][0]['path']=='/resources' and reply.json()['items'][0]['status']=='queued'
    assert client.post('/api/sites/own/network/fake-main-queue',json=request).json()['active_count']==1
    assert client.get('/api/sites/own/network/fake-main-queue').json()['active_count']==1


def test_queue_cannot_be_read_or_changed_for_inaccessible_project(api):
    client,_,_=api
    assert client.get('/api/sites/other/network/fake-main-queue').status_code==404
    assert client.post('/api/sites/other/network/fake-main-queue',json={'request_id':str(uuid4()),'action':'delete','path':'old'}).status_code==404
