from uuid import uuid4
import httpx
from sqlalchemy import select

from app import models, network_indexing as indexing, project_network as network
from test_project_network import env, change, MARKUP


def receipts(db):
    return db.scalars(select(models.NetworkOperation).where(models.NetworkOperation.action == 'indexing')).all()


def test_manual_confirmation_queues_once_excludes_amp_and_history(env):
    db, site, remote = env
    # Exercise production session behavior: queued receipt must see flushed confirmation.
    db.autoflush = False
    remote.data['settings']['domains'] += ['amp.test', 'next.test']
    remote.data['settings']['ampDomains'] = ['amp.test']
    before = network.read_network(db, site)
    result = change(env, 'reglue', before['revision'], domain='reserve.test')
    assert len(receipts(db)) == 1
    op = receipts(db)[0]
    assert op.status == 'index_queued'
    assert op.request_payload['domains'] == ['https://main.test/', 'https://reserve.test/', 'https://next.test/']
    assert '_indexing' not in remote.calls[-1][2]
    for _ in range(2):
        network.read_network(db, site)
    assert len(receipts(db)) == 1
    assert any(x['action'] == 'indexing' and len(x['domains']) == 3 for x in result['operations'])


def test_waits_for_canonical_and_exact_alternates_then_recovers_without_browser(env, monkeypatch):
    db, site, remote = env
    remote.delayed = True
    before = network.read_network(db, site)
    change(env, 'reglue', before['revision'], domain='reserve.test')
    assert not receipts(db)
    remote.data['settings']['canon'] = 'reserve.test'
    remote.data['head']['alternateMarkup'] = ''
    network.read_network(db, site)
    assert not receipts(db)
    remote.data['head']['alternateMarkup'] = MARKUP
    submitted = []
    monkeypatch.setattr(indexing, 'submit_network_indexing', lambda db, op_id: submitted.append(op_id))
    indexing.process_network_indexing(db)
    assert len(receipts(db)) == 1 and submitted == [receipts(db)[0].id]
    assert len(remote.calls) == 1  # Recovery never resends the reglue.


def test_indexing_submission_persists_id_and_never_repeats(env):
    db, site, remote = env
    state = network.read_network(db, site)
    op = indexing.queue_indexing(db, site, state, str(uuid4()), 'admin'); db.commit()
    sent = []
    def respond(request):
        assert db.get(models.NetworkOperation, op.id).status == 'index_submitting'
        sent.append(request)
        return httpx.Response(200, json={'google': {'icon': 'success', 'text': 'ID задачи: task-123.'}})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        indexing.submit_network_indexing(db, op.id, client=client)
        indexing.submit_network_indexing(db, op.id, client=client)
    assert len(sent) == 1 and op.status == 'index_submitted'
    assert op.request_payload['task_id'] == 'task-123'
    assert network.operation_history(db, site)[0]['task_id'] == 'task-123'


def test_lost_response_never_retries(env):
    db, site, _ = env
    op = indexing.queue_indexing(db, site, network.read_network(db, site), str(uuid4()), 'admin'); db.commit()
    sent = []
    def timeout(request):
        sent.append(request)
        raise httpx.ReadTimeout('timeout')
    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        indexing.submit_network_indexing(db, op.id, client=client)
        indexing.submit_network_indexing(db, op.id, client=client)
    assert op.status == 'index_unknown' and len(sent) == 1


def test_failed_reglue_does_not_queue(env):
    db, site, remote = env
    before = network.read_network(db, site)
    remote.fail = httpx.HTTPStatusError('bad request', request=httpx.Request('POST', 'https://example.test'), response=httpx.Response(400))
    change(env, 'reglue', before['revision'], domain='reserve.test')
    assert not receipts(db)


def test_partial_head_observation_does_not_confirm_indexing(env):
    db, site, remote = env
    before = network.read_network(db, site); remote.delayed = True
    change(env, 'reglue', before['revision'], domain='reserve.test')
    remote.data['settings']['canon'] = 'reserve.test'
    full_head = remote.data.pop('head')
    partial = network.read_network(db, site)
    assert partial['head_verified'] is False and not receipts(db)
    remote.data['head'] = full_head
    network.read_network(db, site)
    assert len(receipts(db)) == 1


def test_history_endpoint_reads_only_database(monkeypatch):
    from test_api_serialization import make_client
    client, sessions = make_client()
    with sessions() as db:
        site = db.scalar(select(models.Site)); site_id = site.id
        op = indexing.queue_indexing(db, site, {'domains': ['example.test'], 'amp_domains': []}, str(uuid4()), 'admin'); db.commit()
    monkeypatch.setattr(network, 'read_network', lambda *args: (_ for _ in ()).throw(AssertionError('unexpected Webdev read')))
    response = client.get(f'/api/sites/{site_id}/network/operations')
    assert response.status_code == 200
    assert response.json()[0]['action'] == 'indexing'
