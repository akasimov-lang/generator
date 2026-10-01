from types import SimpleNamespace
import asyncio
import json
import httpx
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
