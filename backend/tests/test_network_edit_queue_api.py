from uuid import uuid4
from test_permissions import api


def test_enqueue_and_read_do_not_contact_webdev(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr('app.project_network.Remote', lambda *_: (_ for _ in ()).throw(AssertionError('Enqueue contacted Webdev')))
    payload = {'request_id': str(uuid4()), 'action': 'reserve', 'revision': 'cached', 'domain': 'next.test', 'expected': {'canon': 'main.test', 'reserve': ''}}
    response = client.post('/api/sites/own/network/edit-queue', json=payload)
    assert response.status_code == 202, response.text
    assert response.json()['items'][0]['status'] == 'queued'
    assert len(client.post('/api/sites/own/network/edit-queue', json=payload).json()['items']) == 1
    assert len(client.get('/api/sites/own/network/edit-queue').json()['items']) == 1


def test_queue_respects_project_access(api):
    client, _, _ = api
    assert client.get('/api/sites/other/network/edit-queue').status_code == 404
    assert client.post('/api/sites/other/network/edit-queue', json={'request_id': str(uuid4()), 'action': 'reserve', 'revision': 'cached', 'domain': 'next.test', 'expected': {'canon': 'main.test', 'reserve': ''}}).status_code == 404
