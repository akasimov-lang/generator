from types import SimpleNamespace
import asyncio
import json
import httpx
import pytest
from app import project_cache

def test_refresh_requests_supported_fields_and_keeps_server_metadata(monkeypatch):
    monkeypatch.setattr(project_cache,'get_settings',lambda:SimpleNamespace(project_cache_url='https://webdev.test',project_cache_username='user',project_cache_password='secret',app_public_url='https://panel.test/'))
    def respond(request):
        if request.url.path=='/auth/login':
            assert request.headers['Origin']=='https://panel.test'
            return httpx.Response(200,json={'token':'session'})
        assert request.url.path=='/projects/cache'
        assert json.loads(request.content)=={'fields':{'settings':True,'head':True,'data':True},'names':['own.test']}
        assert request.headers['Authorization']=='Bearer session'
        return httpx.Response(201,json=[{'name':'own.test','serverIp':'shark','settings':{},'head':{}}])
    client=httpx.Client
    monkeypatch.setattr(project_cache.httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(respond),**kw))
    assert project_cache.fetch_project_cache(['own.test'])[0]['serverIp']=='shark'


def test_publication_token_request_sends_panel_origin(monkeypatch):
    monkeypatch.setattr(project_cache, 'get_settings', lambda: SimpleNamespace(
        project_cache_url='https://webdev.test',
        project_cache_username='user',
        project_cache_password='secret',
        app_public_url='https://panel.test/',
    ))

    def respond(request):
        assert request.url.path == '/auth/login'
        assert request.headers['Origin'] == 'https://panel.test'
        return httpx.Response(200, json={'token': 'publication-token'})

    async def request_token():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await project_cache.refresh_project_server_token(client)

    assert asyncio.run(request_token()) == 'publication-token'


@pytest.fixture
def cache_transport(monkeypatch):
    monkeypatch.setattr(project_cache, 'get_settings', lambda: SimpleNamespace(
        project_cache_url='https://webdev.test', project_cache_username='user',
        project_cache_password='secret', app_public_url='https://panel.test/'))
    sleeps = []
    monkeypatch.setattr(project_cache.time, 'sleep', sleeps.append)
    client = httpx.Client
    def install(respond):
        monkeypatch.setattr(project_cache.httpx, 'Client',
            lambda **kw: client(transport=httpx.MockTransport(respond), **kw))
    return install, sleeps


def test_cache_retries_network_unreachable_during_login(cache_transport):
    install, sleeps = cache_transport
    logins = []
    def respond(request):
        if request.url.path == '/auth/login':
            logins.append(request)
            if len(logins) == 1:
                raise httpx.ConnectError('[Errno 101] Network is unreachable', request=request)
            return httpx.Response(200, json={'token': 'session'})
        return httpx.Response(200, json=[{'name': 'own.test'}])
    install(respond)
    assert project_cache.fetch_project_cache() == [{'name': 'own.test'}]
    assert len(logins) == 2 and sleeps == [1]


def test_cache_read_timeout_reauthenticates_and_preserves_selection(cache_transport):
    install, sleeps = cache_transport
    logins, reads = [], []
    def respond(request):
        if request.url.path == '/auth/login':
            logins.append(request)
            return httpx.Response(200, json={'token': f'session-{len(logins)}'})
        reads.append(request)
        if len(reads) == 1:
            raise httpx.ReadTimeout('temporary read timeout', request=request)
        assert request.headers['Authorization'] == 'Bearer session-2'
        assert json.loads(request.content) == {'fields': {'settings': True, 'head': True, 'data': True}, 'names': ['own.test']}
        return httpx.Response(200, json=[{'name': 'own.test'}])
    install(respond)
    assert project_cache.fetch_project_cache(['own.test']) == [{'name': 'own.test'}]
    assert len(logins) == 2 and len(reads) == 2 and sleeps == [1]


def test_cache_retry_stops_after_three_transport_failures(cache_transport):
    install, sleeps = cache_transport
    requests = []
    def respond(request):
        requests.append(request)
        raise httpx.ConnectError('unavailable', request=request)
    install(respond)
    with pytest.raises(project_cache.ProjectCacheError, match='unavailable') as caught:
        project_cache.fetch_project_cache()
    assert isinstance(caught.value.__cause__, httpx.ConnectError)
    assert len(requests) == 3 and sleeps == [1, 2]


def test_cache_retries_temporary_server_failure(cache_transport):
    install, sleeps = cache_transport
    reads = []
    def respond(request):
        if request.url.path == '/auth/login':
            return httpx.Response(200, json={'token': 'session'})
        reads.append(request)
        return httpx.Response(503 if len(reads) == 1 else 200, json=[])
    install(respond)
    assert project_cache.fetch_project_cache() == []
    assert len(reads) == 2 and sleeps == [1]


def test_cache_does_not_retry_invalid_credentials(cache_transport):
    install, sleeps = cache_transport
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(401, json={'detail': 'unauthorized'})
    install(respond)
    with pytest.raises(project_cache.ProjectCacheError):
        project_cache.fetch_project_cache()
    assert len(requests) == 1 and sleeps == []


def test_cache_does_not_retry_invalid_response_shape(cache_transport):
    install, sleeps = cache_transport
    reads = []
    def respond(request):
        if request.url.path == '/auth/login':
            return httpx.Response(200, json={'token': 'session'})
        reads.append(request)
        return httpx.Response(200, json={'unexpected': []})
    install(respond)
    with pytest.raises(project_cache.ProjectCacheError, match='unexpected response'):
        project_cache.fetch_project_cache()
    assert len(reads) == 1 and sleeps == []


def test_cache_does_not_retry_missing_login_token(cache_transport):
    install, sleeps = cache_transport
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={})
    install(respond)
    with pytest.raises(project_cache.ProjectCacheError, match='did not return a token'):
        project_cache.fetch_project_cache()
    assert len(requests) == 1 and sleeps == []
